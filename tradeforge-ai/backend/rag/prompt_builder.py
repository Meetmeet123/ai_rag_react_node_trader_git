"""
RAG-Augmented Prompt Builder for TradeForge AI

Constructs LLM prompts enriched with retrieved context from the RAG
pipeline.  Uses Jinja2 templates for flexible, maintainable formatting.

Supported prompt types:
* **strategy_generation** – create a new trading strategy with market context
* **strategy_improvement** – refine an existing strategy using backtest data
* **backtest_analysis** – interpret backtest results
* **market_analysis** – analyse current market conditions
* **risk_assessment** – evaluate risk factors for a position or strategy

Each template is carefully designed to present retrieved context in a
structured way that helps the LLM generate accurate, actionable output.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from jinja2 import BaseLoader, Environment, Template
from loguru import logger

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

# Strategy generation – the most important template
_STRATEGY_GENERATION_TEMPLATE = """You are TradeForge AI, an expert quantitative trading strategist specialising in Indian equity markets (NSE / BSE).

## User Request
{{ user_prompt }}

## Target Instrument
{{ instrument }} ({% if segment %}{{ segment }}{% else %}equity{% endif %})

## Similar Successful Strategies (from database)
{% for strategy in similar_strategies %}
### Strategy {{ loop.index }}: {{ strategy.name }}
- Description: {{ strategy.description }}
- Instrument: {{ strategy.instrument }} | Timeframe: {{ strategy.timeframe }}
- Entry: {{ strategy.entry_conditions | join('; ') }}
- Exit: {{ strategy.exit_conditions | join('; ') }}
- Performance: {{ strategy.win_rate }}% win rate{% if strategy.pnl %}, Rs.{{ strategy.pnl }} P&L{% endif %}{% if strategy.sharpe %}, Sharpe {{ strategy.sharpe }}{% endif %}
{% endfor %}
{% if not similar_strategies %}
(No similar strategies found in the database.)
{% endif %}

## Current Market Context
{% for ctx in market_context %}
- {{ ctx }}
{% endfor %}
{% if not market_context %}
(No recent market context available.)
{% endif %}

## Recent News
{% for news in recent_news %}
- {{ news.title }}{% if news.time_ago %} ({{ news.time_ago }}){% endif %}: {{ news.summary }}
{% endfor %}
{% if not recent_news %}
(No recent news for this instrument.)
{% endif %}

## Technical Indicator Reference
{% for ind in indicator_context %}
- {{ ind.name }}: {{ ind.description }}{% if ind.best_for %}. Best used for: {{ ind.best_for }}{% endif %}
{% endfor %}
{% if not indicator_context %}
(No indicator references retrieved.)
{% endif %}

## Backtest Insights
{% for bt in backtest_insights %}
- {{ bt.strategy_name }} on {{ bt.symbol }}: {{ bt.win_rate }}% WR, Rs.{{ bt.pnl }} P&L{% if bt.sharpe %}, Sharpe {{ bt.sharpe }}{% endif %}
{% endfor %}
{% if not backtest_insights %}
(No backtest data available.)
{% endif %}

---

## Instructions
Generate a complete trading strategy in **valid JSON format** with the following structure:

```json
{
  "strategy_name": "<descriptive name>",
  "description": "<detailed description of the strategy logic>",
  "instrument": "{{ instrument }}",
  "segment": "{% if segment %}{{ segment }}{% else %}equity{% endif %}",
  "timeframe": "<e.g., 15m, 1h, 1d>",
  "entry_conditions": [
    {"indicator": "<name>", "period": <int>, "condition": "<e.g., crosses_above>", "value": <float>}
  ],
  "exit_conditions": [
    {"indicator": "<name>", "period": <int>, "condition": "<e.g., crosses_below>", "value": <float>}
  ],
  "stop_loss": {"type": "<fixed|atr_based|percentage>", "value": <float>, "trailing": <bool>},
  "target": {"type": "<fixed|atr_based|rrr_based>", "value": <float>, "rrr": <float|null>},
  "position_sizing": {"type": "<fixed_quantity|capital_percentage|risk_based>", "value": <float>},
  "rationale": "<why this strategy fits current market conditions>"
}
```

