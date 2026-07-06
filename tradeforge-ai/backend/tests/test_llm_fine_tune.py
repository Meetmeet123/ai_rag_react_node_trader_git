"""Fine-tuning integration test for LLMEngine."""

from __future__ import annotations

import os
import shutil
from typing import Any

import pytest

from core.llm_engine import LLMEngine
from training.dataset_builder import StrategyDatasetBuilder


@pytest.mark.slow
@pytest.mark.training
async def test_llm_engine_fine_tune_checkpoint_saved(tmp_path: Any) -> None:
    """Fine-tune a tiny dataset and verify the LoRA checkpoint is saved."""
    strategy = {
        "strategy_name": "Test Mean Reversion",
        "description": "A minimal test strategy.",
        "instrument": "RELIANCE",
        "segment": "equity",
        "timeframe": "15m",
        "entry_conditions": [
            {"indicator": "rsi", "period": 14, "condition": "<", "value": 30}
        ],
        "exit_conditions": [
            {"indicator": "rsi", "period": 14, "condition": ">", "value": 70}
        ],
        "stop_loss": {"type": "fixed_pct", "value": 1.0},
        "target": {"type": "fixed_pct", "value": 2.0},
        "position_sizing": {"type": "pct_capital", "value": 10},
        "confidence": 0.8,
        "reasoning": "Test reasoning.",
    }

    builder = StrategyDatasetBuilder(max_length=64, validation_split=0.0)
    dataset = builder.build_from_strategies([strategy])

    checkpoint_dir = tmp_path / "checkpoints"
    engine = LLMEngine(
        base_model="gpt2",
        device="cpu",
        use_lora=True,
        checkpoint_dir=str(checkpoint_dir),
    )

    output_path = await engine.fine_tune(
        dataset=dataset,
        checkpoint_path=None,
        epochs=1,
        learning_rate=5e-5,
        batch_size=1,
        job_id=999,
        progress_callback=None,
    )

    try:
        assert os.path.isdir(output_path)
        assert os.path.isfile(os.path.join(output_path, "adapter_config.json"))
    finally:
        shutil.rmtree(output_path, ignore_errors=True)
