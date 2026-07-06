"""
Custom LLM Engine for TradeForge AI

Fine-tuned language model that:
1. Converts natural language trading ideas into structured strategy definitions
2. Analyzes backtest results and suggests improvements
3. Generates market analysis and trade recommendations
4. Explains strategies in plain language

Architecture:
- Base model: microsoft/DialoGPT-medium (lightweight, fast)
- Fine-tuned on trading strategy dataset
- LoRA/PEFT for efficient fine-tuning
- Quantized inference for speed

Dependencies:
    transformers>=4.30.0
    peft>=0.4.0
    datasets>=2.12.0
    torch>=2.0.0
    pydantic>=2.0.0
    loguru>=0.7.0
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from datetime import datetime
from typing import Any, Callable, Coroutine, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, Field, field_validator
from loguru import logger

# ---------------------------------------------------------------------------
# Lazy imports for heavy ML libraries — only loaded when LLMEngine is used.
# This keeps the module import-time lightweight for the fast-path (StrategyLLM).
# ---------------------------------------------------------------------------
torch: Any = None
AutoTokenizer: Any = None
AutoModelForCausalLM: Any = None
pipeline: Any = None
TrainingArguments: Any = None
Trainer: Any = None
TrainerCallback: Any = None
DataCollatorForLanguageModeling: Any = None
LoraConfig: Any = None
get_peft_model: Any = None
PeftModel: Any = None
TaskType: Any = None
Dataset: Any = None


def _load_ml_deps() -> None:
    """Import heavy ML libraries on first use."""
    global torch, AutoTokenizer, AutoModelForCausalLM, pipeline
    global TrainingArguments, Trainer, TrainerCallback, DataCollatorForLanguageModeling
    global LoraConfig, get_peft_model, PeftModel, TaskType, Dataset

    if torch is not None:
        return  # Already loaded

    import torch as _torch
    from transformers import (
        AutoTokenizer as _AutoTokenizer,
        AutoModelForCausalLM as _AutoModelForCausalLM,
        pipeline as _pipeline,
        TrainingArguments as _TrainingArguments,
        Trainer as _Trainer,
        TrainerCallback as _TrainerCallback,
        DataCollatorForLanguageModeling as _DataCollatorForLanguageModeling,
    )
    from datasets import Dataset as _Dataset

    torch = _torch
    AutoTokenizer = _AutoTokenizer
    AutoModelForCausalLM = _AutoModelForCausalLM
    pipeline = _pipeline
    TrainingArguments = _TrainingArguments
    Trainer = _Trainer
    TrainerCallback = _TrainerCallback
    DataCollatorForLanguageModeling = _DataCollatorForLanguageModeling
    Dataset = _Dataset

    # PEFT is optional at import/load time but required for fine-tuning.
    try:
        from peft import (
            LoraConfig as _LoraConfig,
            get_peft_model as _get_peft_model,
            PeftModel as _PeftModel,
            TaskType as _TaskType,
        )
        LoraConfig = _LoraConfig
        get_peft_model = _get_peft_model
        PeftModel = _PeftModel
        TaskType = _TaskType
    except ImportError:
        logger.warning(
            "PEFT is not installed. Fine-tuning will not be available."
        )
        LoraConfig = None
        get_peft_model = None
        PeftModel = None
        TaskType = None

    logger.debug("Heavy ML dependencies loaded successfully.")


# =============================================================================
# Pydantic v2 schemas
# =============================================================================


class StopLossConfig(BaseModel):
    """Stop-loss configuration for a trading strategy."""

    type: str = Field(
        default="fixed_pct",
        description="Stop-loss type: fixed_pct / trailing / atr / volatility_based",
    )
    value: float = Field(default=1.0, description="Stop-loss value (context depends on type)")
    atr_multiplier: Optional[float] = Field(
        default=None, description="ATR multiplier when type='atr'"
    )
    trail_pct: Optional[float] = Field(
        default=None, description="Trailing percentage when type='trailing'"
    )


class TargetConfig(BaseModel):
    """Profit target configuration for a trading strategy."""

    type: str = Field(
        default="fixed_pct",
        description="Target type: fixed_pct / risk_reward / trailing / partial",
    )
    value: float = Field(default=2.0, description="Target value (context depends on type)")
    risk_reward_ratio: Optional[float] = Field(
        default=None, description="R:R ratio when type='risk_reward'"
    )
    partial_targets: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Partial profit-taking levels"
    )


class PositionSizingConfig(BaseModel):
    """Position sizing configuration for a trading strategy."""

    type: str = Field(
        default="pct_capital",
        description="Sizing type: fixed_qty / pct_capital / risk_based / kelly",
    )
    value: float = Field(
        default=10.0, description="Value (context depends on type)"
    )
    max_position_pct: float = Field(
        default=25.0, description="Maximum position size as % of capital"
    )
    risk_per_trade_pct: Optional[float] = Field(
        default=1.0, description="Risk per trade as % of capital"
    )


class Condition(BaseModel):
    """Single entry or exit condition within a strategy."""

    indicator: str = Field(description="Technical indicator name (rsi, sma, ema, macd, ...)")
    condition: str = Field(
        description="Comparison operator: <, >, ==, crosses_above, crosses_below, between"
    )
    value: Union[float, int, List[float]] = Field(
        description="Threshold value(s) for the condition"
    )
    period: Optional[int] = Field(default=None, description="Indicator lookback period")
    params: Dict[str, Any] = Field(
        default_factory=dict, description="Additional indicator-specific parameters"
    )


class StrategyOutput(BaseModel):
    """Structured strategy output produced by the LLM engine."""

    strategy_name: str = Field(description="Human-readable name of the strategy")
    description: str = Field(description="Detailed human-readable description")
    instrument: str = Field(
        description="Trading instrument symbol (RELIANCE, NIFTY50, BANKNIFTY, etc.)"
    )
    segment: str = Field(
        default="equity",
        description="Market segment: equity / futures / options / forex / crypto",
    )
    timeframe: str = Field(
        default="15m",
        description="Chart timeframe: 1m / 5m / 15m / 1H / 4H / 1D / 1W",
    )

    entry_conditions: List[Condition] = Field(
        default_factory=list, description="Ordered list of entry condition objects"
    )
    exit_conditions: List[Condition] = Field(
        default_factory=list, description="Ordered list of exit condition objects"
    )

    stop_loss: StopLossConfig = Field(
        default_factory=StopLossConfig, description="Stop-loss configuration"
    )
    target: TargetConfig = Field(
        default_factory=TargetConfig, description="Profit target configuration"
    )
    position_sizing: PositionSizingConfig = Field(
        default_factory=PositionSizingConfig, description="Position sizing configuration"
    )

    confidence: float = Field(
        default=0.8, ge=0.0, le=1.0, description="LLM confidence score (0.0 – 1.0)"
    )
    reasoning: str = Field(
        default="", description="Chain-of-thought reasoning that led to the strategy"
    )

    # ------------------------------------------------------------------
    # Pydantic v2 validators
    # ------------------------------------------------------------------

    @field_validator("segment")
    @classmethod
    def _validate_segment(cls, v: str) -> str:
        allowed = {"equity", "futures", "options", "forex", "crypto"}
        if v.lower() not in allowed:
            raise ValueError(f"segment must be one of {allowed}, got '{v}'")
        return v.lower()

    @field_validator("timeframe")
    @classmethod
    def _validate_timeframe(cls, v: str) -> str:
        allowed = {"1m", "5m", "15m", "1h", "4h", "1d", "1w", "1M"}
        normalized = v.lower()
        if normalized not in allowed:
            raise ValueError(f"timeframe must be one of {allowed}, got '{v}'")
        return normalized

    @field_validator("confidence")
    @classmethod
    def _validate_confidence(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"confidence must be in [0.0, 1.0], got {v}")
        return round(v, 4)

    def to_json(self, indent: int = 2) -> str:
        """Serialize strategy to pretty-printed JSON."""
        return json.dumps(self.model_dump(), indent=indent, ensure_ascii=False)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize strategy to a plain Python dictionary."""
        return self.model_dump()


# =============================================================================
# Training progress callback — forwards Trainer events to an async callback
# =============================================================================


