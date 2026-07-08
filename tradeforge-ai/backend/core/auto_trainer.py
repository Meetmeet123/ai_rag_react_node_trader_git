"""
Auto-Training Pipeline — Decoupled Celery Worker Implementation

The pipeline logic is shared between the API process and Celery workers.
State is persisted in MongoDB via the ``TrainingPipelineState`` singleton
document; job history is stored in ``TrainingLog`` documents.

Scheduled execution is handled by Celery beat (see ``celery_app.py`` and
``tasks/training.py``).  The API process can start/stop the scheduler flag
and trigger manual runs, but it no longer runs the training loop itself.

Lifecycle of one cycle (``run_single_cycle``):
    1. **Detect changes** — new market data or strategy-formula changes.
    2. **Build dataset** — fetches latest data and assembles splits.
    3. **Fine-tune model** — incremental training from the active checkpoint.
    4. **Validate** — backtest on held-out data for trading performance.
    5. **Deploy if better** — activate the new model only if it wins.
    6. **Log & broadcast** — update the ``TrainingLog`` doc and emit WS events.

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
    >>> await pipeline.initialize()
    >>> await pipeline.start()   # sets the DB "is_running" flag
    >>> # Celery beat fires run_training_cycle every N minutes
    >>> await pipeline.stop()    # clears the DB flag
"""

from __future__ import annotations

import asyncio
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

from loguru import logger

from core.artifact_store import ArtifactStore
from core.drift_detector import DriftDetector
from core.metrics import (
    ACTIVE_MODEL_VERSION,
    BACKTEST_PNL,
    DRIFT_DETECTED,
    TRAINING_DURATION,
    TRAINING_JOBS_TOTAL,
)
from core.model_registry import ModelRegistry, ModelVersionInfo, compute_formula_hash
from database.models import TrainingLog, TrainingPipelineState

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
        for key in ("started_at", "completed_at"):
            val = d.get(key)
            if isinstance(val, datetime):
                d[key] = val.isoformat()
        return d


# ---------------------------------------------------------------------------
# Main pipeline class
# ---------------------------------------------------------------------------


