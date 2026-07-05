"""
TradeForge AI — Training Package

Provides dataset building, model fine-tuning, and reinforcement learning
capabilities for the trading LLM.

Modules:
    dataset_builder: StrategyDatasetBuilder, MarketDatasetBuilder
    fine_tuner: TradingLLMTrainer, CheckpointManager
    reinforcement: TradeExecutionRL, DeepTradeExecutionRL
"""

from training.dataset_builder import (
    MarketDatasetBuilder,
    StrategyDatasetBuilder,
    build_combined_dataset,
)
from training.fine_tuner import (
    CheckpointManager,
    TradingLLMTrainer,
    create_trainer_with_defaults,
)
from training.reinforcement import (
    Action,
    DeepTradeExecutionRL,
    EpisodeResult,
    TradeExecutionRL,
    TradeState,
    create_agent_for_market,
    train_and_evaluate,
)

__all__ = [
    # Dataset building
    "StrategyDatasetBuilder",
    "MarketDatasetBuilder",
    "build_combined_dataset",
    # Fine-tuning
    "TradingLLMTrainer",
    "CheckpointManager",
    "create_trainer_with_defaults",
    # Reinforcement learning
    "TradeExecutionRL",
    "DeepTradeExecutionRL",
    "TradeState",
    "Action",
    "EpisodeResult",
    "create_agent_for_market",
    "train_and_evaluate",
]