def _make_progress_callback_class() -> type:
    """Return a ``TrainerCallback`` subclass that forwards events async."""
    if TrainerCallback is None:
        raise RuntimeError("Transformers TrainerCallback is not available.")

    class _FineTuneProgressCallback(TrainerCallback):
        """
        Transformers ``TrainerCallback`` that forwards events to an async callback.

        The trainer runs inside a thread-pool executor. This callback captures the
        current asyncio event loop at construction time and uses
        ``loop.call_soon_threadsafe`` to schedule the async callback back on the
        loop thread.
        """

        def __init__(
            self,
            loop: asyncio.AbstractEventLoop,
            async_callback: Callable[[Dict[str, Any]], Coroutine],
        ) -> None:
            super().__init__()
            self._loop = loop
            self._async_callback = async_callback

        def _emit(self, payload: Dict[str, Any]) -> None:
            if self._async_callback is None:
                return
            try:
                self._loop.call_soon_threadsafe(
                    asyncio.create_task, self._async_callback(payload)
                )
            except RuntimeError:
                # Event loop closed — ignore late events during shutdown.
                pass

        def on_log(
            self,
            args: Any,
            state: Any,
            control: Any,
            logs: Optional[Dict[str, Any]] = None,
            **kwargs: Any,
        ) -> None:
            if logs:
                self._emit({"event": "log", **logs})

        def on_epoch_end(
            self, args: Any, state: Any, control: Any, **kwargs: Any
        ) -> None:
            payload: Dict[str, Any] = {
                "event": "epoch_end",
                "epoch": int(state.epoch) if state.epoch else 0,
            }
            if state.log_history:
                latest = state.log_history[-1]
                payload["loss"] = latest.get("loss", 0.0)
            self._emit(payload)

    return _FineTuneProgressCallback


# =============================================================================
# LLM Engine — full model-based generation
# =============================================================================


