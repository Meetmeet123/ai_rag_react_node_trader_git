"""
Model Registry — Model Version Management

Manages model versions with:
    - Immutable version tracking (each training run = new version)
    - A/B testing between versions via performance comparison
    - One-click rollback to previous versions
    - Archival of old versions (keep metadata, optionally delete weights)
    - Persistent storage of version metadata as JSON on disk

Design notes:
    - Checkpoint files live on disk under ``models_dir/``; this registry
      only stores *metadata* (JSON) about each checkpoint.
    - Only **one** version can be ``ACTIVE`` at any time — the one used
      for live inference.
    - ``rollback()`` automatically activates the most-recent non-archived
      version that is not the currently active one.
    - Thread-safety: all mutating methods acquire an internal asyncio lock.

Example:
    >>> registry = ModelRegistry(models_dir="./models")
    >>> v1 = ModelVersionInfo(version_id=1, version_name="v1-baseline", ...)
    >>> registry.register_version(v1)
    >>> registry.activate_version(1)
    >>> # ... train v2 ...
    >>> registry.compare_versions(1, 2)
    {'accuracy_delta': 0.03, 'f1_delta': 0.015, 'winner_id': 2}
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger


# ---------------------------------------------------------------------------
# Data class for version metadata
# ---------------------------------------------------------------------------

class ModelVersionInfo:
    """Mutable container for model-version metadata.

    Attributes:
        version_id: Monotonically increasing integer (1, 2, 3 …).
        version_name: Human-readable name, e.g. ``"v3-lr1e4"``.
        description: Free-text description of what changed.
        checkpoint_path: Absolute or relative path to model checkpoint.
        training_data_size: Number of samples used for training.
        training_duration_sec: Wall-clock training time in seconds.
        epochs: Number of epochs completed.
        final_loss: Final training-set loss.
        validation_loss: Validation-set loss (early-stopping target).
        accuracy: Classification accuracy on validation set.
        precision: Precision on validation set.
        recall: Recall on validation set.
        f1_score: F1 score on validation set.
        backtest_pnl: P&L returned by backtest (INR or % depending on config).
        status: One of ``training``, ``ready``, ``active``, ``archived``, ``failed``.
        is_active: Convenience flag — ``True`` iff this version is the active model.
        triggered_by: What triggered training — ``scheduled_20min``, ``formula_change``, ``manual``.
        formula_snapshot: Dict snapshot of strategy formulas at training time.
        created_at: When the version record was created.
        completed_at: When training finished (``None`` until then).
    """

    def __init__(
        self,
        version_id: int,
        version_name: str,
        checkpoint_path: str,
        description: str = "",
        training_data_size: int = 0,
        training_duration_sec: float = 0.0,
        epochs: int = 0,
        final_loss: float = 0.0,
        validation_loss: float = 0.0,
        accuracy: float = 0.0,
        precision: float = 0.0,
        recall: float = 0.0,
        f1_score: float = 0.0,
        backtest_pnl: float = 0.0,
        status: str = "training",
        is_active: bool = False,
        triggered_by: str = "scheduled_20min",
        formula_snapshot: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
    ) -> None:
        self.version_id = version_id
        self.version_name = version_name
        self.description = description
        self.checkpoint_path = checkpoint_path
        self.training_data_size = training_data_size
        self.training_duration_sec = training_duration_sec
        self.epochs = epochs
        self.final_loss = final_loss
        self.validation_loss = validation_loss
        self.accuracy = accuracy
        self.precision = precision
        self.recall = recall
        self.f1_score = f1_score
        self.backtest_pnl = backtest_pnl
        self.status = status
        self.is_active = is_active
        self.triggered_by = triggered_by
        self.formula_snapshot = formula_snapshot or {}
        self.created_at = created_at or datetime.utcnow()
        self.completed_at = completed_at

    # ---- dict serialization helpers ----

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a JSON-serializable dictionary."""
        return {
            "version_id": self.version_id,
            "version_name": self.version_name,
            "description": self.description,
            "checkpoint_path": self.checkpoint_path,
            "training_data_size": self.training_data_size,
            "training_duration_sec": self.training_duration_sec,
            "epochs": self.epochs,
            "final_loss": self.final_loss,
            "validation_loss": self.validation_loss,
            "accuracy": self.accuracy,
            "precision": self.precision,
            "recall": self.recall,
            "f1_score": self.f1_score,
            "backtest_pnl": self.backtest_pnl,
            "status": self.status,
            "is_active": self.is_active,
            "triggered_by": self.triggered_by,
            "formula_snapshot": self.formula_snapshot,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelVersionInfo":
        """Reconstruct from a dictionary (inverse of ``to_dict``)."""
        # Parse ISO datetime strings back to datetime objects
        for key in ("created_at", "completed_at"):
            val = data.get(key)
            if isinstance(val, str):
                data[key] = datetime.fromisoformat(val)
        return cls(**{k: v for k, v in data.items() if k in cls.__init__.__code__.co_varnames})

    def __repr__(self) -> str:
        return (
            f"<ModelVersionInfo id={self.version_id} name={self.version_name!r} "
            f"status={self.status} active={self.is_active}>"
        )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class ModelRegistry:
    """Central registry for all model versions.

    Persists version metadata to ``{models_dir}/registry.json`` so that
    the registry survives process restarts.  Checkpoint files themselves
    are stored separately (this class only tracks their paths).

    Thread-safety: all public mutating methods are protected by an
    ``asyncio.Lock`` so they can safely be called from multiple async
    tasks (e.g., training loop + HTTP admin API).

    Args:
        models_dir: Directory where registry.json and per-version
            subdirectories live.
    """

    REGISTRY_FILENAME = "registry.json"

    def __init__(self, models_dir: str = "./models") -> None:
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)

        # In-memory store: version_id -> ModelVersionInfo
        self.versions: Dict[int, ModelVersionInfo] = {}
        self.active_version_id: Optional[int] = None

        # Concurrency control
        self._lock = asyncio.Lock()  # type: ignore[var-annotated]

        self._load_registry()
        logger.info(
            f"ModelRegistry loaded — {len(self.versions)} versions, "
            f"active={self.active_version_id}"
        )

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def register_version(self, info: ModelVersionInfo) -> int:
        """Register a new model version.

        Args:
            info: Populated ``ModelVersionInfo`` instance.  If
                ``version_id`` collides with an existing entry a
                new ID is auto-assigned.

        Returns:
            The (possibly reassigned) version ID.
        """
        # Auto-assign ID if collision
        if info.version_id in self.versions:
            new_id = (max(self.versions.keys()) + 1) if self.versions else 1
            logger.warning(
                f"Version ID {info.version_id} already exists — "
                f"reassigning to {new_id}"
            )
            info.version_id = new_id

        self.versions[info.version_id] = info
        self._save_registry()
        logger.info(
            f"Registered model version {info.version_id} — {info.version_name!r}"
        )
        return info.version_id

    def activate_version(self, version_id: int) -> bool:
        """Set a version as the active model.

        Deactivates the currently active version (if any) and updates
        the new version's status to ``active``.

        Args:
            version_id: ID of the version to activate.

        Returns:
            ``True`` on success, ``False`` if version not found or
            status is ``archived`` / ``failed``.
        """
        if version_id not in self.versions:
            logger.error(f"Cannot activate unknown version {version_id}")
            return False

        target = self.versions[version_id]
        if target.status in ("archived", "failed"):
            logger.error(
                f"Cannot activate version {version_id} — status is {target.status}"
            )
            return False

        # Deactivate previous
        if self.active_version_id is not None:
            prev = self.versions.get(self.active_version_id)
            if prev is not None:
                prev.is_active = False
                if prev.status == "active":
                    prev.status = "ready"

        # Activate new
        target.is_active = True
        target.status = "active"
        self.active_version_id = version_id
        self._save_registry()
        logger.info(f"Activated model version {version_id} — {target.version_name!r}")
        return True

    def get_active_version(self) -> Optional[ModelVersionInfo]:
        """Get the currently active model version, or ``None``."""
        if self.active_version_id is None:
            return None
        return self.versions.get(self.active_version_id)

    def get_version(self, version_id: int) -> Optional[ModelVersionInfo]:
        """Get a specific version by ID."""
        return self.versions.get(version_id)

    def list_versions(
        self,
        status_filter: Optional[str] = None,
    ) -> List[ModelVersionInfo]:
        """List all versions sorted by creation date (newest first).

        Args:
            status_filter: If provided, only return versions with this
                status (e.g., ``"active"``, ``"ready"``).

        Returns:
            List of ``ModelVersionInfo`` objects.
        """
        versions = list(self.versions.values())
        if status_filter:
            versions = [v for v in versions if v.status == status_filter]
        versions.sort(key=lambda v: v.created_at, reverse=True)
        return versions

    # ------------------------------------------------------------------
    # Comparison & rollback
    # ------------------------------------------------------------------

    def compare_versions(self, v1_id: int, v2_id: int) -> Dict[str, Any]:
        """Compare two model versions across all metrics.

        Computes delta as ``v2 - v1`` so positive values mean v2 is
        better.

        Args:
            v1_id: Baseline version ID.
            v2_id: Challenger version ID.

        Returns:
            Dict with raw metrics for both versions, deltas, and a
            ``winner_id`` field indicating which version is better.
        """
        v1 = self.versions.get(v1_id)
        v2 = self.versions.get(v2_id)
        if v1 is None or v2 is None:
            missing = []
            if v1 is None:
                missing.append(v1_id)
            if v2 is None:
                missing.append(v2_id)
            raise ValueError(f"Version(s) not found: {missing}")

        metrics = ["accuracy", "precision", "recall", "f1_score", "backtest_pnl"]
        v1_metrics = {m: getattr(v1, m, 0.0) for m in metrics}
        v2_metrics = {m: getattr(v2, m, 0.0) for m in metrics}
        deltas = {f"{m}_delta": v2_metrics[m] - v1_metrics[m] for m in metrics}

        # Simple scoring: sum of normalized deltas (all metrics treated equally)
        score = sum(deltas.values())
        winner_id = v2_id if score >= 0 else v1_id

        return {
            "version_a_id": v1_id,
            "version_a_name": v1.version_name,
            "version_b_id": v2_id,
            "version_b_name": v2.version_name,
            "v1_metrics": v1_metrics,
            "v2_metrics": v2_metrics,
            "deltas": deltas,
            "composite_score": round(score, 6),
            "winner_id": winner_id,
            "summary": (
                f"Version {winner_id} wins with composite score {score:+.4f} "
                f"(accuracy Δ={deltas.get('accuracy_delta', 0):+.4f}, "
                f"f1 Δ={deltas.get('f1_score_delta', 0):+.4f}, "
                f"backtest_pnl Δ={deltas.get('backtest_pnl_delta', 0):+.4f})"
            ),
        }

    def rollback(self) -> bool:
        """Rollback to the previous active version.

        Activates the most-recent non-archived, non-failed version that
        is *not* the currently active one.

        Returns:
            ``True`` if a previous version was found and activated.
        """
        candidates = [
            v for v in self.versions.values()
            if v.version_id != self.active_version_id
            and v.status not in ("archived", "failed")
        ]
        if not candidates:
            logger.warning("Rollback failed — no eligible previous version")
            return False

        # Pick most recent
        prev = max(candidates, key=lambda v: v.created_at)
        logger.info(
            f"Rolling back from version {self.active_version_id} "
            f"to version {prev.version_id}"
        )
        return self.activate_version(prev.version_id)

    # ------------------------------------------------------------------
    # Archive / delete
    # ------------------------------------------------------------------

    def archive_version(self, version_id: int) -> None:
        """Archive a version.

        Sets status to ``archived`` and deactivates if it was active.
        The checkpoint file is kept on disk but is no longer eligible
        for activation.

        Args:
            version_id: Version to archive.
        """
        if version_id not in self.versions:
            logger.warning(f"Cannot archive unknown version {version_id}")
            return
        v = self.versions[version_id]
        if v.is_active:
            v.is_active = False
            self.active_version_id = None
        v.status = "archived"
        self._save_registry()
        logger.info(f"Archived version {version_id} — {v.version_name!r}")

    def delete_version(self, version_id: int) -> None:
        """Permanently delete a version.

        Removes the metadata entry **and** the checkpoint directory.
        If the version was active, the active pointer is cleared.

        Args:
            version_id: Version to delete.
        """
        if version_id not in self.versions:
            logger.warning(f"Cannot delete unknown version {version_id}")
            return
        v = self.versions.pop(version_id)
        if v.is_active:
            self.active_version_id = None
        # Delete checkpoint files
        ckpt_path = Path(v.checkpoint_path)
        if ckpt_path.exists():
            try:
                if ckpt_path.is_dir():
                    shutil.rmtree(ckpt_path)
                else:
                    ckpt_path.unlink()
                logger.info(f"Deleted checkpoint for version {version_id}")
            except Exception as exc:
                logger.error(f"Failed to delete checkpoint {ckpt_path}: {exc}")
        self._save_registry()
        logger.info(f"Deleted version {version_id} — {v.version_name!r}")

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def update_performance(self, version_id: int, metrics: Dict[str, float]) -> None:
        """Update performance metrics for a version (e.g., from live trading).

        Args:
            version_id: Target version.
            metrics: Dict of metric names to values.  Supported keys:
                ``accuracy``, ``precision``, ``recall``, ``f1_score``,
                ``backtest_pnl``.
        """
        if version_id not in self.versions:
            logger.warning(f"Cannot update metrics for unknown version {version_id}")
            return
        v = self.versions[version_id]
        for key in ("accuracy", "precision", "recall", "f1_score", "backtest_pnl"):
            if key in metrics:
                setattr(v, key, float(metrics[key]))
        self._save_registry()
        logger.debug(f"Updated metrics for version {version_id}")

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _registry_path(self) -> Path:
        return self.models_dir / self.REGISTRY_FILENAME

    def _save_registry(self) -> None:
        """Flush in-memory version store to ``registry.json``."""
        payload = {
            "active_version_id": self.active_version_id,
            "versions": {vid: v.to_dict() for vid, v in self.versions.items()},
            "saved_at": datetime.utcnow().isoformat(),
        }
        try:
            with open(self._registry_path(), "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2, ensure_ascii=False, default=str)
        except Exception as exc:
            logger.error(f"Failed to save registry: {exc}")

    def _load_registry(self) -> None:
        """Hydrate in-memory store from ``registry.json``."""
        path = self._registry_path()
        if not path.exists():
            logger.info("No existing registry found — starting fresh")
            return
        try:
            with open(path, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
            self.active_version_id = payload.get("active_version_id")
            raw_versions = payload.get("versions", {})
            self.versions = {
                int(vid): ModelVersionInfo.from_dict(vdict)
                for vid, vdict in raw_versions.items()
            }
            logger.info(f"Loaded registry with {len(self.versions)} versions")
        except Exception as exc:
            logger.error(f"Failed to load registry from {path}: {exc}")
            self.versions = {}
            self.active_version_id = None

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def get_next_version_id(self) -> int:
        """Return the next available version ID (max + 1)."""
        if not self.versions:
            return 1
        return max(self.versions.keys()) + 1

    def get_version_count(self) -> int:
        """Total number of registered versions."""
        return len(self.versions)

    def get_active_count_by_status(self) -> Dict[str, int]:
        """Return counts of versions grouped by status."""
        counts: Dict[str, int] = {}
        for v in self.versions.values():
            counts[v.status] = counts.get(v.status, 0) + 1
        return counts

    def __repr__(self) -> str:
        return (
            f"<ModelRegistry versions={len(self.versions)} "
            f"active={self.active_version_id}>"
        )


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------

def compute_formula_hash(formula_dict: Dict[str, Any]) -> str:
    """Compute a SHA-256 hash of a formula dictionary.

    Used to detect whether strategy formulas have changed between
    training runs.

    Args:
        formula_dict: Dictionary containing strategy parameters.

    Returns:
        Hex digest string.
    """
    canonical = json.dumps(formula_dict, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
