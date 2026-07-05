"""
LLM API Routes

- POST /generate-strategy -- Convert NL to strategy
- POST /chat -- AI chat assistant
- POST /explain-strategy -- Explain strategy in plain language
- POST /analyze-backtest -- Analyze backtest results
- POST /parse-strategy -- Parse NL prompt to structured strategy template
- GET /health -- LLM engine health check
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from loguru import logger
from sqlalchemy.orm import Session

from database.connection import get_db_session
from core.llm_engine import LLMEngine, StrategyOutput
from core.strategy_parser import NLParser, CodeGenerator, StrategyValidator

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class StrategyPromptRequest(BaseModel):
    """Request body for strategy generation from natural language."""

    prompt: str = Field(..., min_length=1, description="Natural language trading idea")
    instrument: str = Field(default="NIFTY50", description="Trading instrument")
    segment: str = Field(default="equity", description="Market segment")
    timeframe: str = Field(default="15m", description="Candle timeframe")


class ChatRequest(BaseModel):
    """Request body for AI chat assistant."""

    message: str = Field(..., min_length=1, description="User message")
    context: Optional[List[Dict[str, str]]] = Field(
        default=None, description="Previous conversation turns"
    )


class ExplainStrategyRequest(BaseModel):
    """Request body for strategy explanation."""

    strategy: Dict[str, Any] = Field(..., description="Strategy definition dict")


class AnalyzeBacktestRequest(BaseModel):
    """Request body for backtest analysis."""

    results: Dict[str, Any] = Field(..., description="Backtest results dictionary")


class ParseStrategyRequest(BaseModel):
    """Request body for NL -> structured strategy parsing."""

    prompt: str = Field(..., min_length=1, description="Natural language prompt")


class StrategyResponse(BaseModel):
    """Full strategy response with generated code."""

    strategy: Dict[str, Any] = Field(..., description="Structured strategy definition")
    confidence: float = Field(..., description="LLM confidence score 0.0-1.0")
    reasoning: str = Field(..., description="Chain-of-thought reasoning")
    generated_code: str = Field(..., description="Auto-generated Python strategy code")


class ChatResponse(BaseModel):
    """Chat assistant response."""

    response: str = Field(..., description="AI assistant reply")
    model_loaded: bool = Field(default=False, description="Whether LLM model is loaded")


class ParseStrategyResponse(BaseModel):
    """Parsed strategy template response."""

    name: str = Field(..., description="Strategy name")
    description: str = Field(..., description="Strategy description")
    instrument: str = Field(..., description="Trading instrument")
    segment: str = Field(..., description="Market segment")
    timeframe: str = Field(..., description="Candle timeframe")
    indicators: List[Dict[str, Any]] = Field(default_factory=list, description="Indicators used")
    entry_conditions: str = Field(..., description="Entry conditions as Python expression")
    exit_conditions: str = Field(..., description="Exit conditions as Python expression")
    risk_params: Dict[str, Any] = Field(default_factory=dict, description="Risk parameters")
    generated_code: str = Field(default="", description="Generated Python code")
    validation: Dict[str, Any] = Field(default_factory=dict, description="Validation results")


class LLMHealthResponse(BaseModel):
    """LLM engine health status."""

    model_loaded: bool = Field(..., description="Whether the model is loaded")
    base_model: str = Field(..., description="Base model name")
    device: str = Field(..., description="Compute device")
    quantization: Optional[str] = Field(None, description="Quantization mode")


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


@router.post(
    "/generate-strategy",
    response_model=StrategyResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate trading strategy from natural language",
    description="Convert a natural language trading idea into a structured strategy with auto-generated Python code.",
)
async def generate_strategy(
    request: StrategyPromptRequest,
) -> StrategyResponse:
    """
    Generate trading strategy from natural language.

    Example prompt: "Buy Nifty when RSI below 30 with 1% stop loss"
    """
    try:
        llm_engine = LLMEngine()
        strategy_output: StrategyOutput = llm_engine.generate_strategy(
            prompt=request.prompt
        )

        # Also generate executable code via the strategy parser + code generator
        parser = NLParser()
        template = parser.parse(request.prompt)

        validator = StrategyValidator()
        validation_result = validator.validate(template)

        generator = CodeGenerator()
        generated_code = generator.generate(template)

        strategy_dict = strategy_output.to_dict()
        strategy_dict["validation"] = {
            "is_valid": validation_result.is_valid,
            "errors": validation_result.errors,
            "warnings": validation_result.warnings,
        }

        logger.info(
            "Strategy generated for prompt: {} | instrument={} confidence={:.2f}",
            request.prompt[:80],
            strategy_output.instrument,
            strategy_output.confidence,
        )

        return StrategyResponse(
            strategy=strategy_dict,
            confidence=strategy_output.confidence,
            reasoning=strategy_output.reasoning,
            generated_code=generated_code,
        )

    except Exception as exc:
        logger.exception("Strategy generation failed: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Strategy generation failed: {exc}",
        )


@router.post(
    "/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Chat with AI trading assistant",
    description="Have a conversation with the TradeForge AI trading assistant.",
)
async def chat(request: ChatRequest) -> ChatResponse:
    """Chat with AI trading assistant."""
    try:
        llm_engine = LLMEngine()
        context = request.context or []
        response_text = llm_engine.chat(
            message=request.message,
            context=context,
        )

        return ChatResponse(
            response=response_text,
            model_loaded=llm_engine.is_ready(),
        )

    except Exception as exc:
        logger.exception("Chat failed: {}", exc)
        # Return a graceful fallback response
        return ChatResponse(
            response=(
                "I'm sorry, I'm having trouble processing your request right now. "
                "Please try again or rephrase your question."
            ),
            model_loaded=False,
        )


@router.post(
    "/explain-strategy",
    response_model=Dict[str, str],
    status_code=status.HTTP_200_OK,
    summary="Explain a strategy in plain language",
    description="Provide a beginner-friendly explanation of any trading strategy.",
)
async def explain_strategy(request: ExplainStrategyRequest) -> Dict[str, str]:
    """Explain a strategy in plain, beginner-friendly language."""
    try:
        llm_engine = LLMEngine()
        explanation = llm_engine.explain_strategy(request.strategy)

        return {
            "explanation": explanation,
            "strategy_name": request.strategy.get("strategy_name", "Unnamed Strategy"),
        }

    except Exception as exc:
        logger.exception("Strategy explanation failed: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Strategy explanation failed: {exc}",
        )


@router.post(
    "/analyze-backtest",
    response_model=Dict[str, str],
    status_code=status.HTTP_200_OK,
    summary="Analyze backtest results",
    description="Analyze backtest metrics and receive actionable improvement suggestions.",
)
async def analyze_backtest(request: AnalyzeBacktestRequest) -> Dict[str, str]:
    """Analyze backtest results and suggest improvements."""
    try:
        llm_engine = LLMEngine()
        analysis = llm_engine.analyze_backtest(request.results)

        return {
            "analysis": analysis,
            "metrics_summary": json.dumps(
                {
                    k: v
                    for k, v in request.results.items()
                    if k not in ("equity_curve", "drawdown_curve", "trade_log", "monthly_returns", "daily_pnl")
                },
                indent=2,
                default=str,
            ),
        }

    except Exception as exc:
        logger.exception("Backtest analysis failed: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Backtest analysis failed: {exc}",
        )


@router.post(
    "/parse-strategy",
    response_model=ParseStrategyResponse,
    status_code=status.HTTP_200_OK,
    summary="Parse NL prompt to structured strategy",
    description="Parse a natural language prompt into a structured strategy template without loading the LLM.",
)
async def parse_strategy(request: ParseStrategyRequest) -> ParseStrategyResponse:
    """
    Parse a natural-language prompt into a structured strategy template.

    This is a lightweight, rule-based parser that works without the LLM,
    making it ideal for quick previews and form auto-fill in the UI.
    """
    try:
        parser = NLParser()
        template = parser.parse(request.prompt)

        validator = StrategyValidator()
        validation = validator.validate(template)

        generator = CodeGenerator()
        code = generator.generate(template)

        # Build indicator summary
        indicators_summary = []
        for ind in template.indicators:
            indicators_summary.append(
                {
                    "name": ind.name.value,
                    "params": [{"name": p.name, "value": p.value} for p in ind.params],
                    "column": ind.column_name(),
                }
            )

        return ParseStrategyResponse(
            name=template.name,
            description=template.description,
            instrument=template.instrument,
            segment=template.segment,
            timeframe=template.timeframe,
            indicators=indicators_summary,
            entry_conditions=template.entry_conditions.to_python(),
            exit_conditions=template.exit_conditions.to_python(),
            risk_params={
                "stop_loss_type": template.risk.stop_loss_type.value,
                "stop_loss_value": template.risk.stop_loss_value,
                "target_type": template.risk.target_type.value,
                "target_value": template.risk.target_value,
                "position_sizing_type": template.risk.position_sizing_type.value,
                "position_sizing_value": template.risk.position_sizing_value,
            },
            generated_code=code,
            validation={
                "is_valid": validation.is_valid,
                "errors": validation.errors,
                "warnings": validation.warnings,
            },
        )

    except ValueError as exc:
        logger.warning("Strategy parse validation error: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        logger.exception("Strategy parsing failed: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Strategy parsing failed: {exc}",
        )


@router.get(
    "/health",
    response_model=LLMHealthResponse,
    summary="LLM engine health check",
    description="Check whether the LLM model is loaded and ready.",
)
async def llm_health() -> LLMHealthResponse:
    """Check LLM engine health status."""
    try:
        llm_engine = LLMEngine()
        return LLMHealthResponse(
            model_loaded=llm_engine.is_ready(),
            base_model=llm_engine.base_model_name,
            device=llm_engine.device,
            quantization=llm_engine.quantization,
        )
    except Exception as exc:
        logger.warning("LLM health check failed: {}", exc)
        return LLMHealthResponse(
            model_loaded=False,
            base_model="unknown",
            device="unknown",
            quantization=None,
        )
