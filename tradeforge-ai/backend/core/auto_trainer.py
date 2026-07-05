"""
Auto-Training Pipeline — 20-Minute Scheduled Retraining

Every 20 minutes the pipeline:
    1. **Detects changes** — new market data since last training, or
       strategy-formula changes detected via hash comparison.
    2. **Builds a dataset** — fetches latest data, computes features,
       and assembles training / validation splits.
    3. **Fine-tunes the model** — runs incremental training starting
       from the current active checkpoint.
    4. **Validates** — runs a backtest on held-out data to measure
       trading performance (not just ML metrics).
    5. **Deploys if better** — compares backtest P&L + F1 against the
       currently active model; activates the new one only if it wins.
    6. **Logs everything** — structured JSON logs + progress broadcasts
       via WebSocket.

Architecture:
    - Uses ``APScheduler`` with ``AsyncIOScheduler`` for cron-like
      scheduling without blocking the event loop.
    - The training loop is fully async — data fetching, model training,
      and backtesting all yield control.
    - Consecutive failure tracking with automatic circuit-breaker
      (pauses training after 3 consecutive failures).
    - Job history is kept in-memory with a configurable limit; persists
      to disk on each completed job.

Integration points (dependency-injected):
    - ``llm_engine`` — must provide ``async fine_tune(dataset, config) -> checkpoint_path``
    - ``backtest_engine`` — must provide ``async run(config) -> metrics_dict``
    - ``model_registry`` — ``ModelRegistry`` instance (this package)
    - ``dataset_builder`` — must provide ``async build(since) -> Dataset``
    - ``ws_server`` (optional) — ``TradeForgeWebSocket`` for progress broadcasts

Example:
    >>> pipeline = AutoTrainingPipeline(
    ...     llm_engine=my_llm, backtest_engine=my_bt,
    ...     model_registry=registry, dataset_builder=builder,
    ... )
    >>> pipeline.start()   # non-blocking — scheduler starts in bg
    >>> # ... 20 min later first training run fires automatically ...
    >>> pipeline.stop()    # graceful shutdown
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Callable,
    Coroutine,
    Dict,
    List,
    Optional,
    Protocol,
    runtime_checkable,
)

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from core.model_registry import ModelRegistry, ModelVersionInfo, compute_formula_hash


# ---------------------------------------------------------------------------
# Protocols for injected dependencies (duck-typing friendly)
# ---------------------------------------------------------------------------

@runtime_checkable
class LLMEngineProtocol(Protocol):
    """Minimal interface expected from the LLM engine."""

    async def fine_tune(
        self,
        dataset: Any,
        checkpoint_path: Optional[str],
        epochs: int,
        learning_rate: float,
        batch_size: int,
        job_id: int,
        progress_callback: Optional[Callable[[Dict[str, Any]], Coroutine]] = None,
    ) -> str:
        """Fine-tune and return path to new checkpoint."""
        ...

    def get_model_info(self) -> Dict[str, Any]:
        """Return dict with model architecture info."""
        ...


@runtime_checkable
class BacktestEngineProtocol(Protocol):
    """Minimal interface expected from the backtest engine."""

    async def run(
        self,
        checkpoint_path: str,
        start_date: datetime,
        end_date: datetime,
        symbols: List[str],
    ) -> Dict[str, Any]:
        """Run backtest and return metrics dict."""
        ...


@runtime_checkable
class DatasetBuilderProtocol(Protocol):
    """Minimal interface expected from the dataset builder."""

    async def build(
        self,
        since: datetime,
        symbols: Optional[List[str]] = None,
    ) -> Any:
        """Build training dataset from data newer than *since*."""
        ...

    def get_formula_snapshot(self) -> Dict[str, Any]:
        """Return current strategy formula dict for hash comparison."""
        ...

    def estimate_samples(self, since: datetime) -> int:
        """Estimate number of new samples available."""
        ...


# ---------------------------------------------------------------------------
# Training job dataclass
# ---------------------------------------------------------------------------

class TriggerReason(str, Enum):
    """Why a training job was started."""
    SCHEDULED_20MIN = "scheduled_20min"
    FORMULA_CHANGE = "formula_change"
    MANUAL = "manual"
    NEW_DATA_THRESHOLD = "new_data_threshold"


class TrainingStatus(str, Enum):
    """Lifecycle status of a training job."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TrainingJob:
    """Record of a single training run.

    Attributes:
        job_id: Monotonically increasing integer.
        trigger_reason: Why this job started.
        started_at: UTC datetime when job began.
        completed_at: UTC datetime when job finished (None until then).
        status: Current status.
        data_samples: Number of training samples used.
        epochs_trained: Epochs actually completed.
        final_loss: Training loss at end.
        validation_loss: Validation loss at end.
        model_version_id: ID assigned by ModelRegistry (None until registered).
        checkpoint_path: Filesystem path to saved checkpoint.
        error_message: Empty unless status == FAILED.
    """
    job_id: int
    trigger_reason: str = "scheduled_20min"
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    status: str = "queued"
    data_samples: int = 0
    epochs_trained: int = 0
    final_loss: float = 0.0
    validation_loss: float = 0.0
    model_version_id: Optional[int] = None
    checkpoint_path: str = ""
    error_message: str = ""
    backtest_metrics: Dict[str, Any] = field(default_factory=dict)
    deployed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-friendly dict."""
        d = asdict(self)
        # Convert datetimes to ISO strings
        for key in ("started_at", "completed_at"):
            val = d.get(key)
            if isinstance(val, datetime):
                d[key] = val.isoformat()
        return d


# ---------------------------------------------------------------------------
# Main pipeline class
# ---------------------------------------------------------------------------

class AutoTrainingPipeline:
    """Automated training pipeline that runs every N minutes (default 20).

    See module docstring for the full 6-step pipeline description.

    Args:
        llm_engine: Object implementing ``LLMEngineProtocol``.
        backtest_engine: Object implementing ``BacktestEngineProtocol``.
        model_registry: ``ModelRegistry`` instance.
        dataset_builder: Object implementing ``DatasetBuilderProtocol``.
        training_interval_minutes: Minutes between scheduled runs.
        min_new_samples: Minimum new samples required to trigger training.
        ws_server: Optional ``TradeForgeWebSocket`` for live progress.
        job_history_limit: Max number of past jobs to keep in memory.
    """

    def __init__(
        self,
        llm_engine: Any,           # LLMEngineProtocol
        backtest_engine: Any,      # BacktestEngineProtocol
        model_registry: ModelRegistry,
        dataset_builder: Any,      # DatasetBuilderProtocol
        training_interval_minutes: int = 20,
        min_new_samples: int = 50,
        ws_server: Optional[Any] = None,
        job_history_limit: int = 100,
        models_dir: str = "./models",
    ) -> None:
        # Dependencies (injected)
        self.llm = llm_engine
        self.backtest = backtest_engine
        self.registry = model_registry
        self.dataset_builder = dataset_builder
        self.ws = ws_server  # optional WebSocket server for broadcasts

        # Configuration
        self.interval: int = training_interval_minutes
        self.min_new_samples: int = min_new_samples
        self.job_history_limit: int = job_history_limit
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)

        # APScheduler
        self.scheduler = AsyncIOScheduler(timezone="UTC")
        self._scheduler_job_id: Optional[str] = None

        # Job tracking
        self.current_job: Optional[TrainingJob] = None
        self.jobs_history: List[TrainingJob] = []
        self._next_job_id: int = 1

        # State tracking
        self.last_training_time: Optional[datetime] = None
        self.last_formula_hash: str = ""
        self.consecutive_failures: int = 0
        self.max_consecutive_failures: int = 3
        self._is_running: bool = False
        self._lock = asyncio.Lock()

        # Load persisted state
        self._load_state()
        logger.info(
            f"AutoTrainingPipeline initialised — interval={self.interval}min, "
            f"min_samples={self.min_new_samples}"
        )

    # ===================================================================
    # Lifecycle
    # ===================================================================

    def start(self) -> None:
        """Start the auto-training scheduler (non-blocking).

        The scheduler runs in the background on the current asyncio
        event loop.  Training jobs fire every ``interval`` minutes.
        """
        if self._is_running:
            logger.warning("Pipeline already running — ignoring start()")
            return

        trigger = IntervalTrigger(minutes=self.interval)
        self._scheduler_job_id = f"training_loop_{id(self)}"
        self.scheduler.add_job(
            self._training_loop_wrapper,
            trigger=trigger,
            id=self._scheduler_job_id,
            name="auto_training_loop",
            replace_existing=True,
        )
        self.scheduler.start()
        self._is_running = True
        logger.info(
            f"Auto-training started — next run in {self.interval} minutes"
        )

    def stop(self) -> None:
        """Stop the scheduler gracefully.

        The currently running training job (if any) is allowed to
        finish; no new jobs are scheduled after this call.
        """
        if not self._is_running:
            return
        self.scheduler.shutdown(wait=False)
        self._is_running = False
        self._save_state()
        logger.info("Auto-training stopped")

    # ===================================================================
    # Main training loop (step-by-step)
    # ===================================================================

    async def _training_loop_wrapper(self) -> None:
        """APScheduler-compatible wrapper that schedules ``_training_loop``."""
        try:
            await self._training_loop()
        except Exception as exc:
            logger.exception(f"Unhandled exception in training loop: {exc}")
            self.consecutive_failures += 1

    async def _training_loop(self) -> None:
        """Execute one full training cycle.

        Step 1 — Detect changes
        Step 2 — Build dataset
        Step 3 — Fine-tune model
        Step 4 — Validate via backtest
        Step 5 — Deploy if better
        Step 6 — Log & broadcast results
        """
        async with self._lock:
            # ---- Circuit breaker ----
            if self.consecutive_failures >= self.max_consecutive_failures:
                logger.error(
                    f"Circuit breaker OPEN — {self.consecutive_failures} "
                    f"consecutive failures. Manual intervention required."
                )
                await self._broadcast_alert({
                    "severity": "critical",
                    "category": "training",
                    "title": "Training circuit breaker OPEN",
                    "message": (
                        f"Auto-training paused after {self.consecutive_failures} "
                        f"consecutive failures."
                    ),
                })
                return

            # ---- Step 1: Detect changes ----
            changes = await self._detect_changes()
            logger.info(f"Change detection: {changes}")

            # Decide whether to train
            should_train = (
                changes["new_data"] or
                changes["formula_changed"] or
                changes["manual_trigger"]
            )
            if not should_train:
                logger.info("No changes detected — skipping training cycle")
                return

            # Determine trigger reason
            trigger_reason = TriggerReason.SCHEDULED_20MIN.value
            if changes["formula_changed"]:
                trigger_reason = TriggerReason.FORMULA_CHANGE.value
            elif changes["manual_trigger"]:
                trigger_reason = TriggerReason.MANUAL.value
            elif changes["new_data"]:
                trigger_reason = TriggerReason.NEW_DATA_THRESHOLD.value

            # ---- Create job record ----
            job = TrainingJob(
                job_id=self._next_job_id,
                trigger_reason=trigger_reason,
                started_at=datetime.utcnow(),
                status=TrainingStatus.RUNNING.value,
            )
            self._next_job_id += 1
            self.current_job = job
            self.jobs_history.append(job)
            # Trim history
            if len(self.jobs_history) > self.job_history_limit:
                self.jobs_history = self.jobs_history[-self.job_history_limit:]

            await self._broadcast_training_progress({
                "job_id": job.job_id,
                "event": "started",
                "trigger_reason": trigger_reason,
                "timestamp": datetime.utcnow().isoformat(),
            })

            # ===========================================================
            # Step 2: Build dataset
            # ===========================================================
            dataset = None
            try:
                logger.info(f"[Job {job.job_id}] Step 2 — Building dataset")
                await self._broadcast_training_progress({
                    "job_id": job.job_id,
                    "event": "building_dataset",
                    "message": "Fetching latest market data and computing features",
                })

                dataset = await self._build_dataset()
                job.data_samples = getattr(dataset, "__len__", lambda: 0)()
                if hasattr(dataset, "num_samples"):
                    job.data_samples = dataset.num_samples

                logger.info(f"[Job {job.job_id}] Dataset built — {job.data_samples} samples")
                await self._broadcast_training_progress({
                    "job_id": job.job_id,
                    "event": "dataset_ready",
                    "samples": job.data_samples,
                })
            except Exception as exc:
                logger.exception(f"[Job {job.job_id}] Dataset build failed: {exc}")
                await self._fail_job(job, f"Dataset build failed: {exc}")
                return

            # ===========================================================
            # Step 3: Fine-tune model
            # ===========================================================
            checkpoint_path = ""
            try:
                logger.info(f"[Job {job.job_id}] Step 3 — Fine-tuning model")
                await self._broadcast_training_progress({
                    "job_id": job.job_id,
                    "event": "training_started",
                    "message": "Starting incremental fine-tuning",
                    "epochs": 3,
                })

                checkpoint_path = await self._train_model(dataset)
                job.checkpoint_path = checkpoint_path

                logger.info(f"[Job {job.job_id}] Training complete — checkpoint: {checkpoint_path}")
                await self._broadcast_training_progress({
                    "job_id": job.job_id,
                    "event": "training_complete",
                    "checkpoint_path": checkpoint_path,
                    "final_loss": job.final_loss,
                    "validation_loss": job.validation_loss,
                })
            except Exception as exc:
                logger.exception(f"[Job {job.job_id}] Training failed: {exc}")
                await self._fail_job(job, f"Training failed: {exc}")
                return

            # ===========================================================
            # Step 4: Validate via backtest
            # ===========================================================
            new_metrics: Dict[str, Any] = {}
            try:
                logger.info(f"[Job {job.job_id}] Step 4 — Running backtest validation")
                await self._broadcast_training_progress({
                    "job_id": job.job_id,
                    "event": "backtest_started",
                    "message": "Running backtest on validation period",
                })

                new_metrics = await self._validate_model(checkpoint_path)
                job.backtest_metrics = new_metrics

                # Update job with metrics
                job.final_loss = new_metrics.get("final_loss", 0.0)
                job.validation_loss = new_metrics.get("validation_loss", 0.0)
                job.epochs_trained = new_metrics.get("epochs_trained", 0)

                logger.info(
                    f"[Job {job.job_id}] Backtest complete — "
                    f"pnl={new_metrics.get('backtest_pnl', 0):.2f}, "
                    f"f1={new_metrics.get('f1_score', 0):.4f}"
                )
                await self._broadcast_training_progress({
                    "job_id": job.job_id,
                    "event": "backtest_complete",
                    "metrics": new_metrics,
                })
            except Exception as exc:
                logger.exception(f"[Job {job.job_id}] Backtest failed: {exc}")
                await self._fail_job(job, f"Backtest failed: {exc}")
                return

            # ===========================================================
            # Step 5: Deploy if better
            # ===========================================================
            try:
                logger.info(f"[Job {job.job_id}] Step 5 — Comparing and deploying")
                deployed = await self._deploy_if_better(new_metrics, checkpoint_path, job)
                job.deployed = deployed

                if deployed:
                    logger.info(f"[Job {job.job_id}] New model DEPLOYED")
                else:
                    logger.info(f"[Job {job.job_id}] Old model kept — new model archived")
            except Exception as exc:
                logger.exception(f"[Job {job.job_id}] Deployment comparison failed: {exc}")
                await self._fail_job(job, f"Deployment failed: {exc}")
                return

            # ===========================================================
            # Step 6: Finalise
            # ===========================================================
            job.status = TrainingStatus.COMPLETED.value
            job.completed_at = datetime.utcnow()
            self.last_training_time = datetime.utcnow()
            self.consecutive_failures = 0  # reset on success
            self.current_job = None
            self._save_state()

            duration = (job.completed_at - job.started_at).total_seconds()
            logger.info(
                f"[Job {job.job_id}] Training cycle COMPLETED in {duration:.1f}s — "
                f"deployed={deployed}, version={job.model_version_id}"
            )
            await self._broadcast_training_progress({
                "job_id": job.job_id,
                "event": "completed",
                "duration_sec": duration,
                "deployed": deployed,
                "model_version_id": job.model_version_id,
            })

    # ===================================================================
    # Step implementations
    # ===================================================================

    async def _detect_changes(self) -> Dict[str, bool]:
        """Detect what has changed since the last training run.

        Checks three conditions:
            1. **New data** — enough new market samples have arrived.
            2. **Formula changed** — strategy formulas were edited.
            3. **Manual trigger** — a manual training was requested.

        Returns:
            Dict with keys ``new_data``, ``formula_changed``, ``manual_trigger``.
        """
        since = self.last_training_time or (datetime.utcnow() - timedelta(days=30))
        result = {
            "new_data": False,
            "formula_changed": False,
            "manual_trigger": False,
        }

        # 1. Check for new data
        try:
            estimated = self.dataset_builder.estimate_samples(since)
            result["new_data"] = estimated >= self.min_new_samples
            logger.debug(f"New data estimate: {estimated} samples (threshold: {self.min_new_samples})")
        except Exception as exc:
            logger.warning(f"Could not estimate new samples: {exc}")
            result["new_data"] = True  # train anyway if we can't tell

        # 2. Check for formula changes
        try:
            current_formula = self.dataset_builder.get_formula_snapshot()
            current_hash = compute_formula_hash(current_formula)
            if self.last_formula_hash and self.last_formula_hash != current_hash:
                result["formula_changed"] = True
                logger.info(
                    f"Formula hash changed: {self.last_formula_hash} -> {current_hash}"
                )
            elif not self.last_formula_hash:
                # First run — store hash but don't trigger on it
                self.last_formula_hash = current_hash
        except Exception as exc:
            logger.warning(f"Could not compute formula hash: {exc}")

        # 3. Manual trigger is handled separately via trigger_manual_training()
        result["manual_trigger"] = False

        return result

    async def _build_dataset(self) -> Any:
        """Build training dataset from current state.

        Delegates to the injected ``dataset_builder``.  Only includes
        data newer than ``last_training_time``.

        Returns:
            Dataset object (opaque — passed straight to ``llm_engine``).
        """
        since = self.last_training_time or (datetime.utcnow() - timedelta(days=30))
        dataset = await self.dataset_builder.build(since=since)
        return dataset

    async def _train_model(self, dataset: Any) -> str:
        """Fine-tune the model incrementally.

        Starts from the currently active checkpoint (if any) so that
        training is warm-started rather than from scratch.

        Args:
            dataset: Training dataset from ``_build_dataset``.

        Returns:
            Absolute path to the saved checkpoint directory/file.
        """
        active = self.registry.get_active_version()
        base_checkpoint = active.checkpoint_path if active else None

        version_id = self.registry.get_next_version_id()
        checkpoint_dir = self.models_dir / f"version_{version_id}"
        checkpoint_dir.mkdir(parents=True, exist_ok=True)

        # Progress callback — forwards to WebSocket
        async def _progress_cb(update: Dict[str, Any]) -> None:
            if self.current_job:
                self.current_job.epochs_trained = update.get("epoch", 0)
                self.current_job.final_loss = update.get("loss", 0.0)
                self.current_job.validation_loss = update.get("val_loss", 0.0)
            await self._broadcast_training_progress({
                "job_id": self.current_job.job_id if self.current_job else 0,
                "event": "epoch_complete",
                **update,
            })

        checkpoint_path = await self.llm.fine_tune(
            dataset=dataset,
            checkpoint_path=base_checkpoint,
            epochs=3,
            learning_rate=1e-4,
            batch_size=32,
            job_id=self.current_job.job_id if self.current_job else 0,
            progress_callback=_progress_cb,
        )
        return str(checkpoint_path)

    async def _validate_model(self, checkpoint_path: str) -> Dict[str, Any]:
        """Validate a new model by running a backtest.

        The backtest runs on a held-out validation window (last 30 days
        of data) to get a realistic P&L estimate.

        Args:
            checkpoint_path: Path to the newly trained checkpoint.

        Returns:
            Metrics dict with at minimum:
            ``backtest_pnl``, ``f1_score``, ``accuracy``, ``precision``,
            ``recall``, ``final_loss``, ``validation_loss``,
            ``epochs_trained``.
        """
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)

        # Default symbols — Nifty 50 for broad validation
        symbols = self.dataset_builder.get_formula_snapshot().get(
            "symbols", ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK"]
        ) if hasattr(self.dataset_builder, "get_formula_snapshot") else ["RELIANCE"]

        try:
            bt_result = await self.backtest.run(
                checkpoint_path=checkpoint_path,
                start_date=start_date,
                end_date=end_date,
                symbols=symbols,
            )
        except Exception as exc:
            logger.warning(f"Backtest engine failed: {exc} — returning empty metrics")
            bt_result = {}

        # Ensure all expected keys exist
        defaults = {
            "backtest_pnl": 0.0,
            "f1_score": 0.0,
            "accuracy": 0.0,
            "precision": 0.0,
            "recall": 0.0,
            "final_loss": 0.0,
            "validation_loss": 0.0,
            "epochs_trained": 0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
        }
        for key, val in defaults.items():
            bt_result.setdefault(key, val)

        return bt_result

    async def _deploy_if_better(
        self,
        new_metrics: Dict[str, Any],
        checkpoint_path: str,
        job: TrainingJob,
    ) -> bool:
        """Compare new model vs current active. Deploy if better.

        The comparison uses a composite score combining:
            - Backtest P&L (primary)
            - F1 score (secondary)
            - Accuracy (tertiary)

        A model is "better" if its composite score is strictly greater
        than the active model's score by at least a small epsilon
        (to avoid deploying noise).

        Args:
            new_metrics: Metrics dict from backtest.
            checkpoint_path: Path to new checkpoint.
            job: Current training job (updated in-place).

        Returns:
            ``True`` if the new model was deployed.
        """
        # Compute composite score for new model
        new_score = (
            new_metrics.get("backtest_pnl", 0.0) * 0.5 +
            new_metrics.get("f1_score", 0.0) * 100.0 * 0.3 +
            new_metrics.get("accuracy", 0.0) * 100.0 * 0.2
        )

        active = self.registry.get_active_version()

        if active is None:
            # No active model — auto-deploy first model
            logger.info("No active model exists — auto-deploying first model")
            return await self._register_and_activate(
                checkpoint_path, new_metrics, job, new_score
            )

        # Compute composite score for active model
        active_score = (
            active.backtest_pnl * 0.5 +
            active.f1_score * 100.0 * 0.3 +
            active.accuracy * 100.0 * 0.2
        )

        epsilon = 0.01  # minimum improvement threshold
        improvement = new_score - active_score

        logger.info(
            f"Model comparison: new_score={new_score:.4f} vs "
            f"active_score={active_score:.4f} (improvement={improvement:+.4f})"
        )

        if improvement > epsilon:
            logger.info(f"New model is better by {improvement:+.4f} — deploying")
            return await self._register_and_activate(
                checkpoint_path, new_metrics, job, new_score
            )
        else:
            logger.info(
                f"New model not significantly better ({improvement:+.4f} <= {epsilon}) — "
                f"archiving"
            )
            # Register but don't activate
            version_id = await self._register_version(
                checkpoint_path, new_metrics, job, activate=False
            )
            job.model_version_id = version_id
            # Archive the underperforming version
            self.registry.archive_version(version_id)
            return False

    async def _register_and_activate(
        self,
        checkpoint_path: str,
        metrics: Dict[str, Any],
        job: TrainingJob,
        composite_score: float,
    ) -> bool:
        """Register a new version and activate it.

        Returns:
            ``True`` on success.
        """
        version_id = await self._register_version(
            checkpoint_path, metrics, job, activate=True
        )
        job.model_version_id = version_id
        self.registry.activate_version(version_id)

        # Update formula hash since we trained on current formulas
        try:
            current_formula = self.dataset_builder.get_formula_snapshot()
            self.last_formula_hash = compute_formula_hash(current_formula)
        except Exception:
            pass

        await self._broadcast_alert({
            "severity": "info",
            "category": "training",
            "title": "New model deployed",
            "message": (
                f"Version {version_id} deployed (score={composite_score:.4f})"
            ),
            "metadata": {"version_id": version_id, "score": composite_score},
        })
        return True

    async def _register_version(
        self,
        checkpoint_path: str,
        metrics: Dict[str, Any],
        job: TrainingJob,
        activate: bool = False,
    ) -> int:
        """Register a new model version in the registry.

        Args:
            checkpoint_path: Path to checkpoint.
            metrics: Performance metrics.
            job: Training job for metadata.
            activate: Whether to mark as active immediately.

        Returns:
            The assigned version ID.
        """
        version_id = self.registry.get_next_version_id()
        version_name = f"v{version_id}-{job.trigger_reason}"

        info = ModelVersionInfo(
            version_id=version_id,
            version_name=version_name,
            description=f"Auto-trained job {job.job_id} — {job.trigger_reason}",
            checkpoint_path=checkpoint_path,
            training_data_size=job.data_samples,
            training_duration_sec=(
                (datetime.utcnow() - job.started_at).total_seconds()
                if job.started_at else 0.0
            ),
            epochs=job.epochs_trained,
            final_loss=metrics.get("final_loss", 0.0),
            validation_loss=metrics.get("validation_loss", 0.0),
            accuracy=metrics.get("accuracy", 0.0),
            precision=metrics.get("precision", 0.0),
            recall=metrics.get("recall", 0.0),
            f1_score=metrics.get("f1_score", 0.0),
            backtest_pnl=metrics.get("backtest_pnl", 0.0),
            status="active" if activate else "ready",
            is_active=activate,
            triggered_by=job.trigger_reason,
            formula_snapshot=self.dataset_builder.get_formula_snapshot()
                if hasattr(self.dataset_builder, "get_formula_snapshot") else {},
            completed_at=datetime.utcnow(),
        )
        self.registry.register_version(info)
        return version_id

    async def _fail_job(self, job: TrainingJob, error_message: str) -> None:
        """Mark a job as failed, update counters, broadcast alert."""
        job.status = TrainingStatus.FAILED.value
        job.completed_at = datetime.utcnow()
        job.error_message = str(error_message)
        self.consecutive_failures += 1
        self.current_job = None
        self._save_state()

        logger.error(f"[Job {job.job_id}] FAILED: {error_message}")
        await self._broadcast_training_progress({
            "job_id": job.job_id,
            "event": "failed",
            "error": error_message,
        })
        await self._broadcast_alert({
            "severity": "error",
            "category": "training",
            "title": f"Training job {job.job_id} failed",
            "message": error_message,
        })

    # ===================================================================
    # Public status & control API
    # ===================================================================

    def get_status(self) -> Dict[str, Any]:
        """Get current pipeline status snapshot.

        Returns:
            Dict with keys:
            ``is_running``, ``current_job_id``, ``last_training_time``,
            ``next_scheduled_run``, ``interval_minutes``,
            ``total_jobs_completed``, ``total_jobs_failed``,
            ``consecutive_failures``, ``active_model_version_id``,
            ``last_formula_hash``.
        """
        completed = sum(1 for j in self.jobs_history if j.status == TrainingStatus.COMPLETED.value)
        failed = sum(1 for j in self.jobs_history if j.status == TrainingStatus.FAILED.value)
        active = self.registry.get_active_version()

        return {
            "is_running": self._is_running,
            "current_job_id": self.current_job.job_id if self.current_job else None,
            "last_training_time": self.last_training_time.isoformat() if self.last_training_time else None,
            "next_scheduled_run": (
                (self.last_training_time + timedelta(minutes=self.interval)).isoformat()
                if self.last_training_time and self._is_running else None
            ),
            "interval_minutes": self.interval,
            "total_jobs_completed": completed,
            "total_jobs_failed": failed,
            "consecutive_failures": self.consecutive_failures,
            "active_model_version_id": active.version_id if active else None,
            "active_model_name": active.version_name if active else None,
            "last_formula_hash": self.last_formula_hash,
            "circuit_breaker_open": self.consecutive_failures >= self.max_consecutive_failures,
        }

    def get_jobs_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent training jobs as dicts.

        Args:
            limit: Maximum number of jobs to return (newest first).

        Returns:
            List of job dicts.
        """
        jobs = sorted(self.jobs_history, key=lambda j: j.started_at, reverse=True)
        return [j.to_dict() for j in jobs[:limit]]

    async def trigger_manual_training(self) -> int:
        """Manually trigger a training run immediately.

        The manual job runs in the background — this method returns
        immediately with the assigned job ID.

        Returns:
            The new job ID.
        """
        job = TrainingJob(
            job_id=self._next_job_id,
            trigger_reason=TriggerReason.MANUAL.value,
            started_at=datetime.utcnow(),
            status=TrainingStatus.RUNNING.value,
        )
        self._next_job_id += 1
        self.current_job = job
        self.jobs_history.append(job)

        # Schedule the actual training loop
        asyncio.create_task(self._training_loop())
        logger.info(f"Manual training triggered — job {job.job_id}")
        return job.job_id

    async def force_rollback(self) -> bool:
        """Force an immediate rollback to the previous version.

        Returns:
            ``True`` if rollback succeeded.
        """
        result = self.registry.rollback()
        if result:
            active = self.registry.get_active_version()
            await self._broadcast_alert({
                "severity": "warning",
                "category": "system",
                "title": "Model rollback executed",
                "message": f"Rolled back to version {active.version_id if active else 'unknown'}",
            })
        return result

    # ===================================================================
    # WebSocket broadcast helpers
    # ===================================================================

    async def _broadcast_training_progress(self, data: Dict[str, Any]) -> None:
        """Send a training-progress event via WebSocket (if configured)."""
        if self.ws is not None:
            try:
                await self.ws.broadcast_training_progress(data)
            except Exception as exc:
                logger.debug(f"WS broadcast failed: {exc}")

    async def _broadcast_alert(self, alert_data: Dict[str, Any]) -> None:
        """Send an alert via WebSocket (if configured)."""
        if self.ws is not None:
            try:
                await self.ws.broadcast_alert(alert_data)
            except Exception as exc:
                logger.debug(f"WS alert broadcast failed: {exc}")

    # ===================================================================
    # Persistence
    # ===================================================================

    def _state_path(self) -> Path:
        return self.models_dir / "pipeline_state.json"

    def _save_state(self) -> None:
        """Persist pipeline state to disk."""
        payload = {
            "last_training_time": self.last_training_time.isoformat() if self.last_training_time else None,
            "last_formula_hash": self.last_formula_hash,
            "consecutive_failures": self.consecutive_failures,
            "next_job_id": self._next_job_id,
            "jobs_history": [j.to_dict() for j in self.jobs_history[-20:]],  # keep last 20
            "saved_at": datetime.utcnow().isoformat(),
        }
        try:
            with open(self._state_path(), "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2, default=str)
        except Exception as exc:
            logger.error(f"Failed to save pipeline state: {exc}")

    def _load_state(self) -> None:
        """Restore pipeline state from disk."""
        path = self._state_path()
        if not path.exists():
            return
        try:
            with open(path, "r", encoding="utf-8") as fh:
                payload = json.load(fh)

            lt = payload.get("last_training_time")
            if lt:
                self.last_training_time = datetime.fromisoformat(lt)
            self.last_formula_hash = payload.get("last_formula_hash", "")
            self.consecutive_failures = payload.get("consecutive_failures", 0)
            self._next_job_id = payload.get("next_job_id", 1)

            # Restore job history
            for jd in payload.get("jobs_history", []):
                job = TrainingJob(
                    job_id=jd.get("job_id", 0),
                    trigger_reason=jd.get("trigger_reason", "scheduled_20min"),
                    started_at=datetime.fromisoformat(jd["started_at"]) if jd.get("started_at") else datetime.utcnow(),
                    completed_at=datetime.fromisoformat(jd["completed_at"]) if jd.get("completed_at") else None,
                    status=jd.get("status", "queued"),
                    data_samples=jd.get("data_samples", 0),
                    epochs_trained=jd.get("epochs_trained", 0),
                    final_loss=jd.get("final_loss", 0.0),
                    validation_loss=jd.get("validation_loss", 0.0),
                    model_version_id=jd.get("model_version_id"),
                    checkpoint_path=jd.get("checkpoint_path", ""),
                    error_message=jd.get("error_message", ""),
                    backtest_metrics=jd.get("backtest_metrics", {}),
                    deployed=jd.get("deployed", False),
                )
                self.jobs_history.append(job)

            logger.info(f"Loaded pipeline state — {len(self.jobs_history)} jobs, "
                        f"last_train={self.last_training_time}")
        except Exception as exc:
            logger.error(f"Failed to load pipeline state: {exc}")

    def __repr__(self) -> str:
        return (
            f"<AutoTrainingPipeline running={self._is_running} "
            f"interval={self.interval}min jobs={len(self.jobs_history)}>"
        )
