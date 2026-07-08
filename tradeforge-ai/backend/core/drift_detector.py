"""
Model drift detector for TradeForge AI.

Uses the two-sample Kolmogorov-Smirnov test to compare the distribution of
features (or model outputs) captured at training time against the current
window. A low p-value indicates that the market regime has shifted and the
model may need retraining.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
from loguru import logger
from scipy.stats import ks_2samp


class DriftDetector:
    """Detect drift between a reference distribution and a current sample."""

    def __init__(self, threshold: float = 0.05) -> None:
        """
        Args:
            threshold: p-value below which drift is declared.
        """
        self.threshold = threshold

    def check(
        self,
        reference: Dict[str, List[float]],
        current: Dict[str, List[float]],
    ) -> Dict[str, Any]:
        """Run KS tests for each feature present in both distributions.

        Args:
            reference: Mapping from feature name to reference sample values.
            current: Mapping from feature name to current sample values.

        Returns:
            Dict with per-feature KS statistics and an overall ``drift_detected`` flag.
        """
        results: Dict[str, Any] = {}
        drift_detected = False

        for feature, ref_values in reference.items():
            cur_values = current.get(feature)
            if cur_values is None or len(ref_values) < 2 or len(cur_values) < 2:
                continue

            ref = np.asarray(ref_values, dtype=float)
            cur = np.asarray(cur_values, dtype=float)
            # Drop NaNs
            ref = ref[np.isfinite(ref)]
            cur = cur[np.isfinite(cur)]
            if len(ref) < 2 or len(cur) < 2:
                continue

            stat, pvalue = ks_2samp(ref, cur)
            is_drift = pvalue < self.threshold
            drift_detected = drift_detected or is_drift
            results[feature] = {
                "ks_stat": float(stat),
                "pvalue": float(pvalue),
                "drift": is_drift,
            }

        results["drift_detected"] = drift_detected
        logger.debug(
            "Drift check: {} features, drift_detected={}",
            len(results) - 1,
            drift_detected,
        )
        return results

    @staticmethod
    def extract_feature_dict(
        data: Dict[str, List[float]],
        feature_names: Optional[List[str]] = None,
    ) -> Dict[str, List[float]]:
        """Helper to normalise a feature dict (e.g., from a DataFrame)."""
        if feature_names is None:
            return {k: v for k, v in data.items() if isinstance(v, list)}
        return {
            k: data[k] for k in feature_names if k in data and isinstance(data[k], list)
        }