IMPORTANT:
- Return ONLY valid JSON. No markdown code fences around the JSON.
- Consider the current market regime when designing entry/exit rules.
- Use the indicator reference to choose appropriate indicators.
- If similar strategies exist, learn from their strengths and avoid their weaknesses.
- The strategy must be suitable for Indian markets (NSE/BSE).
- Include a clear rationale explaining why this strategy fits the current market.
"""

# Strategy improvement – refine an existing strategy
_STRATEGY_IMPROVEMENT_TEMPLATE = """You are TradeForge AI, a quantitative trading strategy optimiser.

## Current Strategy
Name: {{ strategy_name }}
Description: {{ strategy_description }}

## Current Rules
Entry: {{ entry_conditions | join('; ') }}
Exit: {{ exit_conditions | join('; ') }}
Stop Loss: {{ stop_loss }}
Target: {{ target }}

## Backtest Results
{{ backtest_summary }}

## Similar Strategy Performance
{% for s in similar_backtests %}
- {{ s.name }}: {{ s.win_rate }}% WR, Rs.{{ s.pnl }} P&L, Sharpe {{ s.sharpe }}
{% endfor %}

## Current Market Context
{% for ctx in market_context %}
- {{ ctx }}
{% endfor %}

## Instructions
Analyse the current strategy and provide specific, actionable improvements:

1. What are the top 3 weaknesses of this strategy?
2. What parameter changes would improve performance?
3. Should any conditions be added or removed?
4. How should risk management (stop loss / target) be adjusted?
5. Is this strategy suitable for the current market regime? If not, what changes are needed?

Provide your analysis in structured JSON format:

```json
{
  "weaknesses": ["<weakness 1>", "<weakness 2>", "<weakness 3>"],
  "parameter_changes": {"<param>": "<suggested value and reason>"},
  "condition_changes": {"add": [], "remove": [], "modify": []},
  "risk_management_changes": {"stop_loss": "<change>", "target": "<change>"},
  "market_regime_fit": "<assessment and recommendation>",
  "overall_recommendation": "<summary>"
}
```

Return ONLY valid JSON.
"""

# Backtest analysis
_BACKTEST_ANALYSIS_TEMPLATE = """You are TradeForge AI, an expert quantitative trading analyst.

## Backtest Summary
Strategy: {{ strategy_name }}
Symbol: {{ symbol }}
Period: {{ start_date }} to {{ end_date }}

### Key Metrics
- Total Trades: {{ metrics.total_trades }}
- Win Rate: {{ metrics.win_rate }}%
- P&L: Rs.{{ metrics.total_pnl }}
- Profit Factor: {{ metrics.profit_factor }}
- Sharpe Ratio: {{ metrics.sharpe_ratio }}
- Max Drawdown: {{ metrics.max_drawdown_pct }}%
- Average Profit: Rs.{{ metrics.avg_profit }}
- Average Loss: Rs.{{ metrics.avg_loss }}
- Best Trade: Rs.{{ metrics.best_trade }}
- Worst Trade: Rs.{{ metrics.worst_trade }}

### Monthly Returns
{% for month, ret in monthly_returns.items() %}
- {{ month }}: {{ ret }}%
{% endfor %}

## Similar Strategy Performance
{% for s in similar_backtests %}
- {{ s.name }}: {{ s.win_rate }}% WR, Rs.{{ s.pnl }} P&L, Sharpe {{ s.sharpe }}
{% endfor %}

## Market Conditions During Test Period
{% for ctx in market_conditions %}
- {{ ctx }}
{% endfor %}

## Instructions
Provide a comprehensive analysis in valid JSON:

```json
{
  "strengths": ["<strength 1>", "<strength 2>"],
  "weaknesses": ["<weakness 1>", "<weakness 2>"],
  "key_risks": ["<risk 1>", "<risk 2>"],
  "improvements": ["<improvement 1>", "<improvement 2>"],
  "live_readiness": "<READY / NEEDS_IMPROVEMENT / NOT_READY>",
  "live_readiness_score": <0-100>,
  "confidence": "<HIGH / MEDIUM / LOW>",
  "monthly_analysis": "<observations about monthly consistency>",
  "recommendation": "<final recommendation>"
}
```

