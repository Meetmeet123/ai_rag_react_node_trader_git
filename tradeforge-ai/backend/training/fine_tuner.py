"""
LLM Fine-Tuning Pipeline using LoRA / PEFT

Efficient fine-tuning of a base causal LM on trading-specific data.
Uses LoRA (Low-Rank Adaptation) for low-resource parameter-efficient training.

Key design decisions:
- LoRA instead of full fine-tuning: 10-100x fewer trainable parameters
- Causal LM objective: DialoGPT / GPT-2 style next-token prediction
- Checkpointing: saves only LoRA adapter weights (small, portable)
- Resume support: can resume from any saved checkpoint

Dependencies:
    transformers>=4.30.0
    peft>=0.4.0
    datasets>=2.12.0
    torch>=2.0.0
    accelerate>=0.20.0
    loguru>=0.7.0
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from loguru import logger

# ---------------------------------------------------------------------------
# Lazy imports for heavy ML libraries
# ---------------------------------------------------------------------------

_torch: Any = None
_AutoTokenizer: Any = None
_AutoModelForCausalLM: Any = None
_TrainingArguments: Any = None
_Trainer: Any = None
_DataCollatorForLanguageModeling: Any = None
_LoraConfig: Any = None
_get_peft_model: Any = None
_PeftModel: Any = None
_TaskType: Any = None
_Dataset: Any = None


def _load_deps() -> None:
    """Import heavy ML dependencies on first use."""
    global _torch, _AutoTokenizer, _AutoModelForCausalLM
    global _TrainingArguments, _Trainer, _DataCollatorForLanguageModeling
    global _LoraConfig, _get_peft_model, _PeftModel, _TaskType, _Dataset

    if _torch is not None:
        return

    import torch as __torch
    from transformers import (
        AutoTokenizer as __AutoTokenizer,
        AutoModelForCausalLM as __AutoModelForCausalLM,
        TrainingArguments as __TrainingArguments,
        Trainer as __Trainer,
        DataCollatorForLanguageModeling as __DataCollatorForLanguageModeling,
    )
    from peft import (
        LoraConfig as __LoraConfig,
        get_peft_model as __get_peft_model,
        PeftModel as __PeftModel,
        TaskType as __TaskType,
    )
    from datasets import Dataset as __Dataset

    _torch = __torch
    _AutoTokenizer = __AutoTokenizer
    _AutoModelForCausalLM = __AutoModelForCausalLM
    _TrainingArguments = __TrainingArguments
    _Trainer = __Trainer
    _DataCollatorForLanguageModeling = __DataCollatorForLanguageModeling
    _LoraConfig = __LoraConfig
    _get_peft_model = __get_peft_model
    _PeftModel = __PeftModel
    _TaskType = __TaskType
    _Dataset = __Dataset

    logger.debug("Fine-tuning dependencies loaded.")


# =============================================================================
# TradingLLMTrainer
# =============================================================================


class TradingLLMTrainer:
    """
    Fine-tunes a base causal LM on trading strategy data using LoRA.

    The trainer follows the standard HuggingFace ``Trainer`` pattern but wraps
    it with trading-specific defaults, checkpoint management, and convenient
    helper methods.

    Parameters
    ----------
    base_model:
        HuggingFace model identifier (e.g. ``"microsoft/DialoGPT-medium"``).
    output_dir:
        Directory where checkpoints and final model are saved.
    lora_r:
        LoRA rank — lower = fewer parameters, faster; higher = more expressive.
    lora_alpha:
        LoRA scaling parameter.  Common choice: ``2 * lora_r``.
    lora_dropout:
        Dropout applied to LoRA layers for regularisation.
    learning_rate:
        Peak learning rate for the AdamW optimiser.
    batch_size:
        Per-device batch size.  Effective batch = batch_size * gradient_accumulation * num_gpus.
    epochs:
        Number of training epochs.
    max_length:
        Maximum sequence length for tokenisation (truncation).
    gradient_accumulation_steps:
        Accumulate gradients over N steps before updating weights.
        Useful when GPU memory is limited.
    warmup_ratio:
        Fraction of training steps used for linear LR warmup.
    weight_decay:
        L2 regularisation coefficient.
    logging_steps:
        Log metrics every N steps.
    save_steps:
        Save checkpoint every N steps.
    device:
        ``"auto"`` selects CUDA when available, else CPU.
    quantization:
        ``"4bit"`` or ``"8bit"`` for BitsAndBytes quantisation, or ``None``.

    Example
    -------
    .. code-block:: python

        from training.dataset_builder import StrategyDatasetBuilder
        from training.fine_tuner import TradingLLMTrainer

        # 1. Build dataset
        builder = StrategyDatasetBuilder()
        dataset = builder.build_full_dataset()

        # 2. Train
        trainer = TradingLLMTrainer(
            base_model="microsoft/DialoGPT-medium",
            output_dir="./checkpoints",
            epochs=5,
        )
        trainer.prepare_model()
        checkpoint_path = trainer.train(dataset)
        print(f"Saved to: {checkpoint_path}")
    """

    # Default LoRA target modules for DialoGPT / GPT-2 style models
    _DEFAULT_LORA_TARGETS: List[str] = [
        "c_attn",   # Self-attention projection (GPT-2)
        "c_proj",   # Output projection
        "c_fc",     # Feed-forward intermediate
    ]

    # Alternative target modules for other model families
    _LORA_TARGET_MAP: Dict[str, List[str]] = {
        "gpt2": ["c_attn", "c_proj", "c_fc"],
        "gpt_neo": ["q_proj", "v_proj", "k_proj", "out_proj"],
        "gpt_neox": ["query_key_value", "dense"],
        "llama": ["q_proj", "v_proj", "k_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        "opt": ["q_proj", "v_proj", "k_proj", "out_proj"],
    }

    def __init__(
        self,
        base_model: str = "microsoft/DialoGPT-medium",
        output_dir: str = "./training/checkpoints",
        lora_r: int = 16,
        lora_alpha: int = 32,
        lora_dropout: float = 0.05,
        learning_rate: float = 2e-5,
        batch_size: int = 4,
        epochs: int = 3,
        max_length: int = 512,
        gradient_accumulation_steps: int = 4,
        warmup_ratio: float = 0.03,
        weight_decay: float = 0.01,
        logging_steps: int = 50,
        save_steps: int = 500,
        eval_steps: int = 500,
        device: str = "auto",
        quantization: Optional[str] = None,
        bf16: bool = False,
        fp16: bool = True,
        gradient_checkpointing: bool = True,
        save_total_limit: int = 3,
        random_seed: int = 42,
    ) -> None:
        _load_deps()

        self.base_model_name: str = base_model
        self.output_dir: str = output_dir
        self.lora_r: int = lora_r
        self.lora_alpha: int = lora_alpha
        self.lora_dropout: float = lora_dropout
        self.learning_rate: float = learning_rate
        self.batch_size: int = batch_size
        self.epochs: int = epochs
        self.max_length: int = max_length
        self.gradient_accumulation_steps: int = gradient_accumulation_steps
        self.warmup_ratio: float = warmup_ratio
        self.weight_decay: float = weight_decay
        self.logging_steps: int = logging_steps
        self.save_steps: int = save_steps
        self.eval_steps: int = eval_steps
        self.quantization: Optional[str] = quantization
        self.bf16: bool = bf16
        self.fp16: bool = fp16
        self.gradient_checkpointing: bool = gradient_checkpointing
        self.save_total_limit: int = save_total_limit
        self.random_seed: int = random_seed

        # Device
        if device == "auto":
            self.device: str = "cuda" if _torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        # Internal handles (populated by prepare_model)
        self.tokenizer: Optional[Any] = None
        self.base_model: Optional[Any] = None
        self.peft_model: Optional[Any] = None
        self.data_collator: Optional[Any] = None
        self.training_args: Optional[Any] = None
        self._is_prepared: bool = False

        # Training history
        self._training_history: List[Dict[str, Any]] = []
        self._final_checkpoint_path: Optional[str] = None

        logger.info(
            f"TradingLLMTrainer initialised — base={base_model}, "
            f"LoRA(r={lora_r}, alpha={lora_alpha}), epochs={epochs}, "
            f"lr={learning_rate}, device={self.device}"
        )

    # ------------------------------------------------------------------
    # Model preparation
    # ------------------------------------------------------------------

    def prepare_model(self) -> None:
        """
        Load the base model + tokenizer and apply LoRA configuration.

        This must be called before ``train()``.
        """
        _load_deps()
        logger.info(f"Loading base model: {self.base_model_name} ...")

        # ---- Tokenizer ------------------------------------------------
        self.tokenizer = _AutoTokenizer.from_pretrained(
            self.base_model_name,
            trust_remote_code=True,
            use_fast=True,
        )
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
            self.tokenizer.pad_token_id = self.tokenizer.eos_token_id

        # ---- Model loading --------------------------------------------
        model_kwargs: Dict[str, Any] = {
            "trust_remote_code": True,
        }

        # Quantisation
        if self.quantization == "4bit":
            from transformers import BitsAndBytesConfig
            model_kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=_torch.float16,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
            )
            model_kwargs["device_map"] = "auto"
        elif self.quantization == "8bit":
            model_kwargs["load_in_8bit"] = True
            model_kwargs["device_map"] = "auto"
        else:
            model_kwargs["torch_dtype"] = (
                _torch.float16 if self.device == "cuda" else _torch.float32
            )
            if self.device == "cuda":
                model_kwargs["device_map"] = "auto"

        self.base_model = _AutoModelForCausalLM.from_pretrained(
            self.base_model_name,
            **model_kwargs,
        )

        if self.gradient_checkpointing:
            self.base_model.gradient_checkpointing_enable()

        # ---- LoRA configuration ---------------------------------------
        target_modules = self._resolve_lora_targets(self.base_model_name)
        lora_config = _LoraConfig(
            r=self.lora_r,
            lora_alpha=self.lora_alpha,
            target_modules=target_modules,
            lora_dropout=self.lora_dropout,
            bias="none",
            task_type=_TaskType.CAUSAL_LM,
        )

        self.peft_model = _get_peft_model(self.base_model, lora_config)
        self.peft_model.print_trainable_parameters()

        # ---- Data collator --------------------------------------------
        self.data_collator = _DataCollatorForLanguageModeling(
            tokenizer=self.tokenizer,
            mlm=False,  # Causal LM — not masked
        )

        self._is_prepared = True
        logger.info("Model prepared successfully with LoRA adapters.")

    def _resolve_lora_targets(self, model_name: str) -> List[str]:
        """
        Auto-detect LoRA target modules based on model architecture.

        Falls back to the default GPT-2 target set if the model family
        cannot be identified.
        """
        model_name_lower = model_name.lower()
        for family, targets in self._LORA_TARGET_MAP.items():
            if family in model_name_lower:
                logger.info(f"Detected model family '{family}' — using targets: {targets}")
                return targets

        logger.info(f"Using default LoRA targets: {self._DEFAULT_LORA_TARGETS}")
        return self._DEFAULT_LORA_TARGETS

    # ------------------------------------------------------------------
    # Tokenisation
    # ------------------------------------------------------------------

    def tokenize_dataset(
        self,
        dataset: "Dataset",  # type: ignore[name-defined]
        text_column: str = "text",
    ) -> "Dataset":  # type: ignore[name-defined]
        """
        Tokenise a HuggingFace Dataset for training.

        Parameters
        ----------
        dataset:
            HuggingFace Dataset with a text column.
        text_column:
            Name of the column containing text strings.

        Returns
        -------
        datasets.Dataset
            Tokenised dataset with ``input_ids``, ``attention_mask`` columns.
        """
        if self.tokenizer is None:
            raise RuntimeError("Tokenizer not initialised. Call prepare_model() first.")

        def _tokenize_fn(examples: Dict[str, List[str]]) -> Dict[str, Any]:
            return self.tokenizer(
                examples[text_column],
                truncation=True,
                max_length=self.max_length,
                padding="max_length",
            )

        tokenized = dataset.map(
            _tokenize_fn,
            batched=True,
            remove_columns=dataset.column_names,
        )
        logger.info(f"Tokenised {len(tokenized)} examples.")
        return tokenized

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train(
        self,
        dataset: "Dataset",  # type: ignore[name-defined]
        eval_dataset: Optional["Dataset"] = None,  # type: ignore[name-defined]
        resume_from_checkpoint: Optional[str] = None,
    ) -> str:
        """
        Fine-tune the model on the provided dataset.

        Parameters
        ----------
        dataset:
            HuggingFace Dataset with ``text`` column (or pre-tokenised columns).
        eval_dataset:
            Optional validation dataset.
        resume_from_checkpoint:
            Path to a checkpoint to resume training from.

        Returns
        -------
        str
            Path to the saved checkpoint directory.
        """
        _load_deps()

        if not self._is_prepared:
            raise RuntimeError("Model not prepared. Call prepare_model() first.")

        if self.peft_model is None or self.tokenizer is None:
            raise RuntimeError("PEFT model or tokenizer not initialised.")

        # Tokenise if needed
        sample = dataset[0]
        if "input_ids" not in sample:
            logger.info("Tokenising training dataset ...")
            dataset = self.tokenize_dataset(dataset)
        if eval_dataset is not None and "input_ids" not in eval_dataset[0]:
            logger.info("Tokenising evaluation dataset ...")
            eval_dataset = self.tokenize_dataset(eval_dataset)

        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)

        # Timestamped run directory
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = os.path.join(self.output_dir, f"run_{run_id}")
        os.makedirs(run_dir, exist_ok=True)

        # ---- Training arguments ---------------------------------------
        # Effective batch size = batch_size * gradient_accumulation * num_gpus
        effective_batch = self.batch_size * self.gradient_accumulation_steps
        if _torch.cuda.device_count() > 1:
            effective_batch *= _torch.cuda.device_count()

        self.training_args = _TrainingArguments(
            output_dir=run_dir,
            overwrite_output_dir=True,
            num_train_epochs=self.epochs,
            per_device_train_batch_size=self.batch_size,
            per_device_eval_batch_size=self.batch_size,
            gradient_accumulation_steps=self.gradient_accumulation_steps,
            learning_rate=self.learning_rate,
            weight_decay=self.weight_decay,
            warmup_ratio=self.warmup_ratio,
            logging_dir=os.path.join(run_dir, "logs"),
            logging_steps=self.logging_steps,
            save_steps=self.save_steps,
            save_total_limit=self.save_total_limit,
            eval_steps=self.eval_steps,
            evaluation_strategy="steps" if eval_dataset is not None else "no",
            load_best_model_at_end=eval_dataset is not None,
            metric_for_best_model="eval_loss" if eval_dataset is not None else None,
            greater_is_better=False,
            bf16=self.bf16 and _torch.cuda.is_available() and _torch.cuda.is_bf16_supported(),
            fp16=self.fp16 and _torch.cuda.is_available() and not self.bf16,
            gradient_checkpointing=self.gradient_checkpointing,
            report_to=["tensorboard"],
            seed=self.random_seed,
            data_seed=self.random_seed,
            dataloader_num_workers=2,
            remove_unused_columns=False,
        )

        logger.info(
            f"Training config — effective_batch={effective_batch}, "
            f"epochs={self.epochs}, lr={self.learning_rate}, run_dir={run_dir}"
        )

        # ---- Trainer --------------------------------------------------
        trainer = _Trainer(
            model=self.peft_model,
            args=self.training_args,
            train_dataset=dataset,
            eval_dataset=eval_dataset,
            data_collator=self.data_collator,
            tokenizer=self.tokenizer,
        )

        # ---- Train ----------------------------------------------------
        logger.info("Starting training ...")
        train_start = time.perf_counter()

        try:
            train_result = trainer.train(resume_from_checkpoint=resume_from_checkpoint)

            train_duration = time.perf_counter() - train_start
            metrics = train_result.metrics

            # Record history
            self._training_history.append({
                "run_id": run_id,
                "duration_sec": train_duration,
                "metrics": metrics,
                "run_dir": run_dir,
                "config": self._get_config_dict(),
            })

            logger.info(
                f"Training complete in {train_duration:.1f}s — "
                f"final_loss={metrics.get('train_loss', 'N/A')}"
            )

        except Exception as exc:
            logger.error(f"Training failed: {exc}")
            raise

        # ---- Save final checkpoint ------------------------------------
        final_path = os.path.join(run_dir, "final")
        self.save_checkpoint(final_path)
        self._final_checkpoint_path = final_path

        # Save training config
        config_path = os.path.join(run_dir, "training_config.json")
        with open(config_path, "w", encoding="utf-8") as fh:
            json.dump(self._get_config_dict(), fh, indent=2, ensure_ascii=False)

        logger.info(f"Final checkpoint saved to: {final_path}")
        return final_path

    def train_from_pairs(
        self,
        pairs: List[Dict[str, str]],
        validation_split: float = 0.1,
        **kwargs: Any,
    ) -> str:
        """
        Convenience method: build dataset from prompt-response pairs and train.

        Parameters
        ----------
        pairs:
            List of ``{"prompt": ..., "response": ...}`` dicts.
        validation_split:
            Fraction of data for validation.
        **kwargs:
            Additional args forwarded to ``train()``.

        Returns
        -------
        str
            Path to saved checkpoint.
        """
        from training.dataset_builder import StrategyDatasetBuilder

        builder = StrategyDatasetBuilder(validation_split=validation_split)
        dataset = builder._pairs_to_dataset(pairs)  # type: ignore[attr-defined]
        eval_dataset = builder.get_validation_split()

        return self.train(dataset, eval_dataset=eval_dataset, **kwargs)

    # ------------------------------------------------------------------
    # Checkpoint management
    # ------------------------------------------------------------------

    def save_checkpoint(self, path: str) -> None:
        """
        Save LoRA adapter weights to *path*.

        Only the small adapter weights are saved (not the full base model),
        making checkpoints typically < 50 MB.
        """
        if self.peft_model is None:
            raise RuntimeError("No PEFT model to save. Call prepare_model() first.")

        os.makedirs(path, exist_ok=True)
        self.peft_model.save_pretrained(path)
        if self.tokenizer is not None:
            self.tokenizer.save_pretrained(path)

        # Save metadata
        meta = {
            "base_model": self.base_model_name,
            "lora_config": {
                "r": self.lora_r,
                "alpha": self.lora_alpha,
                "dropout": self.lora_dropout,
            },
            "saved_at": datetime.now().isoformat(),
        }
        with open(os.path.join(path, "adapter_meta.json"), "w", encoding="utf-8") as fh:
            json.dump(meta, fh, indent=2)

        logger.info(f"Checkpoint saved to {path}")

    def load_checkpoint(self, path: str) -> None:
        """
        Load LoRA adapter weights from *path*.

        The base model must already be loaded via ``prepare_model()``.
        """
        if self.peft_model is None:
            raise RuntimeError("Base model not prepared. Call prepare_model() first.")

        if not os.path.isdir(path):
            raise FileNotFoundError(f"Checkpoint directory not found: {path}")

        logger.info(f"Loading checkpoint from {path} ...")
        self.peft_model = _PeftModel.from_pretrained(self.peft_model, path)
        logger.info("Checkpoint loaded successfully.")

    def merge_and_save(self, output_path: str) -> None:
        """
        Merge LoRA weights into the base model and save the complete model.

        This produces a standalone model that does not require PEFT at
        inference time (larger file but simpler deployment).

        Parameters
        ----------
        output_path:
            Directory to save the merged model.
        """
        if self.peft_model is None:
            raise RuntimeError("No PEFT model to merge. Call prepare_model() first.")

        logger.info("Merging LoRA weights into base model ...")
        merged = self.peft_model.merge_and_unload()
        os.makedirs(output_path, exist_ok=True)
        merged.save_pretrained(output_path)
        if self.tokenizer is not None:
            self.tokenizer.save_pretrained(output_path)
        logger.info(f"Merged model saved to {output_path}")

    # ------------------------------------------------------------------
    # Training utilities
    # ------------------------------------------------------------------

    def estimate_memory_usage(self) -> Dict[str, str]:
        """
        Estimate GPU / system memory requirements for training.

        Returns
        -------
        Dict[str, str]
            Human-readable memory estimates.
        """
        estimates: Dict[str, str] = {}

        # Rough heuristic (GB) for DialoGPT-medium + LoRA(r=16)
        param_count_b = 345e6  # 345M params for DialoGPT-medium
        bytes_per_param = 2 if self.fp16 else 4  # float16 vs float32
        model_size_gb = (param_count_b * bytes_per_param) / 1e9

        # LoRA adds ~0.1-1% extra params
        lora_pct = (self.lora_r * self.lora_alpha) / param_count_b * 100
        lora_overhead_gb = model_size_gb * 0.005  # ~0.5% overhead

        # AdamW needs 2x model size for optimiser states
        optimizer_gb = model_size_gb * 2

        # Activations + gradients (rough)
        activation_gb = model_size_gb * 0.5

        total_training_gb = model_size_gb + lora_overhead_gb + optimizer_gb + activation_gb

        estimates["model_weights"] = f"{model_size_gb:.2f} GB"
        estimates["lora_overhead"] = f"{lora_overhead_gb:.2f} GB ({lora_pct:.2f}% extra params)"
        estimates["optimizer_states"] = f"{optimizer_gb:.2f} GB"
        estimates["activations_gradients"] = f"{activation_gb:.2f} GB"
        estimates["total_training"] = f"{total_training_gb:.2f} GB"
        estimates["recommendation"] = (
            f"A GPU with {int(total_training_gb * 1.3) + 1} GB VRAM is recommended."
        )

        return estimates

    def get_trainable_parameters(self) -> Dict[str, Any]:
        """
        Get statistics about trainable vs frozen parameters.

        Returns
        -------
        Dict[str, Any]
            Total, trainable, and frozen parameter counts.
        """
        if self.peft_model is None:
            return {"error": "Model not prepared"}

        total = sum(p.numel() for p in self.peft_model.parameters())
        trainable = sum(p.numel() for p in self.peft_model.parameters() if p.requires_grad)
        frozen = total - trainable

        return {
            "total_parameters": total,
            "trainable_parameters": trainable,
            "frozen_parameters": frozen,
            "trainable_pct": f"{100 * trainable / total:.4f}%",
            "total_million": f"{total / 1e6:.2f}M",
            "trainable_million": f"{trainable / 1e6:.4f}M",
        }

    def get_training_stats(self) -> Dict[str, Any]:
        """
        Return training history and current status.

        Returns
        -------
        Dict[str, Any]
            Training runs, metrics, and configuration.
        """
        return {
            "training_history": self._training_history,
            "final_checkpoint_path": self._final_checkpoint_path,
            "is_prepared": self._is_prepared,
            "config": self._get_config_dict(),
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_config_dict(self) -> Dict[str, Any]:
        """Serialise the trainer configuration to a dictionary."""
        return {
            "base_model": self.base_model_name,
            "lora_r": self.lora_r,
            "lora_alpha": self.lora_alpha,
            "lora_dropout": self.lora_dropout,
            "learning_rate": self.learning_rate,
            "batch_size": self.batch_size,
            "epochs": self.epochs,
            "max_length": self.max_length,
            "gradient_accumulation_steps": self.gradient_accumulation_steps,
            "warmup_ratio": self.warmup_ratio,
            "weight_decay": self.weight_decay,
            "device": self.device,
            "quantization": self.quantization,
            "bf16": self.bf16,
            "fp16": self.fp16,
            "gradient_checkpointing": self.gradient_checkpointing,
        }


# =============================================================================
# Checkpoint manager — standalone utility
# =============================================================================


class CheckpointManager:
    """
    Manage LoRA checkpoints: listing, comparison, pruning, and rollback.

    This is a utility class that operates on the checkpoint directory
    independently of the trainer.
    """

    def __init__(self, checkpoint_dir: str) -> None:
        self.checkpoint_dir = checkpoint_dir
        logger.info(f"CheckpointManager initialised — dir={checkpoint_dir}")

    def list_checkpoints(self) -> List[Dict[str, Any]]:
        """
        List all checkpoints in the checkpoint directory.

        Returns
        -------
        List[Dict[str, Any]]
            Each dict has ``path``, ``name``, ``size_mb``, ``created``, and
            ``metadata`` keys.
        """
        if not os.path.isdir(self.checkpoint_dir):
            return []

        checkpoints: List[Dict[str, Any]] = []
        for entry in os.listdir(self.checkpoint_dir):
            path = os.path.join(self.checkpoint_dir, entry)
            if not os.path.isdir(path):
                continue
            # Check for adapter files
            has_adapter = os.path.isfile(os.path.join(path, "adapter_config.json"))
            if not has_adapter:
                # Check subdirectories (HuggingFace Trainer structure)
                for sub in os.listdir(path):
                    sub_path = os.path.join(path, sub)
                    if os.path.isdir(sub_path) and os.path.isfile(
                        os.path.join(sub_path, "adapter_config.json")
                    ):
                        checkpoints.append(self._describe_checkpoint(sub_path))
                continue

            checkpoints.append(self._describe_checkpoint(path))

        checkpoints.sort(key=lambda c: c.get("created", ""), reverse=True)
        return checkpoints

    def _describe_checkpoint(self, path: str) -> Dict[str, Any]:
        """Build a description dict for a single checkpoint."""
        total_size = sum(
            os.path.getsize(os.path.join(dirpath, f))
            for dirpath, _, filenames in os.walk(path)
            for f in filenames
        )
        created = datetime.fromtimestamp(os.path.getctime(path)).isoformat()

        meta_path = os.path.join(path, "adapter_meta.json")
        metadata: Dict[str, Any] = {}
        if os.path.isfile(meta_path):
            with open(meta_path, "r", encoding="utf-8") as fh:
                metadata = json.load(fh)

        return {
            "path": path,
            "name": os.path.basename(path),
            "size_mb": round(total_size / (1024 * 1024), 2),
            "created": created,
            "metadata": metadata,
        }

    def prune_old_checkpoints(self, keep: int = 3) -> List[str]:
        """
        Remove all but the *keep* most recent checkpoints.

        Parameters
        ----------
        keep:
            Number of checkpoints to retain.

        Returns
        -------
        List[str]
            Paths of removed checkpoints.
        """
        checkpoints = self.list_checkpoints()
        if len(checkpoints) <= keep:
            return []

        to_remove = checkpoints[keep:]
        removed: List[str] = []
        for ckpt in to_remove:
            import shutil
            shutil.rmtree(ckpt["path"], ignore_errors=True)
            removed.append(ckpt["path"])
            logger.info(f"Pruned checkpoint: {ckpt['path']}")

        return removed

    def get_best_checkpoint(self, metric: str = "eval_loss") -> Optional[Dict[str, Any]]:
        """
        Find the checkpoint with the best validation metric.

        Parameters
        ----------
        metric:
            Metric name to optimise (default: ``eval_loss`` — lower is better).

        Returns
        -------
        Dict[str, Any] or None
            Best checkpoint description, or None if no checkpoints found.
        """
        checkpoints = self.list_checkpoints()
        if not checkpoints:
            return None

        # Read trainer_state.json for metrics
        best_ckpt: Optional[Dict[str, Any]] = None
        best_value: float = float("inf")

        for ckpt in checkpoints:
            state_path = os.path.join(ckpt["path"], "trainer_state.json")
            if not os.path.isfile(state_path):
                continue
            try:
                with open(state_path, "r", encoding="utf-8") as fh:
                    state = json.load(fh)
                log_history = state.get("log_history", [])
                for entry in log_history:
                    if metric in entry:
                        val = entry[metric]
                        if val < best_value:
                            best_value = val
                            best_ckpt = ckpt
            except Exception:
                continue

        return best_ckpt


# =============================================================================
# Convenience factory
# =============================================================================


def create_trainer_with_defaults(
    base_model: str = "microsoft/DialoGPT-medium",
    output_dir: str = "./training/checkpoints",
    **kwargs: Any,
) -> TradingLLMTrainer:
    """
    Factory function that creates a pre-configured ``TradingLLMTrainer``.

    Sensible defaults for different hardware configurations are applied
    automatically based on available GPU memory.

    Parameters
    ----------
    base_model:
        Model identifier.
    output_dir:
        Checkpoint output directory.
    **kwargs:
        Overrides for any trainer parameter.

    Returns
    -------
    TradingLLMTrainer
        Configured and ready for ``prepare_model()`` → ``train()``.
    """
    _load_deps()

    # Auto-detect GPU memory and adjust settings
    if _torch.cuda.is_available():
        gpu_mem_gb = _torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
        logger.info(f"Detected GPU with {gpu_mem_gb:.1f} GB VRAM")

        if gpu_mem_gb < 6:
            # Low-VRAM: 4-bit quantisation + small batch
            defaults = {
                "batch_size": 1,
                "gradient_accumulation_steps": 8,
                "quantization": "4bit",
                "lora_r": 8,
                "lora_alpha": 16,
                "gradient_checkpointing": True,
            }
        elif gpu_mem_gb < 12:
            # Mid-range: 8-bit quantisation
            defaults = {
                "batch_size": 2,
                "gradient_accumulation_steps": 4,
                "quantization": "8bit",
                "lora_r": 16,
                "lora_alpha": 32,
                "gradient_checkpointing": True,
            }
        else:
            # High-VRAM: no quantisation
            defaults = {
                "batch_size": 4,
                "gradient_accumulation_steps": 2,
                "quantization": None,
                "lora_r": 16,
                "lora_alpha": 32,
                "gradient_checkpointing": True,
            }
    else:
        # CPU-only: minimal settings
        defaults = {
            "batch_size": 1,
            "gradient_accumulation_steps": 8,
            "quantization": None,
            "lora_r": 8,
            "lora_alpha": 16,
            "device": "cpu",
            "fp16": False,
            "bf16": False,
        }
        logger.warning("No GPU detected — using CPU-only configuration (very slow).")

    # Override defaults with user-provided kwargs
    defaults.update(kwargs)
    defaults["base_model"] = base_model
    defaults["output_dir"] = output_dir

    return TradingLLMTrainer(**defaults)
