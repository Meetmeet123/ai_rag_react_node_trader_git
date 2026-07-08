"""
TradeForge AI — Natural Language Strategy Parser & Code Generator.

This module forms the bridge between human-readable trading ideas and
machine-executable strategy code.  The pipeline is::

    NL prompt → StrategyTemplate (Pydantic) → JSON definition
    JSON definition → CodeGenerator → Python source code

The generated code is pure, stateless, and imports only ``pandas``,
``numpy``, and the local ``core.indicators`` module so it can be safely
executed by the backtest engine or live trading loop.
"""

from __future__ import annotations

import keyword
import re
from enum import Enum
from typing import Any, Dict, List, Set, Tuple

from pydantic import BaseModel, Field, field_validator
from loguru import logger

# ---------------------------------------------------------------------------
# Enums & Constants
# ---------------------------------------------------------------------------


class IndicatorName(str, Enum):
    """Indicators the parser recognises in natural-language prompts."""

    SMA = "sma"
    EMA = "ema"
    WMA = "wma"
    HMA = "hma"
    RSI = "rsi"
    MACD = "macd"
    BB = "bollinger_bands"
    ATR = "atr"
    VWAP = "vwap"
    STOCHASTIC = "stochastic"
    ADX = "adx"
    OBV = "obv"
    CCI = "cci"
    MFI = "mfi"
    SUPERTREND = "supertrend"
    PSAR = "psar"
    WILLIAMS_R = "williams_r"


class ComparisonOp(str, Enum):
    """Comparison operators supported in condition expressions."""

    GT = ">"
    GTE = ">="
    LT = "<"
    LTE = "<="
    EQ = "=="
    NEQ = "!="


class StopLossType(str, Enum):
    """Stop-loss calculation methods."""

    FIXED_PCT = "fixed_pct"
    TRAILING = "trailing"
    ATR_BASED = "atr_based"


class TargetType(str, Enum):
    """Profit-target calculation methods."""

    FIXED_PCT = "fixed_pct"
    TRAILING = "trailing"
    ATR_BASED = "atr_based"


class PositionSizingType(str, Enum):
    """Position sizing modes."""

    FIXED_QTY = "fixed_qty"
    PCT_CAPITAL = "pct_capital"
    RISK_BASED = "risk_based"


# Mapping of fuzzy NL tokens → canonical indicator names.
INDICATOR_ALIASES: Dict[str, IndicatorName] = {
    "simple moving average": IndicatorName.SMA,
    "sma": IndicatorName.SMA,
    "exponential moving average": IndicatorName.EMA,
    "ema": IndicatorName.EMA,
    "weighted moving average": IndicatorName.WMA,
    "wma": IndicatorName.WMA,
    "hull moving average": IndicatorName.HMA,
    "hma": IndicatorName.HMA,
    "rsi": IndicatorName.RSI,
    "relative strength index": IndicatorName.RSI,
    "macd": IndicatorName.MACD,
    "moving average convergence divergence": IndicatorName.MACD,
    "bollinger bands": IndicatorName.BB,
    "bollinger": IndicatorName.BB,
    "bb": IndicatorName.BB,
    "atr": IndicatorName.ATR,
    "average true range": IndicatorName.ATR,
    "vwap": IndicatorName.VWAP,
    "volume weighted average price": IndicatorName.VWAP,
    "stochastic": IndicatorName.STOCHASTIC,
    "stoch": IndicatorName.STOCHASTIC,
    "adx": IndicatorName.ADX,
    "average directional index": IndicatorName.ADX,
    "obv": IndicatorName.OBV,
    "on balance volume": IndicatorName.OBV,
    "cci": IndicatorName.CCI,
    "commodity channel index": IndicatorName.CCI,
    "mfi": IndicatorName.MFI,
    "money flow index": IndicatorName.MFI,
    "supertrend": IndicatorName.SUPERTREND,
    "super trend": IndicatorName.SUPERTREND,
    "psar": IndicatorName.PSAR,
    "parabolic sar": IndicatorName.PSAR,
    "williams r": IndicatorName.WILLIAMS_R,
    "williams %r": IndicatorName.WILLIAMS_R,
    "%r": IndicatorName.WILLIAMS_R,
}

# ---------------------------------------------------------------------------
# Pydantic Data Transfer Objects
# ---------------------------------------------------------------------------


class IndicatorParam(BaseModel):
    """A single parameter for an indicator call."""

    name: str = Field(description="Parameter name, e.g. 'period', 'fast'")
    value: Any = Field(description="Literal value, e.g. 14, 12, 2.0")


class IndicatorRef(BaseModel):
    """Reference to an indicator used inside a strategy."""

    name: IndicatorName
    params: List[IndicatorParam] = Field(default_factory=list)
    output_column: str = Field(
        default="", description="Column alias when indicator returns multiple outputs"
    )

    def column_name(self) -> str:
        """Generate a deterministic column name for this indicator call."""
        if self.output_column:
            return self.output_column
        param_str = "_".join(f"{p.name}{p.value}" for p in self.params)
        if param_str:
            return f"{self.name.value}_{param_str}"
        return self.name.value


