"""Tests for the LLMEngine training pipeline."""

from __future__ import annotations

import os
import shutil
from typing import Any, Dict, List

import pytest

from core.llm_engine import LLMEngine
from training.dataset_builder import StrategyDatasetBuilder


@pytest.mark.slow
@pytest.mark.training
async def test_llm_engine_fine_tune(tmp_path: Any) -> None:
    """Fine-tune a tiny dataset and verify the checkpoint is saved."""
    # Build a tiny dataset from built-in prompt-response pairs.
    builder = StrategyDatasetBuilder(max_length=64, validation_split=0.0)
    full_dataset = builder.build_full_dataset()
    tiny_dataset = full_dataset.select(range(min(4, len(full_dataset))))
    assert len(tiny_dataset) == 4
    assert "text" in tiny_dataset.column_names

    # Use a small base model and a short sequence length to keep the test fast.
    checkpoint_dir = tmp_path / "checkpoints"
    engine = LLMEngine(
        base_model="gpt2",
        max_length=64,
        device="cpu",
        use_lora=False,  # fine_tune applies its own LoRA adapter
        checkpoint_dir=str(checkpoint_dir),
    )
    assert engine.is_ready()

    progress_updates: List[Dict[str, Any]] = []

    async def _progress_cb(update: Dict[str, Any]) -> None:
        progress_updates.append(update)

    checkpoint_path = await engine.fine_tune(
        dataset=tiny_dataset,
        epochs=1,
        batch_size=2,
        learning_rate=5e-5,
        job_id=999,
        progress_callback=_progress_cb,
    )

    try:
        assert isinstance(checkpoint_path, str)
        assert os.path.isdir(checkpoint_path)

        # LoRA adapter artefacts should be present, or a full model checkpoint.
        has_adapter = os.path.isfile(os.path.join(checkpoint_path, "adapter_config.json"))
        has_pytorch_model = os.path.isfile(os.path.join(checkpoint_path, "pytorch_model.bin"))
        has_safetensors = any(
            fname.endswith(".safetensors")
            for fname in os.listdir(checkpoint_path)
        )
        assert has_adapter or has_pytorch_model or has_safetensors

        # Tokenizer should also have been saved alongside the adapter.
        assert os.path.isfile(os.path.join(checkpoint_path, "tokenizer_config.json"))

        # Progress callback should have received at least one update.
        assert len(progress_updates) > 0
    finally:
        shutil.rmtree(checkpoint_path, ignore_errors=True)


def test_llm_engine_get_model_info() -> None:
    """``get_model_info`` should report model architecture and readiness."""
    engine = LLMEngine(
        base_model="gpt2",
        max_length=64,
        device="cpu",
        use_lora=False,
    )
    info = engine.get_model_info()

    assert info["base_model"] == "gpt2"
    assert info["device"] == "cpu"
    assert info["quantization"] is None
    assert info["model_loaded"] is engine.is_ready()
