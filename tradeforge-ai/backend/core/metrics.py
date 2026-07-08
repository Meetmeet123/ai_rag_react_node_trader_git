"""
Prometheus metrics for TradeForge AI.

All custom business/ML metrics are defined here so they can be imported by
core services and routers without creating circular dependencies.
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# ---------------------------------------------------------------------------
# Training / MLOps metrics
# ---------------------------------------------------------------------------

TRAINING_JOBS_TOTAL = Counter(
    "tf_training_jobs_total",
    "Total number of training jobs",
    ["status"],
)

TRAINING_DURATION = Histogram(
    "tf_training_duration_seconds",
    "End-to-end training cycle duration",
)

ACTIVE_MODEL_VERSION = Gauge(
    "tf_active_model_version",
    "Currently active model version ID",
)

BACKTEST_PNL = Gauge(
    "tf_backtest_pnl",
    "Backtest P&L of the latest candidate model",
)

DRIFT_DETECTED = Gauge(
    "tf_drift_detected",
    "1 if model drift was detected in the last check",
)

# ---------------------------------------------------------------------------
# Inference / execution metrics
# ---------------------------------------------------------------------------

PREDICTION_LATENCY = Histogram(
    "tf_prediction_latency_seconds",
    "Latency of LLM signal generation",
)

EXECUTION_LATENCY = Histogram(
    "tf_execution_latency_seconds",
    "Latency of broker order execution",
)

SIGNALS_GENERATED = Counter(
    "tf_signals_generated_total",
    "Total generated trade signals",
    ["mode", "symbol"],
)

# ---------------------------------------------------------------------------
# Risk / business metrics
# ---------------------------------------------------------------------------

RISK_LIMIT_BREACHES = Counter(
    "tf_risk_limit_breaches_total",
    "Risk limit breaches",
    ["reason"],
)

KILL_SWITCH_TRIGGERS = Counter(
    "tf_kill_switch_triggers_total",
    "Kill switch triggers",
)

DAILY_DRAWDOWN = Gauge(
    "tf_daily_drawdown",
    "Current daily drawdown amount",
)

BROKER_CIRCUIT_OPEN = Gauge(
    "tf_broker_circuit_open",
    "1 if the broker circuit breaker is open",
)