class Condition(BaseModel):
    """A single comparison condition (e.g., rsi_14 < 30)."""

    left: str = Field(description="Left-hand side: indicator column or value")
    op: ComparisonOp
    right: str = Field(description="Right-hand side: indicator column or value")

    def to_python(self) -> str:
        """Render the condition as a Python boolean expression."""
        return f"{self.left} {self.op.value} {self.right}"


class ConditionGroup(BaseModel):
    """Grouped conditions with a logical operator."""

    operator: str = Field(
        default="AND", pattern="^(AND|OR)$", description="Logical combiner: AND or OR"
    )
    conditions: List[Condition] = Field(default_factory=list)

    def to_python(self) -> str:
        """Render the group as a parenthesised Python expression."""
        if not self.conditions:
            return "True"
        joined = f" {self.operator.lower()} ".join(
            c.to_python() for c in self.conditions
        )
        return f"({joined})"


class RiskParams(BaseModel):
    """Risk-management parameters for a strategy."""

    stop_loss_type: StopLossType = StopLossType.FIXED_PCT
    stop_loss_value: float = Field(default=1.0, gt=0.0)
    target_type: TargetType = TargetType.FIXED_PCT
    target_value: float = Field(default=2.0, gt=0.0)
    position_sizing_type: PositionSizingType = PositionSizingType.FIXED_QTY
    position_sizing_value: float = Field(default=1.0, gt=0.0)


class StrategyTemplate(BaseModel):
    """Validated, structured representation of a trading strategy.

    This is the central data model that the NL parser produces and the
    code generator consumes.
    """

    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="")
    instrument: str = Field(..., min_length=1, max_length=50)
    segment: str = Field(default="equity")
    timeframe: str = Field(default="15m")

    indicators: List[IndicatorRef] = Field(default_factory=list)
    entry_conditions: ConditionGroup = Field(default_factory=lambda: ConditionGroup())
    exit_conditions: ConditionGroup = Field(default_factory=lambda: ConditionGroup())
    risk: RiskParams = Field(default_factory=RiskParams)

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("strategy name cannot be empty")
        # Sanitise for safe use as a Python identifier.
        v = re.sub(r"[^a-zA-Z0-9_\s]", "", v)
        v = re.sub(r"\s+", "_", v)
        if keyword.iskeyword(v):
            v = f"{v}_strategy"
        return v

    def to_definition_json(self) -> dict:
        """Serialise to the JSON format stored in ``Strategy.definition``."""
        return self.model_dump(mode="json")


# ---------------------------------------------------------------------------
# NL Parser
# ---------------------------------------------------------------------------