class LLMEngine:
    """
    Custom LLM Engine for trading strategy generation.

    Uses a fine-tuned causal LM (default: microsoft/DialoGPT-medium) with
    optional LoRA adapters for efficient trading-specific language understanding.

    Key capabilities
    ----------------
    * ``generate_strategy``  – NL prompt  →  structured ``StrategyOutput``
    * ``analyze_backtest``   – backtest metrics  →  natural language insights
    * ``chat``               – multi-turn trading-aware conversation
    * ``explain_strategy``   – strategy JSON  →  human-friendly explanation

    Example
    -------
    .. code-block:: python

        engine = LLMEngine()
        strategy = engine.generate_strategy(
            "Buy Nifty when RSI drops below 30 with 1% stop loss"
        )
        print(strategy.to_json())
    """

    # ------------------------------------------------------------------
    # Class-level prompt templates
    # ------------------------------------------------------------------

    _STRATEGY_SYSTEM_PROMPT: str = (
        "You are TradeForge AI, an expert quantitative trading strategy designer. "
        "Convert the user's natural-language trading idea into a precise JSON strategy. "
        "Follow these rules:\n"
        "1. Extract instrument, timeframe, entry/exit conditions, stop-loss and target.\n"
        "2. Use only well-known technical indicators (rsi, sma, ema, macd, bollinger, atr, vwap).\n"
        "3. Output ONLY valid JSON — no markdown, no extra commentary.\n"
        "4. Include a short 'reasoning' field explaining your design choices.\n"
    )

    _BACKTEST_SYSTEM_PROMPT: str = (
        "You are TradeForge AI, a senior quantitative analyst. "
        "Analyze the provided backtest results and give actionable improvement suggestions. "
        "Focus on: win-rate optimization, drawdown reduction, risk-adjusted returns. "
        "Respond in clear, structured bullet points."
    )

    _EXPLAIN_SYSTEM_PROMPT: str = (
        "You are TradeForge AI, a trading educator. "
        "Explain the given trading strategy in simple, friendly language that a beginner can understand. "
        "Highlight the logic behind each rule, the risk profile, and when the strategy works best."
    )

    def __init__(
        self,
        base_model: str = "microsoft/DialoGPT-medium",
        checkpoint_dir: str = "./training/checkpoints",
        device: str = "auto",
        max_length: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9,
        repetition_penalty: float = 1.15,
        use_lora: bool = True,
        lora_checkpoint: Optional[str] = None,
        quantization: Optional[str] = None,
    ) -> None:
        """
        Initialise the LLM engine.

        Parameters
        ----------
        base_model:
            HuggingFace model identifier or local path.
        checkpoint_dir:
            Directory where fine-tuned checkpoints are stored.
        device:
            ``"auto"`` selects CUDA when available, else CPU.
        max_length:
            Maximum token length for generation (and truncation).
        temperature:
            Sampling temperature — higher = more creative.
        top_p:
            Nucleus-sampling probability mass.
        repetition_penalty:
            Penalty for repeating tokens (1.0 = no penalty).
        use_lora:
            Whether to attempt loading LoRA adapters.
        lora_checkpoint:
            Specific LoRA adapter path to load (relative to *checkpoint_dir*).
        quantization:
            ``"4bit"`` or ``"8bit"`` for BitsAndBytes quant, or ``None``.
        """
        # Lazy-load heavy dependencies
        _load_ml_deps()

        self.base_model_name: str = base_model
        self.checkpoint_dir: str = checkpoint_dir
        self.max_length: int = max_length
        self.temperature: float = temperature
        self.top_p: float = top_p
        self.repetition_penalty: float = repetition_penalty
        self.use_lora: bool = use_lora
        self.quantization: Optional[str] = quantization

        # Resolve device
        if device == "auto":
            self.device: str = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        logger.info(f"LLMEngine initialising — base_model={base_model}, device={self.device}")

        # Internal handles (populated by _load_model)
        self._tokenizer: Optional[Any] = None
        self._model: Optional[Any] = None
        self._generator: Optional[Any] = None
        self._model_loaded: bool = False
        self._generation_config: Dict[str, Any] = {}

        # Attempt model load — failures are logged but not raised so the
        # engine can still fall back to rule-based generation.
        self._load_model(lora_checkpoint=lora_checkpoint)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_model(self, lora_checkpoint: Optional[str] = None) -> None:
        """
        Load tokenizer + base model (+ optional LoRA adapters).

        On failure the engine remains usable via the ``StrategyLLM`` fast-path.
        """
        try:
            # ---- Tokenizer ------------------------------------------------
            logger.info(f"Loading tokenizer from {self.base_model_name} ...")
            self._tokenizer = AutoTokenizer.from_pretrained(
                self.base_model_name,
                trust_remote_code=True,
                use_fast=True,
            )
            if self._tokenizer.pad_token is None:
                self._tokenizer.pad_token = self._tokenizer.eos_token
                self._tokenizer.pad_token_id = self._tokenizer.eos_token_id

            # ---- Model loading options ------------------------------------
            model_kwargs: Dict[str, Any] = {
                "trust_remote_code": True,
                "torch_dtype": torch.float16 if self.device == "cuda" else torch.float32,
            }

            if self.quantization == "4bit":
                from transformers import BitsAndBytesConfig
                model_kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_quant_type="nf4",
                )
            elif self.quantization == "8bit":
                model_kwargs["load_in_8bit"] = True
            else:
                model_kwargs["device_map"] = "auto" if self.device == "cuda" else None

            logger.info(f"Loading base model {self.base_model_name} ...")
            self._model = AutoModelForCausalLM.from_pretrained(
                self.base_model_name,
                **model_kwargs,
            )

            if self.device == "cpu" and self.quantization is None:
                self._model = self._model.to(self.device)

            # ---- LoRA adapters --------------------------------------------
            if self.use_lora:
                adapter_path: Optional[str] = None
                if lora_checkpoint:
                    adapter_path = os.path.join(self.checkpoint_dir, lora_checkpoint)
                else:
                    # Auto-detect most recent checkpoint
                    adapter_path = self._find_latest_checkpoint()

                if adapter_path and os.path.isdir(adapter_path):
                    logger.info(f"Loading LoRA adapters from {adapter_path} ...")
                    self._model = PeftModel.from_pretrained(self._model, adapter_path)
                elif self.use_lora:
                    logger.warning(
                        "No LoRA checkpoint found — using base model weights only."
                    )

            self._model.eval()
            self._model_loaded = True
            logger.info("Model loaded successfully.")

        except Exception as exc:
            logger.error(f"Model loading failed: {exc}")
            self._model_loaded = False
            self._tokenizer = None
            self._model = None

    def _find_latest_checkpoint(self) -> Optional[str]:
        """Return the path of the most-recent LoRA checkpoint under *checkpoint_dir*."""
        if not os.path.isdir(self.checkpoint_dir):
            return None
        candidates = [
            os.path.join(self.checkpoint_dir, d)
            for d in os.listdir(self.checkpoint_dir)
            if os.path.isdir(os.path.join(self.checkpoint_dir, d))
            and os.path.isfile(os.path.join(self.checkpoint_dir, d, "adapter_config.json"))
        ]
        if not candidates:
            return None
        # Sort by mtime descending
        candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        return candidates[0]

    def _build_prompt(self, system_msg: str, user_msg: str) -> str:
        """Build a chat-style prompt compatible with DialoGPT."""
        # DialoGPT does not use a special chat template — we use a simple
        # structured format that the model can learn from fine-tuning data.
        return (
            f"System: {system_msg}\n"
            f"User: {user_msg}\n"
            f"Assistant:"
        )

    def _generate_text(
        self,
        prompt: str,
        max_new_tokens: int = 256,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
    ) -> str:
        """
        Run text generation using the loaded model.

        Falls back to the lightweight ``StrategyLLM`` if the model is unavailable.
        """
        if not self._model_loaded or self._model is None or self._tokenizer is None:
            logger.warning("Model not loaded — falling back to StrategyLLM.")
            raise RuntimeError("Model not available")

        temp = temperature if temperature is not None else self.temperature
        p = top_p if top_p is not None else self.top_p

        inputs = self._tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=self.max_length,
            padding=True,
        ).to(self.device)

        with torch.no_grad():
            outputs = self._model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=temp,
                top_p=p,
                repetition_penalty=self.repetition_penalty,
                do_sample=True,
                pad_token_id=self._tokenizer.pad_token_id,
                eos_token_id=self._tokenizer.eos_token_id,
            )

        # Decode only the newly generated tokens
        generated_tokens = outputs[0][inputs["input_ids"].shape[1] :]
        text = self._tokenizer.decode(generated_tokens, skip_special_tokens=True)
        return text.strip()

    def _safe_json_parse(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Extract and parse JSON from model output.

        Handles:
        - Markdown code fences (```json ... ```)
        - Truncated JSON (attempts to close braces)
        - Plain JSON strings
        """
        # 1. Try markdown code block
        code_fence = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
        if code_fence:
            text = code_fence.group(1).strip()

        # 2. Try to find the outermost JSON object
        json_match = re.search(r"(\{.*\})", text, re.DOTALL)
        if json_match:
            text = json_match.group(1).strip()

        # 3. Attempt parse + truncation repair
        for strategy in (lambda t: json.loads(t), lambda t: json.loads(t + "}"), lambda t: json.loads(t + "}}")):
            try:
                return strategy(text)
            except json.JSONDecodeError:
                continue

        logger.error(f"Failed to parse JSON from model output: {text[:200]}...")
        return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_ready(self) -> bool:
        """Return ``True`` if the underlying model is loaded and ready."""
        return self._model_loaded

    def get_model_info(self) -> Dict[str, Any]:
        """Return model architecture and runtime information."""
        return {
            "base_model": self.base_model_name,
            "device": self.device,
            "model_loaded": self._model_loaded,
            "quantization": self.quantization,
        }

    async def fine_tune(
        self,
        dataset: Any,
        checkpoint_path: Optional[str] = None,
        epochs: int = 3,
        learning_rate: float = 1e-4,
        batch_size: int = 32,
        job_id: int = 0,
        progress_callback: Optional[Callable[[Dict[str, Any]], Coroutine]] = None,
    ) -> str:
        """
        Fine-tune the base model on a HuggingFace ``datasets.Dataset``.

        The dataset is expected to contain a ``text`` column with causal-LM
        training examples. Training is performed in a background thread pool
        so the async event loop remains responsive.

        Parameters
        ----------
        dataset:
            HuggingFace ``Dataset`` with a ``text`` column.
        checkpoint_path:
            Optional path to an existing LoRA adapter to resume from.
        epochs:
            Number of training epochs.
        learning_rate:
            Optimizer learning rate.
        batch_size:
            Per-device training batch size.
        job_id:
            Identifier used to name the output checkpoint directory.
        progress_callback:
            Optional async callable invoked with training progress dicts.

        Returns
        -------
        str
            Path to the saved checkpoint directory.
        """
        try:
            if LoraConfig is None or get_peft_model is None or PeftModel is None:
                raise RuntimeError("PEFT is required for fine-tuning")

            if self._tokenizer is None:
                raise RuntimeError("Tokenizer not loaded")

            # Resolve a unique output directory under the engine checkpoint dir.
            output_dir = os.path.join(
                self.checkpoint_dir, f"job_{job_id}_{int(time.time())}"
            )
            os.makedirs(output_dir, exist_ok=True)

            # Load a fresh base model for training.
            base_model = AutoModelForCausalLM.from_pretrained(
                self.base_model_name,
                trust_remote_code=True,
                torch_dtype=torch.float32,
                device_map=None,
            )
            base_model = base_model.to(self.device)

            # Attach or resume LoRA adapters.
            if (
                checkpoint_path
                and os.path.isdir(checkpoint_path)
                and os.path.isfile(os.path.join(checkpoint_path, "adapter_config.json"))
            ):
                logger.info(f"Resuming LoRA adapter from {checkpoint_path}")
                train_model = PeftModel.from_pretrained(base_model, checkpoint_path)
            else:
                lora_config = LoraConfig(
                    r=8,
                    lora_alpha=32,
                    target_modules=["c_attn", "c_proj"],
                    lora_dropout=0.05,
                    bias="none",
                    task_type="CAUSAL_LM",
                )
                train_model = get_peft_model(base_model, lora_config)

            train_model.train()

            def _tokenize_function(examples: Dict[str, Any]) -> Dict[str, Any]:
                result = self._tokenizer(
                    examples["text"],
                    truncation=True,
                    padding="max_length",
                    max_length=self.max_length,
                    return_tensors=None,
                )
                result["labels"] = result["input_ids"].copy()
                return result

            tokenized_dataset = dataset.map(
                _tokenize_function,
                batched=True,
                remove_columns=["text"],
                desc="Tokenizing dataset",
            )

            data_collator = DataCollatorForLanguageModeling(
                tokenizer=self._tokenizer,
                mlm=False,
            )

            effective_batch_size = max(1, min(batch_size, len(tokenized_dataset)))

            training_args_kwargs = dict(
                output_dir=output_dir,
                num_train_epochs=epochs,
                per_device_train_batch_size=effective_batch_size,
                learning_rate=learning_rate,
                logging_steps=1,
                save_strategy="epoch",
                fp16=False,
                bf16=False,
                report_to=[],
                disable_tqdm=True,
            )
            # Older/newer transformers versions may not accept this arg.
            if "overwrite_output_dir" in TrainingArguments.__init__.__code__.co_varnames:
                training_args_kwargs["overwrite_output_dir"] = True
            training_args = TrainingArguments(**training_args_kwargs)

            loop = asyncio.get_running_loop()
            progress_callback_instance = _make_progress_callback_class()(
                loop, progress_callback
            )

            trainer = Trainer(
                model=train_model,
                args=training_args,
                train_dataset=tokenized_dataset,
                data_collator=data_collator,
                callbacks=[progress_callback_instance],
            )

            await loop.run_in_executor(None, trainer.train)

            train_model.save_pretrained(output_dir)
            self._tokenizer.save_pretrained(output_dir)

            logger.info(f"Fine-tuned checkpoint saved to {output_dir}")
            return output_dir

        except Exception as exc:
            logger.exception(f"Fine-tuning failed: {exc}")
            raise RuntimeError(f"Fine-tuning failed: {exc}") from exc

    def generate_strategy(self, prompt: str) -> StrategyOutput:
        """
        Convert a natural-language trading idea into a structured strategy.

        Parameters
        ----------
        prompt:
            Natural language description, e.g.:
            ``"Buy when RSI is below 30 on Nifty 15-min chart with 1 % stop loss"``

        Returns
        -------
        StrategyOutput
            Fully populated strategy object.
        """
        start_time = time.perf_counter()
        logger.info(f"Generating strategy for prompt: {prompt[:120]}...")

        # Attempt LLM-based generation
        try:
            built_prompt = self._build_prompt(self._STRATEGY_SYSTEM_PROMPT, prompt)
            raw_output = self._generate_text(built_prompt, max_new_tokens=384)
            parsed = self._safe_json_parse(raw_output)

            if parsed is not None:
                strategy = self._strategy_from_dict(parsed, prompt)
                elapsed = time.perf_counter() - start_time
                logger.info(f"Strategy generated in {elapsed:.2f}s (LLM path).")
                return strategy

        except Exception as exc:
            logger.warning(f"LLM generation failed ({exc}) — falling back to rule-based.")

        # Fallback: rule-based extraction
        fallback = StrategyLLM()
        strategy = fallback.quick_generate(prompt)
        elapsed = time.perf_counter() - start_time
        logger.info(f"Strategy generated in {elapsed:.2f}s (rule-based fallback).")
        return strategy

    def analyze_backtest(
        self,
        backtest_results: Dict[str, Any],
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        Analyze backtest results and provide natural-language insights.

        Parameters
        ----------
        backtest_results:
            Dictionary containing at least:
            ``total_return``, ``sharpe_ratio``, ``max_drawdown``,
            ``win_rate``, ``total_trades``, ``avg_trade_duration``.
        system_prompt:
            Optional system prompt override. When provided, it replaces the
            default backtest analyst system message.

        Returns
        -------
        str
            Structured analysis with improvement suggestions.
        """
        logger.info("Analyzing backtest results ...")

        # Serialize backtest data for the prompt
        backtest_json = json.dumps(backtest_results, indent=2, ensure_ascii=False)
        user_prompt = f"Analyze these backtest results:\n{backtest_json}"

        try:
            system_msg = system_prompt if system_prompt else self._BACKTEST_SYSTEM_PROMPT
            built_prompt = self._build_prompt(system_msg, user_prompt)
            analysis = self._generate_text(built_prompt, max_new_tokens=512, temperature=0.5)
            logger.info("Backtest analysis generated (LLM path).")
            return analysis
        except Exception as exc:
            logger.warning(f"LLM analysis failed ({exc}) — using template-based analysis.")
            return self._template_backtest_analysis(backtest_results)

    def chat(
        self,
        message: str,
        context: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        General trading-aware chat.

        Parameters
        ----------
        message:
            The user's latest message.
        context:
            Previous conversation turns, each a dict with ``role`` and ``content``.
        system_prompt:
            Optional system prompt override. When provided, it replaces the
            default trading assistant system message.

        Returns
        -------
        str
            The model's response.
        """
        context = context or []
        system_msg = system_prompt or (
            "You are TradeForge AI, a helpful trading assistant. "
            "You can discuss strategies, technical analysis, risk management, "
            "and market psychology. Keep answers concise and actionable."
        )

        # Build conversation history
        history_parts = [f"System: {system_msg}"]
        for turn in context[-6:]:  # Keep last 6 turns for context window
            role = turn.get("role", "user")
            content = turn.get("content", "")
            history_parts.append(f"{role.capitalize()}: {content}")
        history_parts.append(f"User: {message}")
        history_parts.append("Assistant:")

        prompt = "\n".join(history_parts)

        try:
            return self._generate_text(prompt, max_new_tokens=384, temperature=0.7)
        except Exception as exc:
            logger.error(f"Chat generation failed: {exc}")
            return (
                "I'm sorry, I'm having trouble processing your request right now. "
                "Please try again or rephrase your question."
            )

    def explain_strategy(self, strategy_definition: Dict[str, Any]) -> str:
        """
        Explain a strategy in plain, beginner-friendly language.

        Parameters
        ----------
        strategy_definition:
            Raw strategy dictionary (e.g. from ``StrategyOutput.to_dict()``).

        Returns
        -------
        str
            Human-readable explanation.
        """
        strategy_json = json.dumps(strategy_definition, indent=2, ensure_ascii=False)
        user_prompt = f"Explain this trading strategy:\n{strategy_json}"

        try:
            built_prompt = self._build_prompt(self._EXPLAIN_SYSTEM_PROMPT, user_prompt)
            explanation = self._generate_text(built_prompt, max_new_tokens=512, temperature=0.6)
            logger.info("Strategy explanation generated (LLM path).")
            return explanation
        except Exception as exc:
            logger.warning(f"LLM explanation failed ({exc}) — using template-based.")
            return self._template_explain_strategy(strategy_definition)

    # ------------------------------------------------------------------
    # Template-based fallbacks (no model required)
    # ------------------------------------------------------------------

    def _template_backtest_analysis(self, results: Dict[str, Any]) -> str:
        """Generate a structured analysis using hard-coded templates."""
        lines: List[str] = ["## Backtest Analysis", ""]

        total_return = results.get("total_return", 0)
        sharpe = results.get("sharpe_ratio", 0)
        max_dd = results.get("max_drawdown", 0)
        win_rate = results.get("win_rate", 0)
        trades = results.get("total_trades", 0)

        lines.append(f"**Total Return:** {total_return:.2f}%")
        lines.append(f"**Sharpe Ratio:** {sharpe:.2f}")
        lines.append(f"**Max Drawdown:** {max_dd:.2f}%")
        lines.append(f"**Win Rate:** {win_rate:.1f}%")
        lines.append(f"**Total Trades:** {trades}")
        lines.append("")

        # Health assessment
        lines.append("### Assessment")
        issues: List[str] = []
        if sharpe < 1.0:
            issues.append("Sharpe ratio below 1.0 — consider improving risk-adjusted returns.")
        if max_dd > 20:
            issues.append("Max drawdown exceeds 20% — risk management needs tightening.")
        if win_rate < 40:
            issues.append("Win rate is low — review entry criteria or reward:risk ratio.")
        if trades < 30:
            issues.append("Low trade count — results may not be statistically significant.")

        if not issues:
            lines.append("Strategy shows solid performance across key metrics.")
        else:
            for issue in issues:
                lines.append(f"- {issue}")

        lines.append("")
        lines.append("### Recommendations")
        if sharpe < 1.0:
            lines.append("- Tighten stop-loss or use trailing stops to improve Sharpe.")
        if max_dd > 20:
            lines.append("- Reduce position size or add a volatility filter.")
        if win_rate < 40:
            lines.append("- Add confirmation indicators (e.g., volume, trend alignment).")
        lines.append("- Consider Walk-Forward Analysis to validate robustness.")

        return "\n".join(lines)

    def _template_explain_strategy(self, strategy_definition: Dict[str, Any]) -> str:
        """Template-based strategy explanation when LLM is unavailable."""
        name = strategy_definition.get("strategy_name", "Unnamed Strategy")
        desc = strategy_definition.get("description", "")
        instrument = strategy_definition.get("instrument", "Unknown")
        timeframe = strategy_definition.get("timeframe", "")
        segment = strategy_definition.get("segment", "")
        entries = strategy_definition.get("entry_conditions", [])
        exits = strategy_definition.get("exit_conditions", [])
        sl = strategy_definition.get("stop_loss", {})
        tgt = strategy_definition.get("target", {})
        sizing = strategy_definition.get("position_sizing", {})

        lines: List[str] = [f"## Strategy: {name}", ""]
        if desc:
            lines.append(desc)
            lines.append("")

        lines.append(f"This strategy trades **{instrument}** in the **{segment}** segment on the **{timeframe}** timeframe.")
        lines.append("")

        # Entry conditions
        lines.append("### When to Enter a Trade")
        if entries:
            for i, cond in enumerate(entries, 1):
                ind = cond.get("indicator", "?").upper()
                condition = cond.get("condition", "?")
                value = cond.get("value", "?")
                period = cond.get("period", "")
                period_str = f"({period})" if period else ""
                lines.append(f"{i}. **{ind}**{period_str} **{condition}** {value}")
        else:
            lines.append("No specific entry conditions defined.")
        lines.append("")

        # Exit conditions
        lines.append("### When to Exit a Trade")
        if exits:
            for i, cond in enumerate(exits, 1):
                ind = cond.get("indicator", "?").upper()
                condition = cond.get("condition", "?")
                value = cond.get("value", "?")
                lines.append(f"{i}. **{ind}** **{condition}** {value}")
        else:
            lines.append("No specific exit conditions defined.")
        lines.append("")

        # Risk management
        lines.append("### Risk Management")
        sl_type = sl.get("type", "N/A")
        sl_val = sl.get("value", "N/A")
        tgt_type = tgt.get("type", "N/A")
        tgt_val = tgt.get("value", "N/A")
        size_type = sizing.get("type", "N/A")
        size_val = sizing.get("value", "N/A")

        lines.append(f"- **Stop Loss:** {sl_type} = {sl_val}")
        lines.append(f"- **Target:** {tgt_type} = {tgt_val}")
        lines.append(f"- **Position Sizing:** {size_type} = {size_val}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Strategy dict → StrategyOutput mapper
    # ------------------------------------------------------------------

    @staticmethod
    def _strategy_from_dict(data: Dict[str, Any], original_prompt: str = "") -> StrategyOutput:
        """
        Safely convert a parsed JSON dictionary into a ``StrategyOutput``.

        Handles missing / malformed fields gracefully by filling sensible defaults.
        """
        # Helper to build Condition objects
        def _make_conditions(raw_list: List[Any]) -> List[Condition]:
            conditions: List[Condition] = []
            for item in raw_list:
                if isinstance(item, dict):
                    try:
                        conditions.append(Condition(**item))
                    except Exception:
                        # Best-effort: fill missing fields
                        conditions.append(
                            Condition(
                                indicator=item.get("indicator", "unknown"),
                                condition=item.get("condition", ">"),
                                value=item.get("value", 0),
                                period=item.get("period"),
                                params={k: v for k, v in item.items() if k not in {"indicator", "condition", "value", "period"}},
                            )
                        )
            return conditions

        entry_raw = data.get("entry_conditions", data.get("entries", []))
        exit_raw = data.get("exit_conditions", data.get("exits", []))

        # Stop-loss
        sl_raw = data.get("stop_loss", data.get("stoploss", {}))
        if isinstance(sl_raw, dict):
            sl = StopLossConfig(**sl_raw)
        else:
            sl = StopLossConfig(type="fixed_pct", value=1.0)

        # Target
        tgt_raw = data.get("target", data.get("targets", {}))
        if isinstance(tgt_raw, dict):
            tgt = TargetConfig(**tgt_raw)
        else:
            tgt = TargetConfig(type="fixed_pct", value=2.0)

        # Position sizing
        sizing_raw = data.get("position_sizing", data.get("position_size", {}))
        if isinstance(sizing_raw, dict):
            sizing = PositionSizingConfig(**sizing_raw)
        else:
            sizing = PositionSizingConfig(type="pct_capital", value=10.0)

        return StrategyOutput(
            strategy_name=data.get("strategy_name", data.get("name", "Auto-Generated Strategy")),
            description=data.get("description", f"Strategy generated from: {original_prompt}"),
            instrument=data.get("instrument", data.get("symbol", "NIFTY50")),
            segment=data.get("segment", "equity"),
            timeframe=data.get("timeframe", "15m"),
            entry_conditions=_make_conditions(entry_raw),
            exit_conditions=_make_conditions(exit_raw),
            stop_loss=sl,
            target=tgt,
            position_sizing=sizing,
            confidence=float(data.get("confidence", 0.75)),
            reasoning=data.get("reasoning", ""),
        )

    def reload_model(self, lora_checkpoint: Optional[str] = None) -> bool:
        """
        Hot-reload the model (useful after a new checkpoint is saved).

        Returns
        -------
        bool
            ``True`` if reload succeeded.
        """
        logger.info("Reloading model ...")
        self._model_loaded = False
        self._model = None
        self._tokenizer = None
        self._load_model(lora_checkpoint=lora_checkpoint)
        return self._model_loaded


# =============================================================================
# StrategyLLM — lightweight rule-based fast path
# =============================================================================


class StrategyLLM:
    """
    Lightweight, zero-dependency strategy generator.

    Uses keyword extraction + template matching to produce a ``StrategyOutput``
    in milliseconds without loading any neural network.  This is the default
    fallback inside ``LLMEngine`` and can also be used stand-alone for
    latency-sensitive applications.
    """

    # ------------------------------------------------------------------
    # Segment / instrument / timeframe detection patterns
    # ------------------------------------------------------------------

    _INSTRUMENT_PATTERNS: Dict[str, List[str]] = {
        "NIFTY50": ["nifty", "nifty50", "nifty 50"],
        "BANKNIFTY": ["banknifty", "bank nifty", "bnf"],
        "FINNIFTY": ["finnifty", "fin nifty"],
        "SENSEX": ["sensex", "bse sensex"],
        "RELIANCE": ["reliance", "reliance industries", "ril"],
        "TCS": ["tcs", "tata consultancy"],
        "INFY": ["infy", "infosys"],
        "HDFCBANK": ["hdfcbank", "hdfc bank"],
        "ICICIBANK": ["icicibank", "icici bank"],
        "SBIN": ["sbin", "sbi", "state bank"],
        "ITC": ["itc"],
        "LT": ["lt", "larsen", "l&t"],
        "BHARTIARTL": ["bharti", "airtel"],
        "ADANIENT": ["adani enterprises", "adani ent"],
        "BTCUSD": ["bitcoin", "btc", "btcusd"],
        "ETHUSD": ["ethereum", "eth", "ethusd"],
        "EURUSD": ["eurusd", "eur/usd", "euro dollar"],
        "GBPUSD": ["gbpusd", "gbp/usd", "pound dollar"],
        "USDJPY": ["usdjpy", "usd/jpy"],
        "XAUUSD": ["gold", "xauusd", "xau/usd"],
    }

    _TIMEFRAME_PATTERNS: Dict[str, List[str]] = {
        "1m": ["1 minute", "1 min", "1m", "one minute"],
        "5m": ["5 minute", "5 min", "5m", "five minute"],
        "15m": ["15 minute", "15 min", "15m", "fifteen minute"],
        "1h": ["1 hour", "1h", "hourly", "one hour", "60 minute", "60m"],
        "4h": ["4 hour", "4h", "four hour"],
        "1d": ["daily", "1 day", "1d", "day"],
        "1w": ["weekly", "1 week", "1w", "week"],
        "1M": ["monthly", "1 month", "month"],
    }

    _SEGMENT_PATTERNS: Dict[str, List[str]] = {
        "equity": ["equity", "cash", "spot"],
        "futures": ["futures", "future", " fut"],
        "options": ["options", "option", " ce", " pe", "call", "put"],
        "forex": ["forex", "fx", "currency"],
        "crypto": ["crypto", "cryptocurrency"],
    }

    def __init__(self) -> None:
        """Initialise keyword dictionaries and strategy templates."""
        self.indicators: Dict[str, Any] = self._load_indicator_keywords()
        self.templates: List[Dict[str, Any]] = self._load_strategy_templates()
        logger.info("StrategyLLM initialised (rule-based fast path).")

    # ------------------------------------------------------------------
    # Keyword dictionaries
    # ------------------------------------------------------------------

    def _load_indicator_keywords(self) -> Dict[str, Any]:
        """
        Load indicator detection keywords and default parameters.

        Each entry maps an internal indicator key to:
        - ``names``: list of lowercase strings to search for in the prompt
        - ``params``: configurable parameter names
        - ``default_params``: fallback values when the user does not specify
        """
        return {
            "rsi": {
                "names": ["rsi", "relative strength index", "relative strength"],
                "params": ["period"],
                "default_params": {"period": 14},
            },
            "sma": {
                "names": ["sma", "simple moving average", "simple ma"],
                "params": ["period"],
                "default_params": {"period": 20},
            },
            "ema": {
                "names": ["ema", "exponential moving average", "exponential ma"],
                "params": ["period"],
                "default_params": {"period": 20},
            },
            "macd": {
                "names": ["macd", "moving average convergence divergence"],
                "params": ["fast", "slow", "signal"],
                "default_params": {"fast": 12, "slow": 26, "signal": 9},
            },
            "bollinger": {
                "names": ["bollinger", "bb", "bollinger bands", "bollinger band"],
                "params": ["period", "std_dev"],
                "default_params": {"period": 20, "std_dev": 2},
            },
            "atr": {
                "names": ["atr", "average true range"],
                "params": ["period"],
                "default_params": {"period": 14},
            },
            "vwap": {
                "names": ["vwap", "volume weighted average price", "volume weighted"],
                "params": [],
                "default_params": {},
            },
            "stochastic": {
                "names": ["stochastic", "stoch", "stochastic oscillator"],
                "params": ["k_period", "d_period"],
                "default_params": {"k_period": 14, "d_period": 3},
            },
            "adx": {
                "names": ["adx", "average directional index", "average directional"],
                "params": ["period"],
                "default_params": {"period": 14},
            },
            "volume": {
                "names": ["volume", "vol", "volumes"],
                "params": [],
                "default_params": {},
            },
            "obv": {
                "names": ["obv", "on balance volume", "on-balance volume"],
                "params": [],
                "default_params": {},
            },
            "supertrend": {
                "names": ["supertrend", "super trend"],
                "params": ["period", "multiplier"],
                "default_params": {"period": 10, "multiplier": 3},
            },
            "fibonacci": {
                "names": ["fibonacci", "fib", "fib retracement", "fibonacci retracement"],
                "params": ["level"],
                "default_params": {"level": 61.8},
            },
        }

    def _load_strategy_templates(self) -> List[Dict[str, Any]]:
        """
        Load a library of common strategy templates for fuzzy matching.

        Each template contains:
        - ``name``: human-readable strategy name
        - ``keywords``: list of terms that trigger this template
        - ``template``: partial ``StrategyOutput`` fields filled by the template
        """
        return [
            {
                "name": "RSI Oversold Bounce",
                "keywords": ["rsi", "below", "oversold", "buy", "mean reversion"],
                "template": {
                    "entry_conditions": [
                        Condition(indicator="rsi", condition="<", value=30, period=14),
                    ],
                    "exit_conditions": [
                        Condition(indicator="rsi", condition=">", value=70, period=14),
                    ],
                    "stop_loss": StopLossConfig(type="fixed_pct", value=1.0),
                    "target": TargetConfig(type="fixed_pct", value=3.0),
                },
            },
            {
                "name": "RSI Overbought Short",
                "keywords": ["rsi", "above", "overbought", "short", "sell"],
                "template": {
                    "entry_conditions": [
                        Condition(indicator="rsi", condition=">", value=70, period=14),
                    ],
                    "exit_conditions": [
                        Condition(indicator="rsi", condition="<", value=30, period=14),
                    ],
                    "stop_loss": StopLossConfig(type="fixed_pct", value=1.0),
                    "target": TargetConfig(type="fixed_pct", value=3.0),
                },
            },
            {
                "name": "SMA Golden Cross",
                "keywords": ["sma", "crossover", "golden cross", "bullish", "above"],
                "template": {
                    "entry_conditions": [
                        Condition(indicator="sma", condition="crosses_above", value=50, period=20),
                    ],
                    "exit_conditions": [
                        Condition(indicator="sma", condition="crosses_below", value=50, period=20),
                    ],
                    "stop_loss": StopLossConfig(type="fixed_pct", value=1.5),
                    "target": TargetConfig(type="risk_reward", value=3.0, risk_reward_ratio=2.0),
                },
            },
            {
                "name": "SMA Death Cross",
                "keywords": ["sma", "crossover", "death cross", "bearish", "below"],
                "template": {
                    "entry_conditions": [
                        Condition(indicator="sma", condition="crosses_below", value=50, period=20),
                    ],
                    "exit_conditions": [
                        Condition(indicator="sma", condition="crosses_above", value=50, period=20),
                    ],
                    "stop_loss": StopLossConfig(type="fixed_pct", value=1.5),
                    "target": TargetConfig(type="risk_reward", value=3.0, risk_reward_ratio=2.0),
                },
            },
            {
                "name": "EMA Trend Following",
                "keywords": ["ema", "trend", "exponential", "bullish", "above"],
                "template": {
                    "entry_conditions": [
                        Condition(indicator="ema", condition="crosses_above", value=200, period=20),
                    ],
                    "exit_conditions": [
                        Condition(indicator="ema", condition="crosses_below", value=200, period=20),
                    ],
                    "stop_loss": StopLossConfig(type="atr", value=1.5, atr_multiplier=1.5),
                    "target": TargetConfig(type="trailing", value=3.0, trail_pct=1.0),
                },
            },
            {
                "name": "MACD Momentum",
                "keywords": ["macd", "momentum", "histogram", "bullish"],
                "template": {
                    "entry_conditions": [
                        Condition(
                            indicator="macd",
                            condition="crosses_above",
                            value=0,
                            params={"fast": 12, "slow": 26, "signal": 9},
                        ),
                    ],
                    "exit_conditions": [
                        Condition(
                            indicator="macd",
                            condition="crosses_below",
                            value=0,
                            params={"fast": 12, "slow": 26, "signal": 9},
                        ),
                    ],
                    "stop_loss": StopLossConfig(type="fixed_pct", value=1.0),
                    "target": TargetConfig(type="fixed_pct", value=4.0),
                },
            },
            {
                "name": "Bollinger Squeeze",
                "keywords": ["bollinger", "squeeze", "band", "volatility", "breakout"],
                "template": {
                    "entry_conditions": [
                        Condition(indicator="bollinger", condition="<", value=-2, period=20),
                    ],
                    "exit_conditions": [
                        Condition(indicator="bollinger", condition=">", value=2, period=20),
                    ],
                    "stop_loss": StopLossConfig(type="atr", value=2.0, atr_multiplier=2.0),
                    "target": TargetConfig(type="fixed_pct", value=4.0),
                },
            },
            {
                "name": "VWAP Reversion",
                "keywords": ["vwap", "volume weighted", "reversion", "pullback"],
                "template": {
                    "entry_conditions": [
                        Condition(indicator="vwap", condition="<", value=-0.5),
                    ],
                    "exit_conditions": [
                        Condition(indicator="vwap", condition=">", value=0.5),
                    ],
                    "stop_loss": StopLossConfig(type="fixed_pct", value=0.8),
                    "target": TargetConfig(type="fixed_pct", value=2.0),
                },
            },
            {
                "name": "Supertrend Follower",
                "keywords": ["supertrend", "super trend", "trend following"],
                "template": {
                    "entry_conditions": [
                        Condition(
                            indicator="supertrend",
                            condition="==",
                            value=1,
                            params={"period": 10, "multiplier": 3},
                        ),
                    ],
                    "exit_conditions": [
                        Condition(
                            indicator="supertrend",
                            condition="==",
                            value=-1,
                            params={"period": 10, "multiplier": 3},
                        ),
                    ],
                    "stop_loss": StopLossConfig(type="atr", value=2.0, atr_multiplier=2.0),
                    "target": TargetConfig(type="trailing", value=5.0, trail_pct=1.5),
                },
            },
            {
                "name": "Stochastic Reversal",
                "keywords": ["stochastic", "stoch", "reversal", "oversold", "overbought"],
                "template": {
                    "entry_conditions": [
                        Condition(
                            indicator="stochastic",
                            condition="<",
                            value=20,
                            params={"k_period": 14, "d_period": 3},
                        ),
                    ],
                    "exit_conditions": [
                        Condition(
                            indicator="stochastic",
                            condition=">",
                            value=80,
                            params={"k_period": 14, "d_period": 3},
                        ),
                    ],
                    "stop_loss": StopLossConfig(type="fixed_pct", value=1.0),
                    "target": TargetConfig(type="fixed_pct", value=3.0),
                },
            },
            {
                "name": "ADX Trend Strength",
                "keywords": ["adx", "trend strength", "directional", "strong trend"],
                "template": {
                    "entry_conditions": [
                        Condition(indicator="adx", condition=">", value=25, period=14),
                    ],
                    "exit_conditions": [
                        Condition(indicator="adx", condition="<", value=20, period=14),
                    ],
                    "stop_loss": StopLossConfig(type="atr", value=2.0, atr_multiplier=2.0),
                    "target": TargetConfig(type="trailing", value=4.0, trail_pct=1.5),
                },
            },
            {
                "name": "Volume Breakout",
                "keywords": ["volume", "breakout", "spike", "high volume"],
                "template": {
                    "entry_conditions": [
                        Condition(indicator="volume", condition=">", value=2.0),
                    ],
                    "exit_conditions": [
                        Condition(indicator="volume", condition="<", value=1.0),
                    ],
                    "stop_loss": StopLossConfig(type="fixed_pct", value=1.5),
                    "target": TargetConfig(type="fixed_pct", value=4.0),
                },
            },
            {
                "name": "RSI + MACD Combo",
                "keywords": ["rsi", "macd", "combo", "combined", "multi"],
                "template": {
                    "entry_conditions": [
                        Condition(indicator="rsi", condition="<", value=35, period=14),
                        Condition(
                            indicator="macd",
                            condition="crosses_above",
                            value=0,
                            params={"fast": 12, "slow": 26, "signal": 9},
                        ),
                    ],
                    "exit_conditions": [
                        Condition(indicator="rsi", condition=">", value=65, period=14),
                        Condition(
                            indicator="macd",
                            condition="crosses_below",
                            value=0,
                            params={"fast": 12, "slow": 26, "signal": 9},
                        ),
                    ],
                    "stop_loss": StopLossConfig(type="fixed_pct", value=1.2),
                    "target": TargetConfig(type="risk_reward", value=2.5, risk_reward_ratio=2.0),
                },
            },
        ]

    # ------------------------------------------------------------------
    # Core fast-generation logic
    # ------------------------------------------------------------------

    def quick_generate(self, prompt: str) -> StrategyOutput:
        """
        Generate a strategy in < 10 ms using keyword extraction + template matching.

        Parameters
        ----------
        prompt:
            Natural language trading idea.

        Returns
        -------
        StrategyOutput
            Best-matching strategy populated from templates + extracted parameters.
        """
        prompt_lower = prompt.lower().strip()
        logger.debug(f"StrategyLLM.quick_generate — prompt: {prompt_lower[:100]}")

        # 1. Detect template
        matched_template = self._match_template(prompt_lower)

        # 2. Extract entities
        instrument = self._extract_instrument(prompt_lower)
        timeframe = self._extract_timeframe(prompt_lower)
        segment = self._extract_segment(prompt_lower)
        detected_indicators = self._extract_indicators(prompt_lower)

        # 3. Extract numeric parameters (stop-loss, target, etc.)
        sl_pct = self._extract_stop_loss(prompt_lower)
        tgt_pct = self._extract_target(prompt_lower)
        sizing = self._extract_position_sizing(prompt_lower)

        # 4. Build strategy from template + overrides
        base = matched_template["template"].copy()
        name = matched_template["name"]

        # Override with detected indicators if they differ from template
        entry_conditions: List[Condition] = list(base.get("entry_conditions", []))
        exit_conditions: List[Condition] = list(base.get("exit_conditions", []))

        # If user explicitly named indicators not in the template, try to add them
        user_indicators = [d["indicator"] for d in detected_indicators]
        template_indicators = [c.indicator for c in entry_conditions]
        for di in detected_indicators:
            if di["indicator"] not in template_indicators:
                # Add a sensible default condition for this indicator
                entry_conditions.append(self._default_entry_for_indicator(di))
                exit_conditions.append(self._default_exit_for_indicator(di))

        # Override stop-loss / target from prompt
        sl = base.get("stop_loss", StopLossConfig())
        if sl_pct is not None:
            sl = StopLossConfig(type="fixed_pct", value=sl_pct)

        tgt = base.get("target", TargetConfig())
        if tgt_pct is not None:
            tgt = TargetConfig(type="fixed_pct", value=tgt_pct)

        # Position sizing
        pos_sizing = PositionSizingConfig(type="pct_capital", value=10.0)
        if sizing is not None:
            pos_sizing = sizing

        # Build a human-readable description
        description = self._build_description(
            name, instrument, timeframe, entry_conditions, exit_conditions, sl, tgt
        )

        return StrategyOutput(
            strategy_name=f"{name} — {instrument}",
            description=description,
            instrument=instrument,
            segment=segment,
            timeframe=timeframe,
            entry_conditions=entry_conditions,
            exit_conditions=exit_conditions,
            stop_loss=sl,
            target=tgt,
            position_sizing=pos_sizing,
            confidence=0.7,  # Rule-based = moderate confidence
            reasoning=f"Matched template '{name}' via keyword extraction. "
                      f"Detected indicators: {', '.join(user_indicators) or 'none'}.",
        )

    # ------------------------------------------------------------------
    # Entity extraction helpers
    # ------------------------------------------------------------------

    def _match_template(self, prompt: str) -> Dict[str, Any]:
        """
        Score each template by keyword overlap and return the best match.

        If no template scores above the threshold, return a generic
        RSI mean-reversion template as a safe default.
        """
        best_score = 0
        best_template = self.templates[0]  # default fallback

        for tmpl in self.templates:
            score = sum(1 for kw in tmpl["keywords"] if kw in prompt)
            if score > best_score:
                best_score = score
                best_template = tmpl

        logger.debug(f"Template match score: {best_score} — '{best_template['name']}'")
        return best_template

    def _extract_instrument(self, prompt: str) -> str:
        """Detect the trading instrument from the prompt."""
        for symbol, aliases in self._INSTRUMENT_PATTERNS.items():
            if any(alias in prompt for alias in aliases):
                return symbol
        return "NIFTY50"  # Default

    def _extract_timeframe(self, prompt: str) -> str:
        """Detect the chart timeframe from the prompt."""
        for tf, aliases in self._TIMEFRAME_PATTERNS.items():
            if any(alias in prompt for alias in aliases):
                return tf
        return "15m"  # Default

    def _extract_segment(self, prompt: str) -> str:
        """Detect the market segment from the prompt."""
        for seg, aliases in self._SEGMENT_PATTERNS.items():
            if any(alias in prompt for alias in aliases):
                return seg
        return "equity"  # Default

    def _extract_indicators(self, prompt: str) -> List[Dict[str, Any]]:
        """
        Detect which technical indicators are mentioned in the prompt.

        Returns a list of dicts with ``indicator``, ``params``, and any
        explicit values the user provided (e.g. "RSI(7)" → period=7).
        """
        detected: List[Dict[str, Any]] = []
        for key, meta in self.indicators.items():
            if any(name in prompt for name in meta["names"]):
                entry: Dict[str, Any] = {
                    "indicator": key,
                    **meta["default_params"],
                }
                # Try to extract explicit period from patterns like "RSI 7", "RSI(7)"
                for name in meta["names"]:
                    pattern = rf"{re.escape(name)}\s*\(?\s*(\d+)\s*\)?"
                    m = re.search(pattern, prompt)
                    if m and "period" in meta["default_params"]:
                        entry["period"] = int(m.group(1))
                        break
                detected.append(entry)
        return detected

    def _extract_stop_loss(self, prompt: str) -> Optional[float]:
        """Extract stop-loss percentage from the prompt if present."""
        patterns = [
            r"(?:stop loss|sl|stop-loss)\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*%?",
            r"(\d+(?:\.\d+)?)\s*%\s+(?:stop loss|sl|stop-loss)",
        ]
        for pat in patterns:
            m = re.search(pat, prompt)
            if m:
                return float(m.group(1))
        return None

    def _extract_target(self, prompt: str) -> Optional[float]:
        """Extract profit target percentage from the prompt if present."""
        patterns = [
            r"(?:target|profit|tp|take profit)\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*%?",
            r"(\d+(?:\.\d+)?)\s*%\s+(?:target|profit|tp)",
            r"risk[- ]?reward\s+(?:ratio\s+)?(?:of\s+)?1\s*:\s*(\d+(?:\.\d+)?)",
        ]
        for pat in patterns:
            m = re.search(pat, prompt)
            if m:
                return float(m.group(1))
        return None

    def _extract_position_sizing(self, prompt: str) -> Optional[PositionSizingConfig]:
        """Extract position sizing hints from the prompt."""
        # Percentage of capital
        m = re.search(r"(\d+(?:\.\d+)?)\s*%\s+(?:of\s+)?(?:capital|portfolio|account)", prompt)
        if m:
            return PositionSizingConfig(type="pct_capital", value=float(m.group(1)))
        # Fixed quantity
        m = re.search(r"(\d+)\s+(?:shares?|lots?|quantity|qty)", prompt)
        if m:
            return PositionSizingConfig(type="fixed_qty", value=float(m.group(1)))
        # Risk-based
        m = re.search(r"risk\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*%\s+per\s+trade", prompt)
        if m:
            return PositionSizingConfig(
                type="risk_based",
                value=float(m.group(1)),
                risk_per_trade_pct=float(m.group(1)),
            )
        return None

    # ------------------------------------------------------------------
    # Default condition builders
    # ------------------------------------------------------------------

    @staticmethod
    def _default_entry_for_indicator(indicator_info: Dict[str, Any]) -> Condition:
        """Create a sensible default *entry* condition for a detected indicator."""
        name = indicator_info["indicator"]
        period = indicator_info.get("period")
        params = {k: v for k, v in indicator_info.items() if k != "indicator"}

        defaults: Dict[str, Dict[str, Any]] = {
            "rsi": {"condition": "<", "value": 30},
            "sma": {"condition": "crosses_above", "value": 50},
            "ema": {"condition": "crosses_above", "value": 200},
            "macd": {"condition": "crosses_above", "value": 0, "params": {"fast": 12, "slow": 26, "signal": 9}},
            "bollinger": {"condition": "<", "value": -2},
            "atr": {"condition": ">", "value": 1.5},
            "vwap": {"condition": "<", "value": -0.5},
            "stochastic": {"condition": "<", "value": 20, "params": {"k_period": 14, "d_period": 3}},
            "adx": {"condition": ">", "value": 25},
            "volume": {"condition": ">", "value": 1.5},
            "supertrend": {"condition": "==", "value": 1, "params": {"period": 10, "multiplier": 3}},
        }
        d = defaults.get(name, {"condition": ">", "value": 0})
        return Condition(
            indicator=name,
            condition=d["condition"],
            value=d["value"],
            period=period,
            params=d.get("params", params),
        )

    @staticmethod
    def _default_exit_for_indicator(indicator_info: Dict[str, Any]) -> Condition:
        """Create a sensible default *exit* condition for a detected indicator."""
        name = indicator_info["indicator"]
        period = indicator_info.get("period")
        params = {k: v for k, v in indicator_info.items() if k != "indicator"}

        defaults: Dict[str, Dict[str, Any]] = {
            "rsi": {"condition": ">", "value": 70},
            "sma": {"condition": "crosses_below", "value": 50},
            "ema": {"condition": "crosses_below", "value": 200},
            "macd": {"condition": "crosses_below", "value": 0, "params": {"fast": 12, "slow": 26, "signal": 9}},
            "bollinger": {"condition": ">", "value": 2},
            "atr": {"condition": "<", "value": 0.5},
            "vwap": {"condition": ">", "value": 0.5},
            "stochastic": {"condition": ">", "value": 80, "params": {"k_period": 14, "d_period": 3}},
            "adx": {"condition": "<", "value": 20},
            "volume": {"condition": "<", "value": 0.8},
            "supertrend": {"condition": "==", "value": -1, "params": {"period": 10, "multiplier": 3}},
        }
        d = defaults.get(name, {"condition": "<", "value": 0})
        return Condition(
            indicator=name,
            condition=d["condition"],
            value=d["value"],
            period=period,
            params=d.get("params", params),
        )

    @staticmethod
    def _build_description(
        name: str,
        instrument: str,
        timeframe: str,
        entries: List[Condition],
        exits: List[Condition],
        sl: StopLossConfig,
        tgt: TargetConfig,
    ) -> str:
        """Assemble a human-readable description string."""
        lines: List[str] = [f"{name} strategy for {instrument} on the {timeframe} timeframe."]
        lines.append("")
        lines.append("Entry: " + " AND ".join(
            f"{c.indicator.upper()}{f'({c.period})' if c.period else ''} {c.condition} {c.value}"
            for c in entries
        ) + ".")
        lines.append("Exit: " + " AND ".join(
            f"{c.indicator.upper()}{f'({c.period})' if c.period else ''} {c.condition} {c.value}"
            for c in exits
        ) + ".")
        lines.append(f"Stop-loss: {sl.type} = {sl.value}. Target: {tgt.type} = {tgt.value}.")
        return " ".join(lines)


# =============================================================================
# Utility functions
# =============================================================================


def format_strategy_for_display(strategy: StrategyOutput) -> str:
    """
    Pretty-print a strategy for terminal / log display.

    Parameters
    ----------
    strategy:
        The strategy to format.

    Returns
    -------
    str
        Multi-line formatted string with box-drawing characters.
    """
    lines = [
        "╔══════════════════════════════════════════════════════════════╗",
        f"║  Strategy: {strategy.strategy_name:<49} ║",
        "╠══════════════════════════════════════════════════════════════╣",
        f"║  Instrument : {strategy.instrument:<45} ║",
        f"║  Segment    : {strategy.segment:<45} ║",
        f"║  Timeframe  : {strategy.timeframe:<45} ║",
        f"║  Confidence : {strategy.confidence:<45.2%} ║",
        "╠══════════════════════════════════════════════════════════════╣",
        "║  ENTRY CONDITIONS                                            ║",
    ]
    for cond in strategy.entry_conditions:
        period_str = f"({cond.period})" if cond.period else ""
        line = f"    {cond.indicator.upper()}{period_str} {cond.condition} {cond.value}"
        lines.append(f"║{line:<62}║")

    lines.append("║                                                              ║")
    lines.append("║  EXIT CONDITIONS                                             ║")
    for cond in strategy.exit_conditions:
        period_str = f"({cond.period})" if cond.period else ""
        line = f"    {cond.indicator.upper()}{period_str} {cond.condition} {cond.value}"
        lines.append(f"║{line:<62}║")

    lines.extend([
        "╠══════════════════════════════════════════════════════════════╣",
        f"║  Stop Loss  : {strategy.stop_loss.type} = {strategy.stop_loss.value:<35} ║",
        f"║  Target     : {strategy.target.type} = {strategy.target.value:<35} ║",
        f"║  Position   : {strategy.position_sizing.type} = {strategy.position_sizing.value:<35} ║",
        "╚══════════════════════════════════════════════════════════════╝",
    ])
    return "\n".join(lines)


def merge_strategies(
    strategy_a: StrategyOutput,
    strategy_b: StrategyOutput,
    merge_name: Optional[str] = None,
) -> StrategyOutput:
    """
    Merge two strategies by combining their entry/exit conditions.

    Useful for ensemble strategies or combining signals from multiple
    sub-strategies.

    Parameters
    ----------
    strategy_a:
        First strategy (forms the base).
    strategy_b:
        Second strategy (conditions are appended).
    merge_name:
        Optional name for the merged strategy.

    Returns
    -------
    StrategyOutput
        New strategy with combined conditions.
    """
    return StrategyOutput(
        strategy_name=merge_name or f"Merged: {strategy_a.strategy_name} + {strategy_b.strategy_name}",
        description=f"Merged strategy combining {strategy_a.strategy_name} and {strategy_b.strategy_name}.",
        instrument=strategy_a.instrument,
        segment=strategy_a.segment,
        timeframe=strategy_a.timeframe,
        entry_conditions=strategy_a.entry_conditions + strategy_b.entry_conditions,
        exit_conditions=strategy_a.exit_conditions + strategy_b.exit_conditions,
        stop_loss=strategy_a.stop_loss,
        target=strategy_a.target,
        position_sizing=strategy_a.position_sizing,
        confidence=min(strategy_a.confidence, strategy_b.confidence) * 0.9,
        reasoning=f"Merged '{strategy_a.strategy_name}' with '{strategy_b.strategy_name}'.",
    )


def validate_strategy(strategy: StrategyOutput) -> Tuple[bool, List[str]]:
    """
    Validate a strategy for common issues.

    Parameters
    ----------
    strategy:
        The strategy to validate.

    Returns
    -------
    Tuple[bool, List[str]]
        ``(is_valid, list_of_issues)`` — empty issue list means fully valid.
    """
    issues: List[str] = []

    if not strategy.entry_conditions:
        issues.append("No entry conditions defined.")
    if not strategy.exit_conditions:
        issues.append("No exit conditions defined.")
    if strategy.stop_loss.value <= 0:
        issues.append("Stop-loss value must be positive.")
    if strategy.target.value <= 0:
        issues.append("Target value must be positive.")
    if strategy.confidence < 0.5:
        issues.append("Confidence score is low — consider manual review.")
    if strategy.position_sizing.value > strategy.position_sizing.max_position_pct:
        issues.append("Position size exceeds maximum allowed percentage.")

    # Check for duplicate conditions
    entry_keys = [f"{c.indicator}_{c.condition}_{c.value}" for c in strategy.entry_conditions]
    if len(entry_keys) != len(set(entry_keys)):
        issues.append("Duplicate entry conditions detected.")

    return len(issues) == 0, issues