Return ONLY valid JSON.
"""

# Market analysis
_MARKET_ANALYSIS_TEMPLATE = """You are TradeForge AI, a senior market analyst for Indian equities.

## Analysis Request
Symbol: {{ symbol }}
Date: {{ analysis_date }}

## Price Action
{{ price_action }}

## Technical Indicators
{{ indicators }}

## Recent News
{% for news in news_items %}
- {{ news.title }}: {{ news.summary }}
{% endfor %}

## Similar Historical Periods
{% for period in historical_similarities %}
- {{ period.date }}: {{ period.regime }} ({{ period.description }})
{% endfor %}

## Instructions
Provide a comprehensive market analysis in valid JSON:

```json
{
  "market_regime": "<trending_up / trending_down / ranging / volatile / breakout / reversal>",
  "regime_confidence": <0-100>,
  "key_levels": {
    "support": [<levels>],
    "resistance": [<levels>]
  },
  "probable_direction": "<bullish / bearish / neutral>",
  "direction_confidence": <0-100>,
  "risks": ["<risk 1>", "<risk 2>"],
  "opportunities": ["<opportunity 1>", "<opportunity 2>"],
  "recommended_strategies": ["<strategy type 1>", "<strategy type 2>"],
  "outlook": "<1-2 paragraph summary>"
}
```

Return ONLY valid JSON.
"""

# Risk assessment
_RISK_ASSESSMENT_TEMPLATE = """You are TradeForge AI, a risk management specialist for algorithmic trading.

## Position / Strategy to Assess
{% if strategy_name %}Strategy: {{ strategy_name }}{% endif %}
{% if symbol %}Symbol: {{ symbol }}{% endif %}
{% if position_size %}Position Size: {{ position_size }}{% endif %}

## Strategy Rules
{{ strategy_rules }}

## Current Market Context
{% for ctx in market_context %}
- {{ ctx }}
{% endfor %}

## Recent Market Events
{% for event in recent_events %}
- {{ event.title }}: {{ event.summary }}
{% endfor %}

## Historical Risk Context
{% for hist in historical_risks %}
- {{ hist.date }}: {{ hist.event }} (impact: {{ hist.impact }})
{% endfor %}

## Instructions
Assess the risk profile and provide a structured risk report in valid JSON:

```json
{
  "overall_risk_level": "<LOW / MEDIUM / HIGH / EXTREME>",
  "risk_score": <0-100>,
  "market_risks": ["<risk 1>", "<risk 2>"],
  "strategy_risks": ["<risk 1>", "<risk 2>"],
  "position_risks": ["<risk 1>", "<risk 2>"],
  "event_risks": ["<risk 1>", "<risk 2>"],
  "mitigation_strategies": ["<strategy 1>", "<strategy 2>"],
  "max_advised_position": "<position size recommendation>",
  "stop_loss_recommendation": "<SL recommendation>",
  "key_warnings": ["<warning 1>", "<warning 2>"],
  "risk_reward_assessment": "<assessment>"
}
```

Return ONLY valid JSON.
"""

# Quick strategy summary (for UI display)
_STRATEGY_SUMMARY_TEMPLATE = """## Strategy Summary

**Name:** {{ strategy_name }}
**Instrument:** {{ instrument }}
**Timeframe:** {{ timeframe }}

### Entry Rules
{% for rule in entry_conditions %}
{{ loop.index }}. {{ rule }}
{% endfor %}

### Exit Rules
{% for rule in exit_conditions %}
{{ loop.index }}. {{ rule }}
{% endfor %}

### Risk Management
- Stop Loss: {{ stop_loss }}
- Target: {{ target }}
- Position Sizing: {{ position_sizing }}