class NLParser:
    """Extract structured strategy components from natural-language text.

    The parser uses keyword matching and lightweight regex — no LLM call is
    required, making it suitable for low-latency interactive use.  The
    resulting :class:`StrategyTemplate` can be refined by the user or sent
    to the :class:`CodeGenerator`.
    """

    # Regex patterns for extracting numeric values after keywords.
    _PERIOD_RE = re.compile(r"period\s+(\d+)", re.IGNORECASE)
    _FAST_RE = re.compile(r"fast\s+(\d+)", re.IGNORECASE)
    _SLOW_RE = re.compile(r"slow\s+(\d+)", re.IGNORECASE)
    _WINDOW_RE = re.compile(r"window\s+(\d+)", re.IGNORECASE)

    # Stop-loss / target extraction.
    _SL_PCT_RE = re.compile(
        r"stop\s*loss\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*%", re.IGNORECASE
    )
    _TG_PCT_RE = re.compile(r"target\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*%", re.IGNORECASE)
    _SL_ATR_RE = re.compile(
        r"stop\s*loss\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*(?:x\s*)?atr",
        re.IGNORECASE,
    )
    _TG_ATR_RE = re.compile(
        r"target\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*(?:x\s*)?atr",
        re.IGNORECASE,
    )

    def __init__(self) -> None:
        self._aliases = INDICATOR_ALIASES

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse(self, prompt: str) -> StrategyTemplate:
        """Parse a natural-language strategy description.

        Parameters
        ----------
        prompt:
            Free-text description, e.g.
            ``"Buy Nifty when RSI below 30 with stop loss 1%"``.

        Returns
        -------
        StrategyTemplate
            Structured, validated strategy representation.
        """
        if not prompt or not prompt.strip():
            raise ValueError("prompt cannot be empty")

        prompt_lower = prompt.lower().strip()
        logger.debug(f"Parsing strategy prompt: {prompt_lower!r}")

        # 1. Detect direction (buy / sell).
        direction = self._detect_direction(prompt_lower)

        # 2. Detect instrument.
        instrument = self._detect_instrument(prompt_lower)

        # 3. Detect timeframe.
        timeframe = self._detect_timeframe(prompt_lower)

        # 4. Extract indicators and their default parameters.
        indicators = self._extract_indicators(prompt_lower)

        # 5. Build entry conditions from detected indicators + comparisons.
        entry_conditions = self._build_conditions(prompt_lower, indicators, direction)

        # 6. Extract risk parameters.
        risk = self._extract_risk_params(prompt_lower)

        # 7. Infer exit conditions (opposite direction or target hit).
        exit_conditions = self._infer_exit_conditions(entry_conditions, risk, direction)

        # 8. Derive strategy name.
        name = self._derive_name(prompt_lower, instrument, direction)

        template = StrategyTemplate(
            name=name,
            description=prompt.strip(),
            instrument=instrument,
            timeframe=timeframe,
            indicators=indicators,
            entry_conditions=entry_conditions,
            exit_conditions=exit_conditions,
            risk=risk,
        )
        logger.info(f"Parsed strategy template: {template.name}")
        return template

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _detect_direction(self, prompt: str) -> str:
        """Return 'buy' or 'sell' based on prompt keywords."""
        buy_words = {"buy", "long", "bullish", "entry", "enter"}
        sell_words = {"sell", "short", "bearish", "exit", "cover"}
        buy_score = sum(1 for w in buy_words if w in prompt)
        sell_score = sum(1 for w in sell_words if w in prompt)
        return "sell" if sell_score > buy_score else "buy"

    def _detect_instrument(self, prompt: str) -> str:
        """Extract instrument / symbol from the prompt."""
        # Common Indian market instruments.
        known = [
            "nifty",
            "nifty50",
            "banknifty",
            "sensex",
            "finnifty",
            "reliance",
            "tcs",
            "infy",
            "hdfcbank",
            "icicibank",
            "sbilife",
            "lt",
            "itc",
            "hul",
            "bhartiartl",
        ]
        for sym in known:
            if sym in prompt.replace(" ", "").replace("&", "").lower():
                return sym.upper()
        # Fallback: try to capture a capitalised word after buy/sell.
        m = re.search(r"(?:buy|sell|long|short)\s+(\w+)", prompt)
        if m:
            return m.group(1).upper()
        return "NIFTY50"

    def _detect_timeframe(self, prompt: str) -> str:
        """Extract candle timeframe from the prompt."""
        tf_pattern = re.compile(
            r"\b(\d+)\s*(min|minute|m|hour|h|day|d|week|wk)\b",
            re.IGNORECASE,
        )
        m = tf_pattern.search(prompt)
        if m:
            num, unit = m.group(1), m.group(2).lower()
            unit_map = {
                "min": "m",
                "minute": "m",
                "m": "m",
                "hour": "h",
                "h": "h",
                "day": "d",
                "d": "d",
                "week": "wk",
                "wk": "wk",
            }
            return f"{num}{unit_map.get(unit, unit)}"
        return "15m"

    def _extract_indicators(self, prompt: str) -> List[IndicatorRef]:
        """Find all indicator references in the prompt."""
        found: List[IndicatorRef] = []
        seen: Set[str] = set()

        for alias, canonical in self._aliases.items():
            if alias in prompt and canonical.value not in seen:
                seen.add(canonical.value)
                params = self._infer_params(prompt, canonical)
                ref = IndicatorRef(name=canonical, params=params)
                found.append(ref)

        # Default: always include SMA as a baseline if no indicators found.
        if not found:
            found.append(
                IndicatorRef(
                    name=IndicatorName.SMA,
                    params=[IndicatorParam(name="period", value=20)],
                )
            )
            logger.debug("No indicators detected — adding default SMA(20)")

        return found

    def _infer_params(
        self, prompt: str, indicator: IndicatorName
    ) -> List[IndicatorParam]:
        """Infer indicator parameters from surrounding context."""
        params: List[IndicatorParam] = []

        # Look for period/window mentions near the indicator name.
        idx = prompt.find(indicator.value)
        if idx == -1:
            # Try aliases.
            for alias, canon in self._aliases.items():
                if canon == indicator and alias in prompt:
                    idx = prompt.find(alias)
                    break

        context = prompt[max(0, idx - 30) : idx + 60] if idx >= 0 else prompt

        if indicator in {
            IndicatorName.RSI,
            IndicatorName.ATR,
            IndicatorName.CCI,
            IndicatorName.MFI,
            IndicatorName.STOCHASTIC,
            IndicatorName.ADX,
        }:
            m = self._PERIOD_RE.search(context)
            period = int(m.group(1)) if m else 14
            params.append(IndicatorParam(name="period", value=period))

        elif indicator == IndicatorName.SMA:
            m = self._PERIOD_RE.search(context)
            period = int(m.group(1)) if m else 20
            params.append(IndicatorParam(name="period", value=period))

        elif indicator == IndicatorName.EMA:
            m = self._PERIOD_RE.search(context)
            period = int(m.group(1)) if m else 20
            params.append(IndicatorParam(name="period", value=period))

        elif indicator == IndicatorName.MACD:
            fast_m = self._FAST_RE.search(context)
            slow_m = self._SLOW_RE.search(context)
            fast = int(fast_m.group(1)) if fast_m else 12
            slow = int(slow_m.group(1)) if slow_m else 26
            params.append(IndicatorParam(name="fast", value=fast))
            params.append(IndicatorParam(name="slow", value=slow))

        elif indicator == IndicatorName.BB:
            m = self._PERIOD_RE.search(context)
            period = int(m.group(1)) if m else 20
            params.append(IndicatorParam(name="period", value=period))

        return params

    def _build_conditions(
        self,
        prompt: str,
        indicators: List[IndicatorRef],
        direction: str,
    ) -> ConditionGroup:
        """Build entry conditions from detected indicators and comparisons."""
        conditions: List[Condition] = []

        for ind in indicators:
            col = ind.column_name()
            # Search for comparison patterns like "RSI below 30".
            patterns = self._condition_patterns_for(ind, col)
            for regex, op, right_template in patterns:
                m = regex.search(prompt)
                if m:
                    right_val = m.group(1)
                    conditions.append(
                        Condition(
                            left=col,
                            op=op,
                            right=right_template.format(right_val),
                        )
                    )
                    break  # Only first match per indicator.

        # Fallback: if no conditions extracted, use a simple crossover.
        if not conditions and len(indicators) >= 1:
            col = indicators[0].column_name()
            if direction == "buy":
                conditions.append(Condition(left=col, op=ComparisonOp.LT, right="30"))
            else:
                conditions.append(Condition(left=col, op=ComparisonOp.GT, right="70"))
            logger.debug(f"No explicit conditions — using fallback {col} threshold")

        return ConditionGroup(operator="AND", conditions=conditions)

    def _condition_patterns_for(
        self, ind: IndicatorRef, col: str
    ) -> List[Tuple[re.Pattern, ComparisonOp, str]]:
        """Return (regex, operator, right-hand-template) tuples for an indicator."""
        return [
            (
                re.compile(
                    rf"{ind.name.value}\s+(?:below|under|less than|<)\s+(\d+(?:\.\d+)?)",
                    re.IGNORECASE,
                ),
                ComparisonOp.LT,
                "{}",
            ),
            (
                re.compile(
                    rf"{ind.name.value}\s+(?:above|over|greater than|>)\s+(\d+(?:\.\d+)?)",
                    re.IGNORECASE,
                ),
                ComparisonOp.GT,
                "{}",
            ),
            (
                re.compile(
                    rf"{ind.name.value}\s+(?:crossing above|crosses above)\s+(\d+(?:\.\d+)?)",
                    re.IGNORECASE,
                ),
                ComparisonOp.GT,
                "{}",
            ),
            (
                re.compile(
                    rf"{ind.name.value}\s+(?:crossing below|crosses below)\s+(\d+(?:\.\d+)?)",
                    re.IGNORECASE,
                ),
                ComparisonOp.LT,
                "{}",
            ),
            # Generic: "<number> RSI"
            (
                re.compile(
                    rf"(?:below|under)\s+(\d+(?:\.\d+)?)\s+{ind.name.value}",
                    re.IGNORECASE,
                ),
                ComparisonOp.LT,
                "{}",
            ),
            (
                re.compile(
                    rf"(?:above|over)\s+(\d+(?:\.\d+)?)\s+{ind.name.value}",
                    re.IGNORECASE,
                ),
                ComparisonOp.GT,
                "{}",
            ),
        ]

    def _extract_risk_params(self, prompt: str) -> RiskParams:
        """Extract stop-loss, target, and position sizing from prompt."""
        sl_type, sl_val = StopLossType.FIXED_PCT, 1.0
        tg_type, tg_val = TargetType.FIXED_PCT, 2.0
        ps_type, ps_val = PositionSizingType.FIXED_QTY, 1.0

        # Stop-loss
        m_pct = self._SL_PCT_RE.search(prompt)
        if m_pct:
            sl_val = float(m_pct.group(1))
            sl_type = StopLossType.FIXED_PCT
        else:
            m_atr = self._SL_ATR_RE.search(prompt)
            if m_atr:
                sl_val = float(m_atr.group(1))
                sl_type = StopLossType.ATR_BASED

        # Target
        m_tg_pct = self._TG_PCT_RE.search(prompt)
        if m_tg_pct:
            tg_val = float(m_tg_pct.group(1))
            tg_type = TargetType.FIXED_PCT
        else:
            m_tg_atr = self._TG_ATR_RE.search(prompt)
            if m_tg_atr:
                tg_val = float(m_tg_atr.group(1))
                tg_type = TargetType.ATR_BASED

        # Position sizing — detect "X% capital" or "X shares"
        ps_pct = re.search(
            r"(\d+(?:\.\d+)?)\s*%\s+(?:of\s+)?capital", prompt, re.IGNORECASE
        )
        if ps_pct:
            ps_type = PositionSizingType.PCT_CAPITAL
            ps_val = float(ps_pct.group(1))
        else:
            ps_qty = re.search(
                r"(\d+)\s*(?:shares|qty|quantity|lots)", prompt, re.IGNORECASE
            )
            if ps_qty:
                ps_val = float(ps_qty.group(1))

        return RiskParams(
            stop_loss_type=sl_type,
            stop_loss_value=sl_val,
            target_type=tg_type,
            target_value=tg_val,
            position_sizing_type=ps_type,
            position_sizing_value=ps_val,
        )

    def _infer_exit_conditions(
        self,
        entry: ConditionGroup,
        risk: RiskParams,
        direction: str,
    ) -> ConditionGroup:
        """Generate sensible exit conditions from entry + risk params."""
        conditions: List[Condition] = []

        # Opposite signal of entry (simplified).
        for ec in entry.conditions:
            inverted_op = {
                ComparisonOp.LT: ComparisonOp.GT,
                ComparisonOp.LTE: ComparisonOp.GTE,
                ComparisonOp.GT: ComparisonOp.LT,
                ComparisonOp.GTE: ComparisonOp.LTE,
                ComparisonOp.EQ: ComparisonOp.NEQ,
                ComparisonOp.NEQ: ComparisonOp.EQ,
            }.get(ec.op, ComparisonOp.EQ)
            conditions.append(Condition(left=ec.left, op=inverted_op, right=ec.right))

        return ConditionGroup(operator="OR", conditions=conditions)

    def _derive_name(self, prompt: str, instrument: str, direction: str) -> str:
        """Create a concise strategy name from prompt components."""
        # Sanitise
        name = re.sub(r"[^a-zA-Z0-9_\s]", "", prompt)
        name = re.sub(r"\s+", "_", name).strip("_")
        # Truncate
        if len(name) > 60:
            name = name[:60]
        if not name:
            name = f"{direction}_{instrument}_strategy"
        return name