class AutoTrainingPipeline:
    """Automated training pipeline whose cycles are executed by Celery workers.

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
        llm_engine: Any,  # LLMEngineProtocol
        backtest_engine: Any,  # BacktestEngineProtocol
        model_registry: ModelRegistry,
        dataset_builder: Any,  # DatasetBuilderProtocol
        training_interval_minutes: int = 20,
        min_new_samples: int = 50,
        ws_server: Optional[Any] = None,
        job_history_limit: int = 100,
        models_dir: str = "./models",
        artifact_store: Optional[ArtifactStore] = None,
        drift_detector: Optional[DriftDetector] = None,
        shadow_mode: bool = False,
    ) -> None:
        # Dependencies (injected)
        self.llm = llm_engine
        self.backtest = backtest_engine
        self.registry = model_registry
        self.dataset_builder = dataset_builder
        self.ws = ws_server  # optional WebSocket server for broadcasts
        self.artifact_store = artifact_store
        self.drift_detector = drift_detector
        self.shadow_mode = shadow_mode

        # Configuration
        self.interval: int = training_interval_minutes
        self.min_new_samples: int = min_new_samples
        self.job_history_limit: int = job_history_limit
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)

        # Job tracking
        self.current_job: Optional[TrainingJob] = None

        # State tracking
        self.last_training_time: Optional[datetime] = None
        self.last_formula_hash: str = ""
        self.consecutive_failures: int = 0
        self.max_consecutive_failures: int = 3
        self._next_job_id: int = 1
        self._is_running: bool = False
        self._lock = asyncio.Lock()

        # MongoDB-backed singleton state document.  Loaded by ``initialize()``.
        self._state_doc: Optional[TrainingPipelineState] = None

        logger.info(
            f"AutoTrainingPipeline initialised — interval={self.interval}min, "
            f"min_samples={self.min_new_samples}"
        )

    # ===================================================================
    # Lifecycle
    # ===================================================================

    async def initialize(self) -> None:
        """Load or create the shared ``TrainingPipelineState`` document."""
        await self._load_state()
        logger.info("AutoTrainingPipeline state loaded from DB")

    async def start(self) -> None:
        """Enable the auto-training scheduler flag in DB.

        Actual scheduled execution is handled by Celery beat.
        """
        if self._is_running:
            logger.warning("Pipeline already running — ignoring start()")
            return

        self._is_running = True
        await self._save_state()
        logger.info(
            f"Auto-training enabled — Celery beat will run every {self.interval} minutes"
        )

    async def stop(self) -> None:
        """Disable the auto-training scheduler flag in DB.

        A running worker job (if any) is allowed to finish; no new jobs
        are scheduled after this call.
        """
        if not self._is_running:
            return
        self._is_running = False
        await self._save_state()
        logger.info("Auto-training disabled")

    # ===================================================================
    # Main training cycle
    # ===================================================================

    async def _training_loop_wrapper(self) -> None:
        """Backwards-compatible wrapper around ``run_single_cycle``."""
        try:
            await self.run_single_cycle()
        except Exception as exc:
            logger.exception(f"Unhandled exception in training loop: {exc}")
            self.consecutive_failures += 1
            await self._save_state()

    async def _training_loop(self) -> Optional[TrainingJob]:
        """Backwards-compatible delegate to ``run_single_cycle``."""
        return await self.run_single_cycle()

    async def run_single_cycle(
        self,
        trigger_reason: str = TriggerReason.SCHEDULED_20MIN.value,
        manual: bool = False,
        job_id: Optional[int] = None,
    ) -> Optional[TrainingJob]:
        """Execute one full training cycle.

        Step 1 — Detect changes
        Step 2 — Build dataset
        Step 3 — Fine-tune model
        Step 4 — Validate via backtest
        Step 5 — Deploy if better
        Step 6 — Log & broadcast results

        Args:
            trigger_reason: Reason string stored on the job record.
            manual: If True, run even when no changes are detected.
            job_id: Optional pre-reserved job ID.  If omitted, the next
                available ID from the shared state is used.

        Returns:
            The completed ``TrainingJob`` or ``None`` if skipped.
        """
        async with self._lock:
            await self._load_state()

            # ---- Circuit breaker ----
            if self.consecutive_failures >= self.max_consecutive_failures:
                logger.error(
                    f"Circuit breaker OPEN — {self.consecutive_failures} "
                    f"consecutive failures. Manual intervention required."
                )
                await self._broadcast_alert(
                    {
                        "severity": "critical",
                        "category": "training",
                        "title": "Training circuit breaker OPEN",
                        "message": (
                            f"Auto-training paused after {self.consecutive_failures} "
                            f"consecutive failures."
                        ),
                    }
                )
                return None

            # ---- Step 1: Detect changes ----
            if not manual:
                changes = await self._detect_changes()
                logger.info(f"Change detection: {changes}")

                should_train = (
                    changes["new_data"]
                    or changes["formula_changed"]
                    or changes["drift_detected"]
                )
                if not should_train:
                    logger.info("No changes detected — skipping training cycle")
                    return None

                if changes["formula_changed"]:
                    trigger_reason = TriggerReason.FORMULA_CHANGE.value
                elif changes["drift_detected"]:
                    trigger_reason = TriggerReason.NEW_DATA_THRESHOLD.value
                elif changes["new_data"]:
                    trigger_reason = TriggerReason.NEW_DATA_THRESHOLD.value

            # ---- Create job record ----
            actual_job_id = job_id or self._next_job_id
            if job_id is None:
                self._next_job_id += 1
            else:
                # Reserved IDs may be ahead of the counter; keep it monotonic.
                self._next_job_id = max(self._next_job_id, actual_job_id + 1)

            log_doc = await TrainingLog.find_one(TrainingLog.job_id == actual_job_id)
            if log_doc is None:
                log_doc = TrainingLog(
                    job_id=actual_job_id,
                    trigger_reason=trigger_reason,
                    status=TrainingStatus.RUNNING.value,
                )
                await log_doc.insert()
            else:
                log_doc.status = TrainingStatus.RUNNING.value
                log_doc.trigger_reason = trigger_reason
                await log_doc.save()

            job = TrainingJob(
                job_id=actual_job_id,
                trigger_reason=trigger_reason,
                started_at=log_doc.started_at or datetime.utcnow(),
                status=TrainingStatus.RUNNING.value,
            )
            self.current_job = job

            await self._broadcast_training_progress(
                {
                    "job_id": job.job_id,
                    "event": "started",
                    "trigger_reason": trigger_reason,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

            # ===========================================================
            # Step 2: Build dataset
            # ===========================================================
            dataset = None
            try:
                logger.info(f"[Job {job.job_id}] Step 2 — Building dataset")
                await self._broadcast_training_progress(
                    {
                        "job_id": job.job_id,
                        "event": "building_dataset",
                        "message": "Fetching latest market data and computing features",
                    }
                )

                dataset = await self._build_dataset()
                job.data_samples = getattr(dataset, "__len__", lambda: 0)()
                if hasattr(dataset, "num_samples"):
                    job.data_samples = dataset.num_samples

                log_doc.data_samples = job.data_samples
                await log_doc.save()

                logger.info(
                    f"[Job {job.job_id}] Dataset built — {job.data_samples} samples"
                )
                await self._broadcast_training_progress(
                    {
                        "job_id": job.job_id,
                        "event": "dataset_ready",
                        "samples": job.data_samples,
                    }
                )
            except Exception as exc:
                logger.exception(f"[Job {job.job_id}] Dataset build failed: {exc}")
                await self._fail_job(job, log_doc, f"Dataset build failed: {exc}")
                return job

            # ===========================================================
            # Step 3: Fine-tune model
            # ===========================================================
            checkpoint_path = ""
            try:
                logger.info(f"[Job {job.job_id}] Step 3 — Fine-tuning model")
                await self._broadcast_training_progress(
                    {
                        "job_id": job.job_id,
                        "event": "training_started",
                        "message": "Starting incremental fine-tuning",
                        "epochs": 3,
                    }
                )

                checkpoint_path = await self._train_model(dataset)
                job.checkpoint_path = checkpoint_path
                log_doc.checkpoint_path = checkpoint_path
                await log_doc.save()

                logger.info(
                    f"[Job {job.job_id}] Training complete — checkpoint: {checkpoint_path}"
                )
                await self._broadcast_training_progress(
                    {
                        "job_id": job.job_id,
                        "event": "training_complete",
                        "checkpoint_path": checkpoint_path,
                        "final_loss": job.final_loss,
                        "validation_loss": job.validation_loss,
                    }
                )
            except Exception as exc:
                logger.exception(f"[Job {job.job_id}] Training failed: {exc}")
                await self._fail_job(job, log_doc, f"Training failed: {exc}")
                return job

            # ===========================================================
            # Step 4: Validate via backtest
            # ===========================================================
            new_metrics: Dict[str, Any] = {}
            try:
                logger.info(f"[Job {job.job_id}] Step 4 — Running backtest validation")
                await self._broadcast_training_progress(
                    {
                        "job_id": job.job_id,
                        "event": "backtest_started",
                        "message": "Running backtest on validation period",
                    }
                )

                new_metrics = await self._validate_model(checkpoint_path)
                job.backtest_metrics = new_metrics
                job.final_loss = new_metrics.get("final_loss", 0.0)
                job.validation_loss = new_metrics.get("validation_loss", 0.0)
                job.epochs_trained = new_metrics.get("epochs_trained", 0)

                log_doc.backtest_metrics = new_metrics
                log_doc.final_loss = job.final_loss
                log_doc.validation_loss = job.validation_loss
                log_doc.epochs = job.epochs_trained
                await log_doc.save()

                logger.info(
                    f"[Job {job.job_id}] Backtest complete — "
                    f"pnl={new_metrics.get('backtest_pnl', 0):.2f}, "
                    f"f1={new_metrics.get('f1_score', 0):.4f}"
                )
                await self._broadcast_training_progress(
                    {
                        "job_id": job.job_id,
                        "event": "backtest_complete",
                        "metrics": new_metrics,
                    }
                )
            except Exception as exc:
                logger.exception(f"[Job {job.job_id}] Backtest failed: {exc}")
                await self._fail_job(job, log_doc, f"Backtest failed: {exc}")
                return job

            # ===========================================================
            # Step 5: Deploy if better
            # ===========================================================
            try:
                logger.info(f"[Job {job.job_id}] Step 5 — Comparing and deploying")
                deployed = await self._deploy_if_better(
                    new_metrics, checkpoint_path, job, log_doc
                )
                job.deployed = deployed
                log_doc.deployed = deployed
                await log_doc.save()

                if deployed:
                    logger.info(f"[Job {job.job_id}] New model DEPLOYED")
                else:
                    logger.info(
                        f"[Job {job.job_id}] Old model kept — new model archived"
                    )
            except Exception as exc:
                logger.exception(
                    f"[Job {job.job_id}] Deployment comparison failed: {exc}"
                )
                await self._fail_job(job, log_doc, f"Deployment failed: {exc}")
                return job

            # ===========================================================
            # Step 6: Finalise
            # ===========================================================
            job.status = TrainingStatus.COMPLETED.value
            job.completed_at = datetime.utcnow()

            log_doc.status = TrainingStatus.COMPLETED.value
            log_doc.completed_at = job.completed_at
            await log_doc.save()

            self.last_training_time = datetime.utcnow()
            self.consecutive_failures = 0
            self.current_job = None
            await self._save_state()

            duration = (job.completed_at - job.started_at).total_seconds()
            TRAINING_JOBS_TOTAL.labels(status="completed").inc()
            TRAINING_DURATION.observe(duration)
            if job.model_version_id is not None:
                ACTIVE_MODEL_VERSION.set(job.model_version_id)
            BACKTEST_PNL.set(new_metrics.get("backtest_pnl", 0.0))

            logger.info(
                f"[Job {job.job_id}] Training cycle COMPLETED in {duration:.1f}s — "
                f"deployed={deployed}, version={job.model_version_id}"
            )
            await self._broadcast_training_progress(
                {
                    "job_id": job.job_id,
                    "event": "completed",
                    "duration_sec": duration,
                    "deployed": deployed,
                    "model_version_id": job.model_version_id,
                }
            )

            return job

    # ===================================================================
    # Step implementations
    # ===================================================================

    async def _detect_changes(self) -> Dict[str, bool]:
        """Detect what has changed since the last training run.

        Checks three conditions:
            1. **New data** — enough new market samples have arrived.
            2. **Formula changed** — strategy formulas were edited.
            3. **Distribution drift** — market feature distributions shifted.

        Returns:
            Dict with keys ``new_data``, ``formula_changed``, ``drift_detected``.
        """
        since = self.last_training_time or (datetime.utcnow() - timedelta(days=30))
        result = {
            "new_data": False,
            "formula_changed": False,
            "drift_detected": False,
        }

        # 1. Check for new data
        try:
            estimated = self.dataset_builder.estimate_samples(since)
            result["new_data"] = estimated >= self.min_new_samples
            logger.debug(
                f"New data estimate: {estimated} samples (threshold: {self.min_new_samples})"
            )
        except Exception as exc:
            logger.warning(f"Could not estimate new samples: {exc}")
            result["new_data"] = True

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
                self.last_formula_hash = current_hash
                await self._save_state()
        except Exception as exc:
            logger.warning(f"Could not compute formula hash: {exc}")

        # 3. Check for distribution drift against active model reference
        try:
            active = self.registry.get_active_version()
            if (
                self.drift_detector is not None
                and active is not None
                and active.reference_distributions
            ):
                current_dist = self.dataset_builder.get_feature_distributions(since)
                drift_result = self.drift_detector.check(
                    active.reference_distributions, current_dist
                )
                result["drift_detected"] = bool(
                    drift_result.get("drift_detected", False)
                )
                DRIFT_DETECTED.set(1.0 if result["drift_detected"] else 0.0)
                if result["drift_detected"]:
                    logger.info(
                        f"Distribution drift detected against version {active.version_id}"
                    )
        except Exception as exc:
            logger.warning(f"Could not run drift detection: {exc}")

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

        async def _progress_cb(update: Dict[str, Any]) -> None:
            if self.current_job:
                self.current_job.epochs_trained = update.get("epoch", 0)
                self.current_job.final_loss = update.get("loss", 0.0)
                self.current_job.validation_loss = update.get("val_loss", 0.0)
            await self._broadcast_training_progress(
                {
                    "job_id": self.current_job.job_id if self.current_job else 0,
                    "event": "epoch_complete",
                    **update,
                }
            )

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

        symbols = ["RELIANCE"]
        if hasattr(self.dataset_builder, "get_formula_snapshot"):
            try:
                symbols = self.dataset_builder.get_formula_snapshot().get(
                    "symbols", ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK"]
                )
            except Exception as exc:
                logger.warning(f"Could not read symbols from formula snapshot: {exc}")

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
        log_doc: TrainingLog,
    ) -> bool:
        """Compare new model vs current active. Deploy if better.

        The comparison uses a composite score combining backtest P&L,
        F1 score, and accuracy.  A model is "better" if its composite
        score exceeds the active model's by at least a small epsilon.

        Args:
            new_metrics: Metrics dict from backtest.
            checkpoint_path: Path to new checkpoint.
            job: Current training job (updated in-place).
            log_doc: Persisted ``TrainingLog`` document.

        Returns:
            ``True`` if the new model was deployed.
        """
        new_score = (
            new_metrics.get("backtest_pnl", 0.0) * 0.5
            + new_metrics.get("f1_score", 0.0) * 100.0 * 0.3
            + new_metrics.get("accuracy", 0.0) * 100.0 * 0.2
        )

        active = self.registry.get_active_version()

        if active is None:
            logger.info("No active model exists — auto-deploying first model")
            return await self._register_and_activate(
                checkpoint_path, new_metrics, job, log_doc, new_score
            )

        active_score = (
            active.backtest_pnl * 0.5
            + active.f1_score * 100.0 * 0.3
            + active.accuracy * 100.0 * 0.2
        )

        epsilon = 0.01
        improvement = new_score - active_score

        logger.info(
            f"Model comparison: new_score={new_score:.4f} vs "
            f"active_score={active_score:.4f} (improvement={improvement:+.4f})"
        )

        if improvement > epsilon:
            logger.info(f"New model is better by {improvement:+.4f} — deploying")
            return await self._register_and_activate(
                checkpoint_path, new_metrics, job, log_doc, new_score
            )

        logger.info(
            f"New model not significantly better ({improvement:+.4f} <= {epsilon}) — "
            f"archiving"
        )
        version_id = await self._register_version(
            checkpoint_path, new_metrics, job, log_doc, activate=False
        )
        job.model_version_id = version_id
        self.registry.archive_version(version_id)
        return False

    async def _register_and_activate(
        self,
        checkpoint_path: str,
        metrics: Dict[str, Any],
        job: TrainingJob,
        log_doc: TrainingLog,
        composite_score: float,
    ) -> bool:
        """Register a new version and activate it.

        Returns:
            ``True`` on success.
        """
        version_id = await self._register_version(
            checkpoint_path, metrics, job, log_doc, activate=True
        )
        job.model_version_id = version_id
        self.registry.activate_version(version_id)

        try:
            current_formula = self.dataset_builder.get_formula_snapshot()
            self.last_formula_hash = compute_formula_hash(current_formula)
        except Exception:
            pass

        await self._broadcast_alert(
            {
                "severity": "info",
                "category": "training",
                "title": "New model deployed",
                "message": (
                    f"Version {version_id} deployed (score={composite_score:.4f})"
                ),
                "metadata": {"version_id": version_id, "score": composite_score},
            }
        )
        return True

    async def _register_version(
        self,
        checkpoint_path: str,
        metrics: Dict[str, Any],
        job: TrainingJob,
        log_doc: TrainingLog,
        activate: bool = False,
    ) -> int:
        """Register a new model version in the registry.

        Args:
            checkpoint_path: Path to checkpoint.
            metrics: Performance metrics.
            job: Training job for metadata.
            log_doc: Persisted ``TrainingLog`` document.
            activate: Whether to mark as active immediately.

        Returns:
            The assigned version ID.
        """
        version_id = self.registry.get_next_version_id()
        version_name = f"v{version_id}-{job.trigger_reason}"

        # Capture reference distributions for future drift detection.
        reference_distributions: Dict[str, List[float]] = {}
        try:
            if hasattr(self.dataset_builder, "get_feature_distributions"):
                reference_distributions = (
                    self.dataset_builder.get_feature_distributions(
                        self.last_training_time
                    )
                )
        except Exception as exc:
            logger.warning(f"Could not capture reference distributions: {exc}")

        # Upload checkpoint artifact to S3/MinIO if configured.
        artifact_uri: Optional[str] = None
        if self.artifact_store is not None:
            try:
                artifact_uri = self.artifact_store.upload_checkpoint(
                    checkpoint_path, version_id
                )
            except Exception as exc:
                logger.warning(f"Artifact upload failed: {exc}")

        info = ModelVersionInfo(
            version_id=version_id,
            version_name=version_name,
            description=f"Auto-trained job {job.job_id} — {job.trigger_reason}",
            checkpoint_path=checkpoint_path,
            training_data_size=job.data_samples,
            training_duration_sec=(
                (datetime.utcnow() - job.started_at).total_seconds()
                if job.started_at
                else 0.0
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
            is_shadow=False,
            triggered_by=job.trigger_reason,
            formula_snapshot=(
                self.dataset_builder.get_formula_snapshot()
                if hasattr(self.dataset_builder, "get_formula_snapshot")
                else {}
            ),
            reference_distributions=reference_distributions,
            artifact_uri=artifact_uri,
            completed_at=datetime.utcnow(),
        )
        self.registry.register_version(info)

        # In shadow mode the new model is registered as challenger, not activated.
        if self.shadow_mode and not activate:
            self.registry.set_shadow_version(version_id)
            logger.info(
                f"[Job {job.job_id}] New version {version_id} registered as shadow"
            )

        job.model_version_id = version_id
        log_doc.version_id = version_id
        await log_doc.save()
        return version_id

    async def _fail_job(
        self,
        job: TrainingJob,
        log_doc: TrainingLog,
        error_message: str,
    ) -> None:
        """Mark a job as failed, update counters, broadcast alert."""
        now = datetime.utcnow()
        job.status = TrainingStatus.FAILED.value
        job.completed_at = now
        job.error_message = str(error_message)

        log_doc.status = TrainingStatus.FAILED.value
        log_doc.completed_at = now
        log_doc.error_message = job.error_message
        await log_doc.save()

        self.consecutive_failures += 1
        self.current_job = None
        await self._save_state()

        TRAINING_JOBS_TOTAL.labels(status="failed").inc()

        logger.error(f"[Job {job.job_id}] FAILED: {error_message}")
        await self._broadcast_training_progress(
            {
                "job_id": job.job_id,
                "event": "failed",
                "error": error_message,
            }
        )
        await self._broadcast_alert(
            {
                "severity": "error",
                "category": "training",
                "title": f"Training job {job.job_id} failed",
                "message": error_message,
            }
        )

    # ===================================================================
    # Public status & control API
    # ===================================================================

    async def get_status(self) -> Dict[str, Any]:
        """Get current pipeline status snapshot from DB.

        Returns:
            Dict with keys:
            ``is_running``, ``current_job_id``, ``last_training_time``,
            ``next_scheduled_run``, ``interval_minutes``,
            ``total_jobs_completed``, ``total_jobs_failed``,
            ``consecutive_failures``, ``active_model_version_id``,
            ``active_model_name``, ``last_formula_hash``,
            ``circuit_breaker_open``.
        """
        await self._load_state()
        completed = await TrainingLog.find(
            TrainingLog.status == TrainingStatus.COMPLETED.value
        ).count()
        failed = await TrainingLog.find(
            TrainingLog.status == TrainingStatus.FAILED.value
        ).count()
        active = self.registry.get_active_version()

        return {
            "is_running": self._is_running,
            "current_job_id": self.current_job.job_id if self.current_job else None,
            "last_training_time": (
                self.last_training_time.isoformat() if self.last_training_time else None
            ),
            "next_scheduled_run": (
                (self.last_training_time + timedelta(minutes=self.interval)).isoformat()
                if self.last_training_time and self._is_running
                else None
            ),
            "interval_minutes": self.interval,
            "total_jobs_completed": completed,
            "total_jobs_failed": failed,
            "consecutive_failures": self.consecutive_failures,
            "active_model_version_id": active.version_id if active else None,
            "active_model_name": active.version_name if active else None,
            "last_formula_hash": self.last_formula_hash,
            "circuit_breaker_open": self.consecutive_failures
            >= self.max_consecutive_failures,
        }

    async def get_jobs_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent training jobs as dicts from DB.

        Args:
            limit: Maximum number of jobs to return (newest first).

        Returns:
            List of job dicts matching ``TrainingJob.to_dict()``.
        """
        docs = (
            await TrainingLog.find()
            .sort(-TrainingLog.started_at)
            .limit(limit)
            .to_list()
        )
        return [_training_log_to_dict(d) for d in docs]

    async def reserve_job_id(self, trigger_reason: str) -> int:
        """Reserve the next job ID without starting a run.

        Used by the API trigger endpoint so it can return a concrete
        integer job ID before enqueuing the Celery task.
        """
        async with self._lock:
            await self._load_state()
            job_id = self._next_job_id
            self._next_job_id += 1
            await self._save_state()
        logger.info(f"Reserved job_id={job_id} trigger={trigger_reason}")
        return job_id

    async def trigger_manual_training(self) -> int:
        """Manually trigger a training run immediately.

        Returns:
            The new job ID.
        """
        job = await self.run_single_cycle(
            trigger_reason=TriggerReason.MANUAL.value,
            manual=True,
        )
        if job is None:
            return self._next_job_id
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
            await self._broadcast_alert(
                {
                    "severity": "warning",
                    "category": "system",
                    "title": "Model rollback executed",
                    "message": f"Rolled back to version {active.version_id if active else 'unknown'}",
                }
            )
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

    async def _load_state(self) -> None:
        """Restore pipeline state from the ``TrainingPipelineState`` document."""
        if self._state_doc is None:
            self._state_doc = await TrainingPipelineState.find_one()
            if self._state_doc is None:
                self._state_doc = TrainingPipelineState(
                    last_training_time=None,
                    last_formula_hash="",
                    consecutive_failures=0,
                    next_job_id=1,
                    is_running=False,
                    interval_minutes=self.interval,
                )
                await self._state_doc.insert()

        self.last_training_time = self._state_doc.last_training_time
        self.last_formula_hash = self._state_doc.last_formula_hash
        self.consecutive_failures = self._state_doc.consecutive_failures
        self._next_job_id = self._state_doc.next_job_id
        self._is_running = self._state_doc.is_running

    async def _save_state(self) -> None:
        """Persist pipeline state to the ``TrainingPipelineState`` document."""
        if self._state_doc is None:
            return
        self._state_doc.last_training_time = self.last_training_time
        self._state_doc.last_formula_hash = self.last_formula_hash
        self._state_doc.consecutive_failures = self.consecutive_failures
        self._state_doc.next_job_id = self._next_job_id
        self._state_doc.is_running = self._is_running
        self._state_doc.interval_minutes = self.interval
        self._state_doc.circuit_breaker_open = (
            self.consecutive_failures >= self.max_consecutive_failures
        )
        self._state_doc.updated_at = datetime.utcnow()
        await self._state_doc.save()

    def __repr__(self) -> str:
        return (
            f"<AutoTrainingPipeline running={self._is_running} "
            f"interval={self.interval}min>"
        )


# ---------------------------------------------------------------------------
# TrainingLog -> TrainingJob dict conversion
# ---------------------------------------------------------------------------


def _training_log_to_dict(doc: TrainingLog) -> Dict[str, Any]:
    """Convert a ``TrainingLog`` document to the ``TrainingJob.to_dict()`` shape."""
    data = doc.model_dump()

    def _iso(val: Any) -> Any:
        return val.isoformat() if isinstance(val, datetime) else val

    return {
        "job_id": data.get("job_id"),
        "trigger_reason": data.get("trigger_reason"),
        "started_at": _iso(data.get("started_at")),
        "completed_at": _iso(data.get("completed_at")),
        "status": data.get("status"),
        "data_samples": data.get("data_samples") or 0,
        "epochs_trained": data.get("epochs") or 0,
        "final_loss": data.get("final_loss") or 0.0,
        "validation_loss": data.get("validation_loss") or 0.0,
        "model_version_id": data.get("version_id"),
        "checkpoint_path": data.get("checkpoint_path") or "",
        "error_message": data.get("error_message") or "",
        "backtest_metrics": data.get("backtest_metrics") or {},
        "deployed": data.get("deployed") or False,
    }