### Expected Performance
{% if win_rate %}- Win Rate: {{ win_rate }}%
{% endif %}{% if expectancy %}- Expectancy: Rs.{{ expectancy }}
{% endif %}{% if sharpe %}- Sharpe Ratio: {{ sharpe }}
{% endif %}{% if max_drawdown %}- Max Drawdown: {{ max_drawdown }}%
{% endif %}
"""


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------


class RAGPromptBuilder:
    """Builds LLM prompts enriched with RAG-retrieved context.

    The builder maintains a registry of Jinja2 templates.  Each template
    receives structured context data and produces a complete prompt string
    ready to be sent to an LLM API.

    Parameters
    ----------
        (none – all configuration is embedded in the templates)

    Example
    -------
    >>> builder = RAGPromptBuilder()
    >>> prompt = builder.build_strategy_prompt(
    ...     user_prompt="RSI mean reversion",
    ...     instrument="NIFTY50",
    ...     retrieved_context=context_dict,
    ... )
    >>> print(prompt[:200])
    """

    # Template registry
    TEMPLATE_STRATEGY_GENERATION: str = _STRATEGY_GENERATION_TEMPLATE
    TEMPLATE_STRATEGY_IMPROVEMENT: str = _STRATEGY_IMPROVEMENT_TEMPLATE
    TEMPLATE_BACKTEST_ANALYSIS: str = _BACKTEST_ANALYSIS_TEMPLATE
    TEMPLATE_MARKET_ANALYSIS: str = _MARKET_ANALYSIS_TEMPLATE
    TEMPLATE_RISK_ASSESSMENT: str = _RISK_ASSESSMENT_TEMPLATE
    TEMPLATE_STRATEGY_SUMMARY: str = _STRATEGY_SUMMARY_TEMPLATE

    def __init__(self) -> None:
        self._env = Environment(
            loader=BaseLoader(), trim_blocks=True, lstrip_blocks=True
        )
        self.templates: Dict[str, Template] = {
            "strategy_generation": self._env.from_string(
                self.TEMPLATE_STRATEGY_GENERATION
            ),
            "strategy_improvement": self._env.from_string(
                self.TEMPLATE_STRATEGY_IMPROVEMENT
            ),
            "backtest_analysis": self._env.from_string(self.TEMPLATE_BACKTEST_ANALYSIS),
            "market_analysis": self._env.from_string(self.TEMPLATE_MARKET_ANALYSIS),
            "risk_assessment": self._env.from_string(self.TEMPLATE_RISK_ASSESSMENT),
            "strategy_summary": self._env.from_string(self.TEMPLATE_STRATEGY_SUMMARY),
        }

    # ===================================================================
    # Strategy prompts
    # ===================================================================

    def build_strategy_prompt(
        self,
        user_prompt: str,
        instrument: str,
        retrieved_context: Dict[str, List[Dict[str, Any]]],
        segment: str = "equity",
    ) -> str:
        """Build a RAG-augmented strategy generation prompt.

        Parameters
        ----------
        user_prompt:
            Original user query or strategy idea.
        instrument:
            Target instrument (e.g. ``"NIFTY50"``).
        retrieved_context:
            Output from ``MultiSourceRetriever.retrieve_for_strategy_generation()``.
            Expected keys: ``similar_strategies``, ``market_context``,
            ``recent_news``, ``indicator_explanations``, ``backtest_insights``.
        segment:
            Market segment (``"equity"``, ``"futures"``, ``"options"``).

        Returns
        -------
        str
            Complete prompt string with injected RAG context.
        """
        # Normalise context lists
        similar = self._normalise_list(retrieved_context.get("similar_strategies", []))
        market = self._normalise_list(retrieved_context.get("market_context", []))
        news = self._normalise_list(retrieved_context.get("recent_news", []))
        indicators = self._normalise_list(
            retrieved_context.get("indicator_explanations", [])
        )
        backtests = self._normalise_list(retrieved_context.get("backtest_insights", []))

        # Format for template consumption
        formatted_strategies = self._format_strategies(similar)
        formatted_market = self._format_market_context(market)
        formatted_news = self._format_news(news)
        formatted_indicators = self._format_indicators(indicators)
        formatted_backtests = self._format_backtests(backtests)

        template = self.templates["strategy_generation"]
        prompt = template.render(
            user_prompt=user_prompt,
            instrument=instrument,
            segment=segment,
            similar_strategies=formatted_strategies,
            market_context=formatted_market,
            recent_news=formatted_news,
            indicator_context=formatted_indicators,
            backtest_insights=formatted_backtests,
        )

        logger.info(
            f"Built strategy prompt: {len(prompt)} chars, instrument={instrument}"
        )
        return prompt

    def build_strategy_improvement_prompt(
        self,
        strategy_name: str,
        strategy_description: str,
        entry_conditions: List[str],
        exit_conditions: List[str],
        stop_loss: Dict[str, Any],
        target: Dict[str, Any],
        backtest_summary: str,
        retrieved_context: Dict[str, List[Dict[str, Any]]],
    ) -> str:
        """Build a prompt for improving an existing strategy.

        Parameters
        ----------
        strategy_name:
            Name of the strategy to improve.
        strategy_description:
            Current description.
        entry_conditions:
            List of entry rule strings.
        exit_conditions:
            List of exit rule strings.
        stop_loss:
            Dict with ``type``, ``value``, ``trailing`` keys.
        target:
            Dict with ``type``, ``value``, ``rrr`` keys.
        backtest_summary:
            Human-readable backtest summary.
        retrieved_context:
            Context from retriever with keys ``similar_backtests``,
            ``market_context``.

        Returns
        -------
        str
            Complete improvement prompt.
        """
        similar_bts = self._normalise_list(
            retrieved_context.get("similar_backtests", [])
        )
        market_ctx = self._normalise_list(retrieved_context.get("market_context", []))

        template = self.templates["strategy_improvement"]
        prompt = template.render(
            strategy_name=strategy_name,
            strategy_description=strategy_description,
            entry_conditions=entry_conditions,
            exit_conditions=exit_conditions,
            stop_loss=json.dumps(stop_loss),
            target=json.dumps(target),
            backtest_summary=backtest_summary,
            similar_backtests=similar_bts,
            market_context=[ctx.get("content", str(ctx)) for ctx in market_ctx],
        )

        logger.info(
            f"Built improvement prompt for strategy '{strategy_name}': {len(prompt)} chars"
        )
        return prompt

    # ===================================================================
    # Analysis prompts
    # ===================================================================

    def build_backtest_analysis_prompt(
        self,
        backtest_results: Dict[str, Any],
        retrieved_context: Dict[str, List[Dict[str, Any]]],
    ) -> str:
        """Build a prompt for backtest result analysis.

        Parameters
        ----------
        backtest_results:
            Dict with keys: ``strategy_name``, ``symbol``, ``start_date``,
            ``end_date``, ``metrics`` (dict), ``monthly_returns`` (dict).
        retrieved_context:
            Context with keys ``similar_backtests``, ``market_conditions``.

        Returns
        -------
        str
            Complete backtest analysis prompt.
        """
        metrics = backtest_results.get("metrics", {})
        similar_bts = self._normalise_list(
            retrieved_context.get("similar_backtests", [])
        )
        market_ctx = self._normalise_list(
            retrieved_context.get("market_conditions", [])
        )

        template = self.templates["backtest_analysis"]
        prompt = template.render(
            strategy_name=backtest_results.get("strategy_name", "Unknown"),
            symbol=backtest_results.get("symbol", ""),
            start_date=backtest_results.get("start_date", ""),
            end_date=backtest_results.get("end_date", ""),
            metrics=metrics,
            monthly_returns=backtest_results.get("monthly_returns", {}),
            similar_backtests=similar_bts,
            market_conditions=[ctx.get("content", str(ctx)) for ctx in market_ctx],
        )

        logger.info(f"Built backtest analysis prompt: {len(prompt)} chars")
        return prompt

    def build_market_analysis_prompt(
        self,
        symbol: str,
        price_action: str,
        indicators: str,
        retrieved_context: Dict[str, List[Dict[str, Any]]],
    ) -> str:
        """Build a prompt for market condition analysis.

        Parameters
        ----------
        symbol:
            Symbol being analysed.
        price_action:
            Description of recent price movement.
        indicators:
            Description of current indicator readings.
        retrieved_context:
            Context with keys ``news``, ``historical_similarities``.

        Returns
        -------
        str
            Complete market analysis prompt.
        """
        news = self._normalise_list(retrieved_context.get("news", []))
        historical = self._normalise_list(
            retrieved_context.get("historical_similarities", [])
        )

        template = self.templates["market_analysis"]
        prompt = template.render(
            symbol=symbol,
            analysis_date=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            price_action=price_action,
            indicators=indicators,
            news_items=news,
            historical_similarities=historical,
        )

        logger.info(f"Built market analysis prompt for {symbol}: {len(prompt)} chars")
        return prompt

    def build_risk_assessment_prompt(
        self,
        strategy_rules: str,
        retrieved_context: Dict[str, List[Dict[str, Any]]],
        strategy_name: Optional[str] = None,
        symbol: Optional[str] = None,
        position_size: Optional[str] = None,
    ) -> str:
        """Build a prompt for risk assessment.

        Parameters
        ----------
        strategy_rules:
            Description of the strategy rules to assess.
        retrieved_context:
            Context with keys ``market_context``, ``recent_events``,
            ``historical_risks``.
        strategy_name:
            Optional strategy name.
        symbol:
            Optional symbol.
        position_size:
            Optional position size description.

        Returns
        -------
        str
            Complete risk assessment prompt.
        """
        market_ctx = self._normalise_list(retrieved_context.get("market_context", []))
        events = self._normalise_list(retrieved_context.get("recent_events", []))
        hist_risks = self._normalise_list(retrieved_context.get("historical_risks", []))

        template = self.templates["risk_assessment"]
        prompt = template.render(
            strategy_name=strategy_name or "Unnamed Strategy",
            symbol=symbol or "",
            position_size=position_size or "",
            strategy_rules=strategy_rules,
            market_context=[ctx.get("content", str(ctx)) for ctx in market_ctx],
            recent_events=events,
            historical_risks=hist_risks,
        )

        logger.info(f"Built risk assessment prompt: {len(prompt)} chars")
        return prompt

    def build_strategy_summary_prompt(
        self,
        strategy: Dict[str, Any],
    ) -> str:
        """Build a human-readable strategy summary (not for LLM, for UI).

        Parameters
        ----------
        strategy:
            Strategy dict with all relevant fields.

        Returns
        -------
        str
            Markdown-formatted summary.
        """
        template = self.templates["strategy_summary"]
        prompt = template.render(
            strategy_name=strategy.get("name", "Unnamed"),
            instrument=strategy.get("instrument", ""),
            timeframe=strategy.get("timeframe", ""),
            entry_conditions=strategy.get("entry_conditions", []),
            exit_conditions=strategy.get("exit_conditions", []),
            stop_loss=strategy.get("stop_loss", {}),
            target=strategy.get("target", {}),
            position_sizing=strategy.get("position_sizing", {}),
            win_rate=strategy.get("win_rate"),
            expectancy=strategy.get("expectancy"),
            sharpe=strategy.get("sharpe_ratio"),
            max_drawdown=strategy.get("max_drawdown"),
        )
        return prompt

    # ===================================================================
    # Generic builder
    # ===================================================================

    def build_prompt(
        self,
        template_type: str,
        **kwargs: Any,
    ) -> str:
        """Build a prompt from a named template.

        Parameters
        ----------
        template_type:
            One of the registered template names.
        **kwargs:
            Template variables.

        Returns
        -------
        str
            Rendered prompt.

        Raises
        ------
        ValueError
            If *template_type* is not recognised.
        """
        if template_type not in self.templates:
            available = ", ".join(self.templates.keys())
            raise ValueError(
                f"Unknown template '{template_type}'. Available: {available}"
            )

        template = self.templates[template_type]
        return template.render(**kwargs)

    # ===================================================================
    # Formatting helpers
    # ===================================================================

    @staticmethod
    def _format_strategies(strategies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalise strategy context objects for the template."""
        formatted = []
        for s in strategies:
            if isinstance(s, RetrievedContext_placeholder):
                s = {"content": s.content, **s.metadata}

            content = s.get("content", "")
            # Parse content if it's a raw string from vector store
            formatted.append(
                {
                    "name": s.get("name", s.get("strategy_name", "Unknown Strategy")),
                    "description": s.get("description", content[:200]),
                    "instrument": s.get("instrument", ""),
                    "timeframe": s.get("timeframe", ""),
                    "entry_conditions": s.get("entry_conditions", []),
                    "exit_conditions": s.get("exit_conditions", []),
                    "win_rate": s.get("win_rate", s.get("win_rate_pct", "N/A")),
                    "pnl": s.get("total_pnl", s.get("pnl", "N/A")),
                    "sharpe": s.get("sharpe_ratio", s.get("sharpe", "N/A")),
                }
            )
        return formatted

    @staticmethod
    def _format_market_context(contexts: List[Dict[str, Any]]) -> List[str]:
        """Extract readable strings from market context objects."""
        formatted = []
        for ctx in contexts:
            if isinstance(ctx, str):
                formatted.append(ctx)
            elif isinstance(ctx, dict):
                content = ctx.get("content", "")
                if content:
                    formatted.append(content)
                else:
                    # Build from metadata
                    parts = []
                    for k, v in ctx.items():
                        if k not in ("content", "metadata", "embedding", "score") and v:
                            parts.append(f"{k}: {v}")
                    formatted.append(" | ".join(parts))
            elif hasattr(ctx, "content"):
                formatted.append(ctx.content)
        return formatted

    @staticmethod
    def _format_news(news_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalise news context objects for the template."""
        formatted = []
        for n in news_items:
            if isinstance(n, RetrievedContext_placeholder):
                n = {"content": n.content, **n.metadata}

            formatted.append(
                {
                    "title": n.get("title", "Untitled"),
                    "summary": n.get("summary", n.get("content", "")[:300]),
                    "time_ago": n.get("time_ago", n.get("published_at", "")),
                    "source": n.get("source", ""),
                }
            )
        return formatted

    @staticmethod
    def _format_indicators(indicators: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalise indicator context objects for the template."""
        formatted = []
        for ind in indicators:
            if isinstance(ind, RetrievedContext_placeholder):
                ind = {"content": ind.content, **ind.metadata}

            formatted.append(
                {
                    "name": ind.get("name", "Unknown"),
                    "description": ind.get("description", ind.get("content", "")[:200]),
                    "best_for": ind.get("best_for", ind.get("category", "")),
                }
            )
        return formatted

    @staticmethod
    def _format_backtests(backtests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalise backtest context objects for the template."""
        formatted = []
        for bt in backtests:
            if isinstance(bt, RetrievedContext_placeholder):
                bt = {"content": bt.content, **bt.metadata}

            formatted.append(
                {
                    "strategy_name": bt.get("strategy_name", bt.get("name", "Unknown")),
                    "symbol": bt.get("symbol", ""),
                    "win_rate": bt.get("win_rate", "N/A"),
                    "pnl": bt.get("total_pnl", bt.get("pnl", "N/A")),
                    "sharpe": bt.get("sharpe_ratio", bt.get("sharpe", "N/A")),
                }
            )
        return formatted

    @staticmethod
    def _normalise_list(items: Any) -> List[Dict[str, Any]]:
        """Ensure items is a list of dicts."""
        if items is None:
            return []
        if isinstance(items, list):
            return items
        return [items]


# ---------------------------------------------------------------------------
# Placeholder to handle RetrievedContext objects without circular imports
# ---------------------------------------------------------------------------


class RetrievedContext_placeholder:
    """Minimal stand-in for ``retriever.RetrievedContext`` to avoid
    circular imports during formatting.  We use duck-typing: anything
    with ``.content`` and ``.metadata`` attributes works."""

    def __init__(self, content: str = "", metadata: Optional[Dict] = None):
        self.content = content
        self.metadata = metadata or {}