# ---------------------------------------------------------------------------
# Strategy Validator
# ---------------------------------------------------------------------------


class ValidationResult(BaseModel):
    """Outcome of a strategy validation run."""

    is_valid: bool = False
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.is_valid = False

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)


class StrategyValidator:
    """Validate a :class:`StrategyTemplate` before code generation.

    Checks that every indicator used in conditions is declared, that
    parameter values are in sensible ranges, and that risk parameters
    are internally consistent.
    """

    # Minimum rows required for each indicator to produce non-NaN output.
    _MIN_PERIODS: Dict[IndicatorName, int] = {
        IndicatorName.SMA: 2,
        IndicatorName.EMA: 2,
        IndicatorName.WMA: 2,
        IndicatorName.HMA: 2,
        IndicatorName.RSI: 14,
        IndicatorName.MACD: 26,
        IndicatorName.BB: 20,
        IndicatorName.ATR: 14,
        IndicatorName.VWAP: 1,
        IndicatorName.STOCHASTIC: 14,
        IndicatorName.ADX: 14,
        IndicatorName.OBV: 1,
        IndicatorName.CCI: 20,
        IndicatorName.MFI: 14,
        IndicatorName.SUPERTREND: 10,
        IndicatorName.PSAR: 2,
        IndicatorName.WILLIAMS_R: 14,
    }

    def validate(self, template: StrategyTemplate) -> ValidationResult:
        """Validate *template* and return a :class:`ValidationResult`.

        Parameters
        ----------
        template:
            The strategy template to validate.

        Returns
        -------
        ValidationResult
            Contains ``is_valid``, ``errors``, and ``warnings``.
        """
        result = ValidationResult(is_valid=True)
        logger.debug(f"Validating strategy: {template.name}")

        self._validate_indicators(template, result)
        self._validate_conditions(template, result)
        self._validate_risk(template, result)
        self._validate_sanity(template, result)

        if result.is_valid and not result.errors:
            logger.info(f"Strategy '{template.name}' is valid")
        else:
            logger.warning(
                f"Strategy '{template.name}' has {len(result.errors)} error(s) "
                f"and {len(result.warnings)} warning(s)"
            )

        return result

    # ------------------------------------------------------------------

    def _validate_indicators(
        self, template: StrategyTemplate, result: ValidationResult
    ) -> None:
        """Check indicator declarations and parameter ranges."""
        if not template.indicators:
            result.add_error("At least one indicator is required")
            return

        seen_names: Set[str] = set()
        for ind in template.indicators:
            col = ind.column_name()
            if col in seen_names:
                result.add_warning(f"Duplicate indicator column: {col}")
            seen_names.add(col)

            # Check RSI/MFI bounds.
            if ind.name in {
                IndicatorName.RSI,
                IndicatorName.MFI,
                IndicatorName.WILLIAMS_R,
            }:
                for p in ind.params:
                    if p.name == "period" and isinstance(p.value, (int, float)):
                        if p.value < 2 or p.value > 100:
                            result.add_warning(
                                f"{ind.name.value} period {p.value} is unusual"
                            )

            # Check MACD fast < slow.
            if ind.name == IndicatorName.MACD:
                params = {p.name: p.value for p in ind.params}
                if params.get("fast", 12) >= params.get("slow", 26):
                    result.add_error("MACD fast period must be less than slow period")

    def _validate_conditions(
        self, template: StrategyTemplate, result: ValidationResult
    ) -> None:
        """Ensure every column referenced in conditions exists in indicators."""
        declared = {ind.column_name() for ind in template.indicators}

        all_conditions = (
            template.entry_conditions.conditions + template.exit_conditions.conditions
        )

        if not all_conditions:
            result.add_error("At least one entry or exit condition is required")

        for cond in all_conditions:
            # Left side should be a declared indicator column.
            if cond.left not in declared:
                # Allow numeric literals on the left (unusual but valid).
                try:
                    float(cond.left)
                except ValueError:
                    result.add_warning(
                        f"Condition references unknown column: '{cond.left}'"
                    )

            # Right side should be a number or a declared column.
            try:
                float(cond.right)
            except ValueError:
                if cond.right not in declared:
                    result.add_warning(
                        f"Condition right-hand side unknown: '{cond.right}'"
                    )

    def _validate_risk(
        self, template: StrategyTemplate, result: ValidationResult
    ) -> None:
        """Check risk-parameter consistency."""
        risk = template.risk

        if risk.stop_loss_value <= 0:
            result.add_error("stop_loss_value must be positive")
        if risk.target_value <= 0:
            result.add_error("target_value must be positive")
        if risk.position_sizing_value <= 0:
            result.add_error("position_sizing_value must be positive")

        if risk.stop_loss_value >= risk.target_value:
            result.add_warning(
                "stop_loss_value >= target_value — risk/reward is <= 1:1"
            )

        if risk.stop_loss_value > 10 and risk.stop_loss_type == StopLossType.FIXED_PCT:
            result.add_warning(f"Stop loss of {risk.stop_loss_value}% is very wide")

    def _validate_sanity(
        self, template: StrategyTemplate, result: ValidationResult
    ) -> None:
        """Catch common logical mistakes."""
        # Entry == Exit conditions would cause instant close.
        entry_str = template.entry_conditions.to_python()
        exit_str = template.exit_conditions.to_python()
        if entry_str == exit_str:
            result.add_error(
                "Entry and exit conditions are identical — trades would "
                "close immediately"
            )

        # Ensure instrument is valid-looking.
        if not re.match(r"^[A-Z0-9&]+$", template.instrument):
            result.add_warning(
                f"Instrument '{template.instrument}' contains unusual characters"
            )


# ---------------------------------------------------------------------------
# Code Generator
# ---------------------------------------------------------------------------


class CodeGenerator:
    """Generate executable Python code from a validated :class:`StrategyTemplate`.

    The output is a self-contained module with a ``Strategy`` class that
    implements ``calculate_indicators(df)`` and ``generate_signals(df)``.
    It imports only ``pandas``, ``numpy``, and ``core.indicators``.
    """

    # Indicator function signatures from core.indicators.
    _SIGNATURES: Dict[IndicatorName, Tuple[str, ...]] = {
        IndicatorName.SMA: ("close",),
        IndicatorName.EMA: ("close",),
        IndicatorName.WMA: ("close",),
        IndicatorName.HMA: ("close",),
        IndicatorName.RSI: ("close",),
        IndicatorName.MACD: ("close",),
        IndicatorName.BB: ("close",),
        IndicatorName.ATR: ("high", "low", "close"),
        IndicatorName.VWAP: ("high", "low", "close", "volume"),
        IndicatorName.STOCHASTIC: ("high", "low", "close"),
        IndicatorName.ADX: ("high", "low", "close"),
        IndicatorName.OBV: ("close", "volume"),
        IndicatorName.CCI: ("high", "low", "close"),
        IndicatorName.MFI: ("high", "low", "close", "volume"),
        IndicatorName.SUPERTREND: ("high", "low", "close"),
        IndicatorName.PSAR: ("high", "low", "close"),
        IndicatorName.WILLIAMS_R: ("high", "low", "close"),
    }

    # Indicators that return multiple outputs.
    _MULTI_OUTPUT: Dict[IndicatorName, Tuple[str, ...]] = {
        IndicatorName.MACD: ("macd", "macd_signal", "macd_hist"),
        IndicatorName.BB: ("bb_upper", "bb_middle", "bb_lower"),
        IndicatorName.STOCHASTIC: ("stoch_k", "stoch_d"),
        IndicatorName.SUPERTREND: ("supertrend_upper", "supertrend_lower"),
    }

    def generate(self, template: StrategyTemplate) -> str:
        """Generate Python source code for *template*.

        Parameters
        ----------
        template:
            Validated strategy template.

        Returns
        -------
        str
            Complete Python module source as a string.
        """
        logger.info(f"Generating code for strategy: {template.name}")

        lines: List[str] = []
        lines.append('"""')
        lines.append(f"Auto-generated strategy: {template.name}")
        lines.append(f"Instrument : {template.instrument}")
        lines.append(f"Timeframe  : {template.timeframe}")
        lines.append(f"Description: {template.description}")
        lines.append('"""')
        lines.append("")

        # Imports
        lines.extend(
            [
                "from __future__ import annotations",
                "",
                "from typing import Optional",
                "",
                "import numpy as np",
                "import pandas as pd",
                "from loguru import logger",
                "",
                "from core import indicators as ind",
                "",
                "",
            ]
        )

        # Strategy class
        lines.append(f"class {self._to_class_name(template.name)}Strategy:")
        lines.append(f'    """{template.description or template.name}"""')
        lines.append("")

        # Class constants
        lines.append(f'    INSTRUMENT: str = "{template.instrument}"')
        lines.append(f'    TIMEFRAME: str = "{template.timeframe}"')
        lines.append("")

        # __init__
        lines.extend(
            [
                "    def __init__(self) -> None:",
                "        pass",
                "",
            ]
        )

        # calculate_indicators
        lines.append(
            "    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:"
        )
        lines.append('        """Add all strategy-specific indicator columns."""')
        lines.append("        result = df.copy()")
        lines.append("")

        for ind_ref in template.indicators:
            assign = self._indicator_assignment(ind_ref)
            lines.append(f"        {assign}")

        lines.append("        return result")
        lines.append("")

        # generate_signals
        lines.append(
            "    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:"
        )
        lines.append('        """')
        lines.append("        Returns a DataFrame with ``signal`` column:")
        lines.append("        1 = entry, -1 = exit, 0 = hold.")
        lines.append('        """')
        lines.append("        df = self.calculate_indicators(df)")
        lines.append("        signals = pd.Series(0, index=df.index, dtype=int)")
        lines.append("")

        # Entry
        entry_expr = template.entry_conditions.to_python()
        lines.append("        # Entry conditions")
        lines.append(f"        entry_mask = {entry_expr}")
        lines.append("        signals.loc[entry_mask] = 1")
        lines.append("")

        # Exit
        exit_expr = template.exit_conditions.to_python()
        lines.append("        # Exit conditions")
        lines.append(f"        exit_mask = {exit_expr}")
        lines.append("        signals.loc[exit_mask] = -1")
        lines.append("")

        lines.append("        df = df.copy()")
        lines.append("        df['signal'] = signals")
        lines.append(
            "        logger.debug(f'Signals generated: {(signals != 0).sum()} events')"
        )
        lines.append("        return df")
        lines.append("")

        # Position sizing helper
        lines.extend(self._position_sizing_code(template.risk))

        # Risk helpers
        lines.extend(self._risk_helpers_code(template.risk))

        code = "\n".join(lines)
        logger.debug(f"Generated {len(code)} characters of strategy code")
        return code

    # ------------------------------------------------------------------

    def _to_class_name(self, name: str) -> str:
        """Convert snake_case strategy name to PascalCase class name."""
        parts = name.split("_")
        return "".join(p.capitalize() for p in parts if p)

    def _indicator_assignment(self, ind_ref: IndicatorRef) -> str:
        """Generate a Python assignment statement for an indicator call."""
        func_name = ind_ref.name.value
        sig = self._SIGNATURES.get(ind_ref.name, ("close",))
        args: List[str] = []
        kwargs: Dict[str, Any] = {}

        # Map positional arguments.
        for col in sig:
            args.append(f'result["{col}"]')

        # Add keyword parameters.
        for p in ind_ref.params:
            kwargs[p.name] = p.value

        kw_str = ", ".join(f"{k}={v}" for k, v in kwargs.items())
        call_args = ", ".join(args)
        if kw_str:
            call_args = f"{call_args}, {kw_str}"

        # Handle multi-output indicators.
        if ind_ref.name in self._MULTI_OUTPUT:
            outputs = self._MULTI_OUTPUT[ind_ref.name]
            return f'{", ".join(outputs)} = ind.{func_name}({call_args})'

        col_name = ind_ref.column_name()
        return f'result["{col_name}"] = ind.{func_name}({call_args})'

    def _position_sizing_code(self, risk: RiskParams) -> List[str]:
        """Generate position-sizing helper method."""
        lines: List[str] = []
        lines.append("    def calculate_position_size(")
        lines.append("        self,")
        lines.append("        capital: float,")
        lines.append("        entry_price: float,")
        lines.append("        stop_loss_price: Optional[float] = None,")
        lines.append("    ) -> int:")
        lines.append('        """Calculate quantity based on risk configuration."""')

        if risk.position_sizing_type == PositionSizingType.FIXED_QTY:
            lines.append(f"        return {int(risk.position_sizing_value)}")
        elif risk.position_sizing_type == PositionSizingType.PCT_CAPITAL:
            lines.append(
                f"        risk_amount = capital * {risk.position_sizing_value / 100.0}"
            )
            lines.append("        qty = int(risk_amount / entry_price)")
            lines.append("        return max(qty, 1)")
        else:  # risk_based
            lines.append("        if stop_loss_price is None:")
            lines.append(
                f"            stop_loss_price = entry_price * (1 - {risk.stop_loss_value / 100.0})"
            )
            lines.append("        risk_per_share = abs(entry_price - stop_loss_price)")
            lines.append(
                f"        risk_amount = capital * {risk.position_sizing_value / 100.0}"
            )
            lines.append(
                "        qty = int(risk_amount / risk_per_share) if risk_per_share > 0 else 1"
            )
            lines.append("        return max(qty, 1)")

        lines.append("")
        return lines

    def _risk_helpers_code(self, risk: RiskParams) -> List[str]:
        """Generate stop-loss and target helper methods."""
        lines: List[str] = []

        # Stop loss
        lines.append("    def calculate_stop_loss(")
        lines.append("        self,")
        lines.append("        entry_price: float,")
        lines.append("        direction: str = 'buy',")
        lines.append("        atr_value: Optional[float] = None,")
        lines.append("    ) -> float:")
        lines.append('        """Compute stop-loss price for a trade."""')

        if risk.stop_loss_type == StopLossType.FIXED_PCT:
            lines.append(f"        sl_pct = {risk.stop_loss_value / 100.0}")
            lines.append("        if direction == 'buy':")
            lines.append("            return entry_price * (1 - sl_pct)")
            lines.append("        return entry_price * (1 + sl_pct)")
        elif risk.stop_loss_type == StopLossType.ATR_BASED:
            lines.append(f"        multiplier = {risk.stop_loss_value}")
            lines.append(
                "        atr_v = atr_value if atr_value is not None else entry_price * 0.01"
            )
            lines.append("        if direction == 'buy':")
            lines.append("            return entry_price - multiplier * atr_v")
            lines.append("        return entry_price + multiplier * atr_v")
        else:  # trailing
            lines.append("        # Trailing stop: caller manages update logic")
            lines.append(
                f"        return entry_price * (1 - {risk.stop_loss_value / 100.0})"
            )

        lines.append("")

        # Target
        lines.append("    def calculate_target(")
        lines.append("        self,")
        lines.append("        entry_price: float,")
        lines.append("        direction: str = 'buy',")
        lines.append("        atr_value: Optional[float] = None,")
        lines.append("    ) -> float:")
        lines.append('        """Compute target price for a trade."""')

        if risk.target_type == TargetType.FIXED_PCT:
            lines.append(f"        tgt_pct = {risk.target_value / 100.0}")
            lines.append("        if direction == 'buy':")
            lines.append("            return entry_price * (1 + tgt_pct)")
            lines.append("        return entry_price * (1 - tgt_pct)")
        elif risk.target_type == TargetType.ATR_BASED:
            lines.append(f"        multiplier = {risk.target_value}")
            lines.append(
                "        atr_v = atr_value if atr_value is not None else entry_price * 0.01"
            )
            lines.append("        if direction == 'buy':")
            lines.append("            return entry_price + multiplier * atr_v")
            lines.append("        return entry_price - multiplier * atr_v")
        else:
            lines.append(
                f"        return entry_price * (1 + {risk.target_value / 100.0})"
            )

        lines.append("")
        return lines


# ---------------------------------------------------------------------------
# Convenience pipeline function
# ---------------------------------------------------------------------------


def parse_and_generate(prompt: str) -> Tuple[StrategyTemplate, str]:
    """End-to-end pipeline: NL prompt → StrategyTemplate → Python code.

    Parameters
    ----------
    prompt:
        Natural-language strategy description.

    Returns
    -------
    tuple[StrategyTemplate, str]
        The parsed template and generated Python source code.

    Raises
    ------
    ValueError
        If the prompt is empty or the template fails validation.
    """
    parser = NLParser()
    validator = StrategyValidator()
    generator = CodeGenerator()

    template = parser.parse(prompt)
    result = validator.validate(template)

    if result.errors:
        err_msg = "; ".join(result.errors)
        raise ValueError(f"Strategy validation failed: {err_msg}")

    for w in result.warnings:
        logger.warning(f"Strategy warning: {w}")

    code = generator.generate(template)
    return template, code
