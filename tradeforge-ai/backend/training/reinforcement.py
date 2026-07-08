"""
Reinforcement Learning module for optimizing trade execution.

Uses Q-Learning to learn optimal:
- Entry timing (when to enter a trade)
- Position sizing adjustments (scale up/down based on state)
- Stop-loss modifications based on market conditions

The state space captures technical indicator readings, market regime,
and temporal features. The action space is {HOLD, BUY/ENTER, SELL/EXIT}.

Design philosophy:
- Discrete Q-Learning for interpretability and fast training
- State binning to handle continuous indicator values
- Epsilon-greedy exploration with decay
- Reward shaping based on risk-adjusted returns

Dependencies:
    numpy>=1.24.0
    pandas>=2.0.0
    loguru>=0.7.0
"""

from __future__ import annotations

import json
import os
import pickle
import random
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import IntEnum
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from loguru import logger

# =============================================================================
# Data structures
# =============================================================================


class Action(IntEnum):
    """
    Discrete actions available to the RL agent.

    These map to trading decisions at each time step:
    - ``HOLD``: No action / maintain current position
    - ``ENTER``: Open a new long position (or add to existing)
    - ``EXIT``: Close the current position
    """

    HOLD = 0
    ENTER = 1
    EXIT = 2


@dataclass(frozen=True)
class TradeState:
    """
    Compact state representation for the RL agent.

    All fields are normalised to [-1, 1] or [0, 1] where possible
    to ensure stable Q-table indexing and learning.

    Parameters
    ----------
    rsi : float
        RSI value normalised to [-1, 1]:  (rsi - 50) / 50
    macd : float
        MACD histogram value, clipped and normalised to [-1, 1]
    price_vs_sma20 : float
        Price deviation from SMA(20) as percentage, normalised
    price_vs_sma50 : float
        Price deviation from SMA(50) as percentage, normalised
    volume_ratio : float
        Current volume / 20-period average volume, log-normalised
    trend_direction : int
        1 = price above both SMA20 and SMA50 (uptrend)
        -1 = price below both (downtrend)
        0 = mixed / sideways
    time_of_day : float
        Normalised to [0, 1] where 0 = market open, 1 = market close
    day_of_week : int
        0 = Monday, ..., 4 = Friday (intraday only)

    Notes
    -----
    The state is intentionally compact (8 dimensions) to keep the
    Q-table manageable.  For higher-dimensional state spaces consider
    switching to a DQN (deep Q-network) approximation.
    """

    rsi: float
    macd: float
    price_vs_sma20: float
    price_vs_sma50: float
    volume_ratio: float
    trend_direction: int
    time_of_day: float
    day_of_week: int

    def to_array(self) -> np.ndarray:
        """Convert state to a NumPy array for indexing / ML."""
        return np.array(
            [
                self.rsi,
                self.macd,
                self.price_vs_sma20,
                self.price_vs_sma50,
                self.volume_ratio,
                float(self.trend_direction),
                self.time_of_day,
                float(self.day_of_week) / 4.0,  # normalise to [0, 1]
            ],
            dtype=np.float32,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TradeState":
        """Reconstruct from a dictionary."""
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def __hash__(self) -> int:
        """Enable use as dict key for Q-table."""
        return hash(tuple(self.to_array().round(4)))


@dataclass
class EpisodeResult:
    """Summary statistics for a single training episode."""

    episode: int
    total_reward: float
    n_trades: int
    n_wins: int
    n_losses: int
    win_rate: float
    final_q_table_size: int
    epsilon: float


# =============================================================================
# TradeExecutionRL — Q-Learning agent
# =============================================================================


class TradeExecutionRL:
    """
    Q-Learning agent for trade execution optimization.

    Learns a policy that maps market states to trading actions
    (HOLD / ENTER / EXIT) to maximise cumulative risk-adjusted returns.

    The agent uses a discretised state space and a Q-table for
    exact value storage.  This makes it:
    - Fast to train (no neural network)
    - Fully interpretable (can inspect Q-values for any state)
    - Lightweight to deploy (small pickle file)

    For continuous or very large state spaces, consider upgrading to
    the ``DeepTradeExecutionRL`` DQN variant.

    Parameters
    ----------
    n_bins_per_dim : int
        Number of discrete bins per state dimension.  Higher = finer
        granularity but larger Q-table.
    n_actions : int
        Number of actions (default 3: HOLD, ENTER, EXIT).
    learning_rate : float
        Alpha — Q-value update step size (0, 1].
    discount_factor : float
        Gamma — future reward discount (0, 1].
    epsilon : float
        Initial exploration rate for epsilon-greedy.
    epsilon_decay : float
        Multiplicative decay per episode.
    epsilon_min : float
        Floor for epsilon after decay.
    reward_scaling : float
        Multiplier applied to raw P&L for reward shaping.
    transaction_cost : float
        Cost per trade as a fraction of position value (e.g., 0.001 = 0.1%).

    Example
    -------
    .. code-block:: python

        from training.reinforcement import TradeExecutionRL, TradeState

        agent = TradeExecutionRL(n_bins_per_dim=8)
        agent.train(historical_df, episodes=2000)

        # Use the trained policy
        state = TradeState(rsi=-0.4, macd=0.1, ..., trend_direction=1, ...)
        action = agent.choose_action(state)  # 0=HOLD, 1=ENTER, 2=EXIT
    """

    # Reward shaping constants
    _WIN_REWARD: float = 1.0
    _LOSS_PENALTY: float = -1.5
    _HOLD_PENALTY: float = -0.01  # Small time-decay penalty
    _TRADE_COST: float = -0.05  # Per-transaction penalty

    def __init__(
        self,
        n_bins_per_dim: int = 8,
        n_actions: int = 3,
        learning_rate: float = 0.1,
        discount_factor: float = 0.95,
        epsilon: float = 1.0,
        epsilon_decay: float = 0.995,
        epsilon_min: float = 0.05,
        reward_scaling: float = 100.0,
        transaction_cost: float = 0.001,
    ) -> None:
        self.n_bins: int = n_bins_per_dim
        self.n_actions: int = n_actions
        self.lr: float = learning_rate
        self.gamma: float = discount_factor
        self.epsilon: float = epsilon
        self.epsilon_decay: float = epsilon_decay
        self.epsilon_min: float = epsilon_min
        self.reward_scaling: float = reward_scaling
        self.transaction_cost: float = transaction_cost

        # Q-table: nested dict {state_index: {action: q_value}}
        self.q_table: Dict[int, Dict[int, float]] = {}

        # State binning: track min/max seen for each dimension
        self._state_mins: Optional[np.ndarray] = None
        self._state_maxs: Optional[np.ndarray] = None
        self._state_initialized: bool = False

        # Training history
        self._episode_results: List[EpisodeResult] = []
        self._total_steps: int = 0

        # Position tracking during simulation
        self._in_position: bool = False
        self._entry_price: float = 0.0
        self._position_size: float = 1.0  # Normalised

        logger.info(
            f"TradeExecutionRL initialised — bins={n_bins_per_dim}, "
            f"actions={n_actions}, lr={learning_rate}, gamma={discount_factor}, "
            f"epsilon={epsilon}"
        )

    # ------------------------------------------------------------------
    # State discretisation
    # ------------------------------------------------------------------

    def _init_state_bounds(self, historical_data: pd.DataFrame) -> None:
        """
        Compute min/max for each state dimension from historical data.

        These bounds are used to bin continuous state values into
        discrete indices for the Q-table.
        """
        states = self._extract_states(historical_data)
        state_arrays = np.stack([s.to_array() for s in states])

        self._state_mins = state_arrays.min(axis=0)
        self._state_maxs = state_arrays.max(axis=0)
        # Add small buffer to avoid edge cases
        buffer = (self._state_maxs - self._state_mins) * 0.05
        self._state_mins -= buffer
        self._state_maxs += buffer
        self._state_initialized = True

        logger.info(
            f"State bounds initialised — table size potential: "
            f"{self.n_bins ** len(TradeState.__dataclass_fields__)} entries"
        )

    def state_to_index(self, state: TradeState) -> int:
        """
        Convert a continuous ``TradeState`` to a discrete Q-table index.

        Uses uniform binning across each dimension.  The index is computed
        as a mixed-radix number to ensure a unique integer for each
        bin combination.

        Parameters
        ----------
        state:
            The continuous state to discretise.

        Returns
        -------
        int
            Discrete state index for Q-table lookup.
        """
        arr = state.to_array()
        n_dims = len(arr)

        if (
            not self._state_initialized
            or self._state_mins is None
            or self._state_maxs is None
        ):
            # Default bounds before data-driven initialisation
            mins = np.full(n_dims, -1.0, dtype=np.float32)
            maxs = np.full(n_dims, 1.0, dtype=np.float32)
        else:
            mins = self._state_mins
            maxs = self._state_maxs

        # Clip and bin each dimension
        clipped = np.clip(arr, mins, maxs)
        # Normalise to [0, 1] then bin
        normalised = (clipped - mins) / (maxs - mins + 1e-10)
        bins = np.floor(normalised * self.n_bins).astype(int)
        bins = np.clip(bins, 0, self.n_bins - 1)

        # Mixed-radix encoding: unique index for each bin combination
        index = 0
        for dim_idx, bin_val in enumerate(bins):
            index += bin_val * (self.n_bins**dim_idx)

        return int(index)

    def _get_q_row(self, state_index: int) -> Dict[int, float]:
        """Get (or create) the Q-value row for a state index."""
        if state_index not in self.q_table:
            self.q_table[state_index] = {a: 0.0 for a in range(self.n_actions)}
        return self.q_table[state_index]

    # ------------------------------------------------------------------
    # Action selection
    # ------------------------------------------------------------------

    def choose_action(self, state: TradeState, training: bool = True) -> int:
        """
        Select an action using epsilon-greedy policy.

        Parameters
        ----------
        state:
            Current market state.
        training:
            If ``True``, uses epsilon-greedy with exploration.
            If ``False``, always selects the best action (greedy).

        Returns
        -------
        int
            Selected action (0=HOLD, 1=ENTER, 2=EXIT).
        """
        state_idx = self.state_to_index(state)
        q_row = self._get_q_row(state_idx)

        if training and np.random.random() < self.epsilon:
            # Exploration: random action
            return int(np.random.randint(0, self.n_actions))

        # Exploitation: best known action
        best_action = max(q_row, key=q_row.get, default=Action.HOLD)
        return best_action

    def get_action_probs(
        self, state: TradeState, temperature: float = 1.0
    ) -> Dict[int, float]:
        """
        Get action probabilities using Boltzmann (softmax) exploration.

        This is useful for stochastic policy evaluation and for generating
        softer action distributions than pure argmax.

        Parameters
        ----------
        state:
            Current market state.
        temperature:
            Higher = more uniform distribution (more exploration).
            Lower = more peaked around the best action.

        Returns
        -------
        Dict[int, float]
            Action → probability mapping.
        """
        state_idx = self.state_to_index(state)
        q_row = self._get_q_row(state_idx)
        q_values = np.array([q_row[a] for a in range(self.n_actions)], dtype=np.float64)

        # Boltzmann distribution
        scaled = q_values / max(temperature, 1e-6)
        # Numerical stability: subtract max
        exp_vals = np.exp(scaled - np.max(scaled))
        probs = exp_vals / (np.sum(exp_vals) + 1e-10)

        return {a: float(probs[a]) for a in range(self.n_actions)}

    # ------------------------------------------------------------------
    # Q-learning update
    # ------------------------------------------------------------------

    def update(
        self,
        state: TradeState,
        action: int,
        reward: float,
        next_state: TradeState,
        done: bool = False,
    ) -> None:
        """
        Perform a single Q-table update.

        Uses the standard Q-learning update rule:

        .. math::

            Q(s,a) += alpha * [r + gamma * max(Q(s',a')) - Q(s,a)]

        Parameters
        ----------
        state:
            Current state (before action).
        action:
            Action taken.
        reward:
            Reward received.
        next_state:
            Resulting state after action.
        done:
            Whether the episode has terminated.
        """
        state_idx = self.state_to_index(state)
        next_idx = self.state_to_index(next_state)

        q_row = self._get_q_row(state_idx)
        current_q = q_row.get(action, 0.0)

        # Terminal state has no future value
        if done:
            target = reward
        else:
            next_q_row = self._get_q_row(next_idx)
            best_next_q = max(next_q_row.values()) if next_q_row else 0.0
            target = reward + self.gamma * best_next_q

        # Update
        q_row[action] = current_q + self.lr * (target - current_q)
        self._total_steps += 1

    # ------------------------------------------------------------------
    # Training loop
    # ------------------------------------------------------------------

    def train(
        self,
        historical_data: pd.DataFrame,
        episodes: int = 1000,
        print_every: int = 100,
        early_stop_patience: int = 50,
        early_stop_min_improvement: float = 0.01,
    ) -> List[EpisodeResult]:
        """
        Train the Q-Learning agent on historical price data.

        The agent simulates trading decisions episode by episode,
        learning from realised P&L (reward signal).

        Parameters
        ----------
        historical_data:
            OHLCV DataFrame with indicator columns (from MarketDatasetBuilder).
        episodes:
            Number of training episodes.
        print_every:
            Log progress every N episodes.
        early_stop_patience:
            Stop if average reward does not improve for this many episodes.
        early_stop_min_improvement:
            Minimum relative improvement to reset patience counter.

        Returns
        -------
        List[EpisodeResult]
            Summary statistics for each episode.
        """
        logger.info(f"Starting training — {episodes} episodes ...")

        # Initialise state bounds from data
        if not self._state_initialized:
            self._init_state_bounds(historical_data)

        states = self._extract_states(historical_data)
        prices = (
            historical_data["close"].values
            if "close" in historical_data.columns
            else historical_data["Close"].values
        )

        best_avg_reward = float("-inf")
        patience_counter = 0
        results: List[EpisodeResult] = []

        for episode in range(1, episodes + 1):
            episode_reward, n_trades, n_wins, n_losses = self._run_episode(
                states, prices
            )

            # Decay epsilon
            self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)

            # Record
            win_rate = n_wins / max(n_trades, 1)
            result = EpisodeResult(
                episode=episode,
                total_reward=episode_reward,
                n_trades=n_trades,
                n_wins=n_wins,
                n_losses=n_losses,
                win_rate=win_rate,
                final_q_table_size=len(self.q_table),
                epsilon=self.epsilon,
            )
            results.append(result)

            # Logging
            if episode % print_every == 0 or episode == 1:
                recent_rewards = [r.total_reward for r in results[-print_every:]]
                avg_reward = sum(recent_rewards) / len(recent_rewards)
                logger.info(
                    f"Episode {episode}/{episodes} — "
                    f"reward={episode_reward:.3f}, "
                    f"avg_reward={avg_reward:.3f}, "
                    f"trades={n_trades}, "
                    f"win_rate={win_rate:.1%}, "
                    f"epsilon={self.epsilon:.3f}, "
                    f"q_table_size={len(self.q_table)}"
                )

            # Early stopping
            if episode > early_stop_patience:
                recent_avg = (
                    sum(r.total_reward for r in results[-early_stop_patience:])
                    / early_stop_patience
                )
                if recent_avg > best_avg_reward * (1 + early_stop_min_improvement):
                    best_avg_reward = recent_avg
                    patience_counter = 0
                else:
                    patience_counter += 1
                    if patience_counter >= early_stop_patience:
                        logger.info(
                            f"Early stopping at episode {episode} — "
                            f"no improvement for {early_stop_patience} episodes."
                        )
                        break

        self._episode_results = results
        logger.info(
            f"Training complete — {len(results)} episodes, "
            f"final Q-table size: {len(self.q_table)}, "
            f"final epsilon: {self.epsilon:.4f}"
        )
        return results

    def _run_episode(
        self,
        states: List[TradeState],
        prices: np.ndarray,
    ) -> Tuple[float, int, int, int]:
        """
        Run a single training episode (one pass through the data).

        Returns
        -------
        Tuple[float, int, int, int]
            (total_reward, n_trades, n_wins, n_losses)
        """
        total_reward = 0.0
        n_trades = 0
        n_wins = 0
        n_losses = 0
        in_position = False
        entry_price = 0.0

        for t in range(len(states) - 1):
            state = states[t]
            current_price = prices[t]

            action = self.choose_action(state, training=True)
            reward = 0.0

            if action == Action.ENTER and not in_position:
                in_position = True
                entry_price = current_price
                n_trades += 1
                reward = self._TRADE_COST  # Transaction cost

            elif action == Action.EXIT and in_position:
                pnl_pct = (current_price - entry_price) / entry_price
                raw_reward = pnl_pct * self.reward_scaling
                reward = raw_reward + self._TRADE_COST

                if pnl_pct > 0:
                    n_wins += 1
                    reward += self._WIN_REWARD
                else:
                    n_losses += 1
                    reward += self._LOSS_PENALTY

                in_position = False
                entry_price = 0.0

            elif action == Action.HOLD and in_position:
                # Small time-decay penalty for holding too long
                reward = self._HOLD_PENALTY

            elif action == Action.HOLD and not in_position:
                # Small penalty for not entering when opportunity exists
                reward = self._HOLD_PENALTY * 0.5

            total_reward += reward

            # Q-table update
            next_state = states[t + 1]
            done = t == len(states) - 2
            self.update(state, action, reward, next_state, done=done)

        # Force close any open position at end of episode
        if in_position:
            pnl_pct = (prices[-1] - entry_price) / entry_price
            reward = pnl_pct * self.reward_scaling + self._TRADE_COST
            if pnl_pct > 0:
                n_wins += 1
            else:
                n_losses += 1
            total_reward += reward

        return total_reward, n_trades, n_wins, n_losses

    # ------------------------------------------------------------------
    # State extraction from DataFrame
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_states(df: pd.DataFrame) -> List[TradeState]:
        """
        Extract a list of ``TradeState`` objects from an OHLCV DataFrame.

        Expects the DataFrame to have indicator columns as produced by
        ``MarketDatasetBuilder.create_indicator_dataset()``.

        Parameters
        ----------
        df:
            DataFrame with OHLCV + indicator columns.

        Returns
        -------
        List[TradeState]
            One state per row (after sufficient history for indicators).
        """
        df = df.copy()
        df.columns = [c.lower() for c in df.columns]

        states: List[TradeState] = []
        for idx in range(len(df)):
            row = df.iloc[idx]

            # RSI: normalise from [0, 100] to [-1, 1]
            rsi_raw = row.get("rsi_14", 50.0)
            rsi_norm = (rsi_raw - 50.0) / 50.0

            # MACD histogram: clip and normalise roughly to [-1, 1]
            macd_raw = row.get("macd_histogram", 0.0)
            macd_norm = np.clip(macd_raw / 5.0, -1.0, 1.0)  # assume ~5 is large

            # Price vs SMA20 and SMA50 as percentage deviations
            price_vs_sma20 = (
                row.get("price_vs_sma20", 0.0) / 10.0
            )  # normalise ~10% to 1.0
            price_vs_sma50 = row.get("price_vs_sma50", 0.0) / 10.0

            # Volume ratio: log-normalise
            vol_ratio = row.get("volume_ratio", 1.0)
            vol_norm = np.clip(np.log(vol_ratio) / 2.0, -1.0, 1.0)

            # Trend direction
            sma20 = row.get("sma_20", row.get("close", 0))
            sma50 = row.get("sma_50", row.get("close", 0))
            close = row.get("close", 0)
            if close > sma20 and close > sma50:
                trend = 1
            elif close < sma20 and close < sma50:
                trend = -1
            else:
                trend = 0

            # Time features (if timestamp available)
            time_of_day = 0.5  # default: mid-session
            day_of_week = 2  # default: Wednesday
            if hasattr(df.index, "hour") and hasattr(df.index, "dayofweek"):
                try:
                    ts = df.index[idx]
                    if hasattr(ts, "hour"):
                        # Indian market hours: 9:15 - 15:30 = 6.25 hours
                        market_minutes = (ts.hour - 9) * 60 + (ts.minute - 15)
                        time_of_day = np.clip(market_minutes / (6.25 * 60), 0.0, 1.0)
                    if hasattr(ts, "dayofweek"):
                        day_of_week = int(ts.dayofweek)
                except Exception:
                    pass

            states.append(
                TradeState(
                    rsi=float(np.clip(rsi_norm, -1.0, 1.0)),
                    macd=float(np.clip(macd_norm, -1.0, 1.0)),
                    price_vs_sma20=float(np.clip(price_vs_sma20, -1.0, 1.0)),
                    price_vs_sma50=float(np.clip(price_vs_sma50, -1.0, 1.0)),
                    volume_ratio=float(np.clip(vol_norm, -1.0, 1.0)),
                    trend_direction=trend,
                    time_of_day=float(time_of_day),
                    day_of_week=day_of_week,
                )
            )

        return states

    # ------------------------------------------------------------------
    # Policy evaluation
    # ------------------------------------------------------------------

    def evaluate_policy(
        self,
        historical_data: pd.DataFrame,
    ) -> Dict[str, Any]:
        """
        Evaluate the trained policy on out-of-sample data (greedy, no exploration).

        Parameters
        ----------
        historical_data:
            OHLCV DataFrame with indicator columns.

        Returns
        -------
        Dict[str, Any]
            Evaluation metrics: total_return, sharpe, max_drawdown, win_rate, etc.
        """
        states = self._extract_states(historical_data)
        prices = (
            historical_data["close"].values
            if "close" in historical_data.columns
            else historical_data["Close"].values
        )

        returns: List[float] = []
        trades: List[Dict[str, Any]] = []
        in_position = False
        entry_price = 0.0
        entry_idx = 0
        equity = 1.0  # Normalised starting equity
        equity_curve = [equity]

        for t in range(len(states) - 1):
            state = states[t]
            action = self.choose_action(state, training=False)
            current_price = prices[t]

            if action == Action.ENTER and not in_position:
                in_position = True
                entry_price = current_price
                entry_idx = t

            elif action == Action.EXIT and in_position:
                pnl_pct = (current_price - entry_price) / entry_price
                trade_return = pnl_pct - 2 * self.transaction_cost  # entry + exit cost
                returns.append(trade_return)
                equity *= 1 + trade_return
                trades.append(
                    {
                        "entry_idx": entry_idx,
                        "exit_idx": t,
                        "entry_price": entry_price,
                        "exit_price": current_price,
                        "return_pct": trade_return * 100,
                    }
                )
                in_position = False

            equity_curve.append(equity)

        # Force close
        if in_position:
            pnl_pct = (prices[-1] - entry_price) / entry_price
            trade_return = pnl_pct - 2 * self.transaction_cost
            returns.append(trade_return)
            equity *= 1 + trade_return
            trades.append(
                {
                    "entry_idx": entry_idx,
                    "exit_idx": len(states) - 1,
                    "entry_price": entry_price,
                    "exit_price": prices[-1],
                    "return_pct": trade_return * 100,
                }
            )

        equity_arr = np.array(equity_curve)

        # Compute metrics
        total_return = (equity - 1.0) * 100
        win_rate = sum(1 for r in returns if r > 0) / max(len(returns), 1) * 100
        avg_return = np.mean(returns) * 100 if returns else 0
        max_dd = self._max_drawdown(equity_arr) * 100

        # Sharpe (daily, assuming each step is a day)
        if len(returns) > 1:
            returns_arr = np.array(returns)
            sharpe = (np.mean(returns_arr) / (np.std(returns_arr) + 1e-10)) * np.sqrt(
                252
            )
        else:
            sharpe = 0.0

        results = {
            "total_return_pct": round(total_return, 2),
            "n_trades": len(trades),
            "win_rate_pct": round(win_rate, 1),
            "avg_trade_return_pct": round(avg_return, 4),
            "max_drawdown_pct": round(max_dd, 2),
            "sharpe_ratio": round(sharpe, 2),
            "final_equity": round(equity, 4),
            "trades": trades,
        }

        logger.info(
            f"Policy evaluation — return={results['total_return_pct']:.2f}%, "
            f"trades={results['n_trades']}, win_rate={results['win_rate_pct']:.1f}%, "
            f"sharpe={results['sharpe_ratio']:.2f}, max_dd={results['max_drawdown_pct']:.2f}%"
        )
        return results

    @staticmethod
    def _max_drawdown(equity_curve: np.ndarray) -> float:
        """
        Compute the maximum drawdown from an equity curve.

        Max drawdown = max peak-to-trough decline as a fraction.
        """
        running_max = np.maximum.accumulate(equity_curve)
        drawdowns = (running_max - equity_curve) / running_max
        return float(np.max(drawdowns))

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: str) -> None:
        """
        Save the agent to disk (Q-table + hyperparameters).

        Parameters
        ----------
        path:
            File path (``.pkl`` extension recommended).
        """
        state = {
            "q_table": self.q_table,
            "n_bins": self.n_bins,
            "n_actions": self.n_actions,
            "lr": self.lr,
            "gamma": self.gamma,
            "epsilon": self.epsilon,
            "epsilon_decay": self.epsilon_decay,
            "epsilon_min": self.epsilon_min,
            "reward_scaling": self.reward_scaling,
            "transaction_cost": self.transaction_cost,
            "state_mins": self._state_mins,
            "state_maxs": self._state_maxs,
            "state_initialized": self._state_initialized,
            "episode_results": self._episode_results,
            "total_steps": self._total_steps,
        }

        os.makedirs(
            os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True
        )
        with open(path, "wb") as fh:
            pickle.dump(state, fh)

        logger.info(f"Agent saved to {path} — Q-table: {len(self.q_table)} entries")

    def load(self, path: str) -> None:
        """
        Load the agent from disk.

        Parameters
        ----------
        path:
            File path previously saved via ``save()``.
        """
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Agent file not found: {path}")

        with open(path, "rb") as fh:
            state = pickle.load(fh)

        self.q_table = state["q_table"]
        self.n_bins = state["n_bins"]
        self.n_actions = state["n_actions"]
        self.lr = state["lr"]
        self.gamma = state["gamma"]
        self.epsilon = state["epsilon"]
        self.epsilon_decay = state["epsilon_decay"]
        self.epsilon_min = state["epsilon_min"]
        self.reward_scaling = state["reward_scaling"]
        self.transaction_cost = state["transaction_cost"]
        self._state_mins = state["state_mins"]
        self._state_maxs = state["state_maxs"]
        self._state_initialized = state["state_initialized"]
        self._episode_results = state.get("episode_results", [])
        self._total_steps = state.get("total_steps", 0)

        logger.info(
            f"Agent loaded from {path} — Q-table: {len(self.q_table)} entries, "
            f"epsilon={self.epsilon:.4f}"
        )

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def get_top_states(self, action: int, n: int = 10) -> List[Tuple[int, float]]:
        """
        Get the states with the highest Q-value for a given action.

        Useful for debugging: shows which market states the agent
        associates most strongly with a particular action.

        Parameters
        ----------
        action:
            Action to inspect (0=HOLD, 1=ENTER, 2=EXIT).
        n:
            Number of top states to return.

        Returns
        -------
        List[Tuple[int, float]]
            (state_index, q_value) tuples sorted descending.
        """
        scored = [
            (state_idx, q_row.get(action, -float("inf")))
            for state_idx, q_row in self.q_table.items()
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:n]

    def get_q_table_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the Q-table.

        Returns
        -------
        Dict[str, Any]
            Size, coverage, and value distribution statistics.
        """
        if not self.q_table:
            return {"size": 0, "coverage_pct": 0.0}

        all_values = []
        for q_row in self.q_table.values():
            all_values.extend(q_row.values())

        arr = np.array(all_values)
        total_possible = self.n_bins**8 * self.n_actions  # 8 state dims

        return {
            "size": len(self.q_table),
            "total_entries": len(all_values),
            "coverage_pct": round(len(self.q_table) / total_possible * 100, 6),
            "q_value_mean": round(float(np.mean(arr)), 4),
            "q_value_std": round(float(np.std(arr)), 4),
            "q_value_min": round(float(np.min(arr)), 4),
            "q_value_max": round(float(np.max(arr)), 4),
            "n_episodes_trained": len(self._episode_results),
            "total_steps": self._total_steps,
            "current_epsilon": round(self.epsilon, 4),
        }

    def export_policy_json(self, path: str, top_n: int = 1000) -> None:
        """
        Export the learned policy to JSON for inspection.

        Only exports the top-N states by Q-value magnitude to keep
        the file manageable.

        Parameters
        ----------
        path:
            Output JSON file path.
        top_n:
            Maximum number of states to export.
        """
        # Score each state by max Q-value
        state_scores = [
            (state_idx, max(q_row.values()))
            for state_idx, q_row in self.q_table.items()
        ]
        state_scores.sort(key=lambda x: x[1], reverse=True)

        policy: Dict[str, Any] = {
            "metadata": {
                "n_bins": self.n_bins,
                "n_actions": self.n_actions,
                "epsilon": self.epsilon,
                "exported_at": datetime.now().isoformat(),
            },
            "policy": [],
        }

        for state_idx, score in state_scores[:top_n]:
            q_row = self.q_table[state_idx]
            best_action = int(max(q_row, key=q_row.get))
            policy["policy"].append(
                {
                    "state_index": state_idx,
                    "best_action": best_action,
                    "action_names": {0: "HOLD", 1: "ENTER", 2: "EXIT"},
                    "q_values": {str(k): round(v, 4) for k, v in q_row.items()},
                    "max_q": round(score, 4),
                }
            )

        with open(path, "w", encoding="utf-8") as fh:
            json.dump(policy, fh, indent=2)

        logger.info(f"Policy exported to {path} — {len(policy['policy'])} states")


# =============================================================================
# Deep Q-Network variant (optional upgrade path)
# =============================================================================


class DeepTradeExecutionRL:
    """
    Deep Q-Network (DQN) agent for trade execution.

    This is an *optional upgrade* from the tabular Q-Learning agent.
    It uses a small neural network to approximate Q(s, a) instead of
    a lookup table, enabling it to handle larger / continuous state
    spaces and generalise to unseen states.

    Architecture:
    - Input: 8-dim state vector (TradeState.to_array())
    - Hidden: 2 layers × 64 neurons (ReLU)
    - Output: 3 Q-values (one per action)

    Training uses:
    - Experience replay buffer
    - Target network (soft updates)
    - Adam optimiser with MSE loss

    Parameters
    ----------
    state_dim : int
        Dimensionality of the state vector (default 8 for TradeState).
    n_actions : int
        Number of actions (default 3).
    learning_rate : float
        Optimiser learning rate.
    gamma : float
        Discount factor.
    epsilon : float
        Initial exploration rate.
    epsilon_decay : float
        Decay per step.
    epsilon_min : float
        Floor for epsilon.
    buffer_size : int
        Experience replay buffer capacity.
    batch_size : int
        Mini-batch size for training.
    target_update_freq : int
        Update target network every N steps.
    hidden_dims : List[int]
        Hidden layer dimensions.

    Example
    -------
    .. code-block:: python

        agent = DeepTradeExecutionRL()
        agent.train(historical_df, episodes=1000)
    """

    def __init__(
        self,
        state_dim: int = 8,
        n_actions: int = 3,
        learning_rate: float = 1e-3,
        gamma: float = 0.99,
        epsilon: float = 1.0,
        epsilon_decay: float = 0.9995,
        epsilon_min: float = 0.05,
        buffer_size: int = 10000,
        batch_size: int = 64,
        target_update_freq: int = 100,
        hidden_dims: Optional[List[int]] = None,
    ) -> None:
        self.state_dim = state_dim
        self.n_actions = n_actions
        self.lr = learning_rate
        self.gamma = gamma
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        self.epsilon_min = epsilon_min
        self.batch_size = batch_size
        self.target_update_freq = target_update_freq

        self.hidden_dims = hidden_dims or [64, 64]
        self._step_count: int = 0

        # Try to import PyTorch — if unavailable, log a warning
        try:
            import torch
            import torch.nn as nn
            import torch.optim as optim

            self._torch = torch
            self._nn = nn
            self._optim = optim
            self._has_torch = True
        except ImportError:
            logger.warning(
                "PyTorch not available — DeepTradeExecutionRL will not function."
            )
            self._has_torch = False
            return

        # Networks
        self.q_network = self._build_network()
        self.target_network = self._build_network()
        self.target_network.load_state_dict(self.q_network.state_dict())
        self.target_network.eval()

        self.optimizer = self._optim.Adam(self.q_network.parameters(), lr=self.lr)

        # Replay buffer
        self._replay_buffer: List[Tuple[np.ndarray, int, float, np.ndarray, bool]] = []
        self._buffer_capacity = buffer_size

        logger.info(
            f"DeepTradeExecutionRL initialised — state_dim={state_dim}, "
            f"hidden={self.hidden_dims}, buffer={buffer_size}"
        )

    def _build_network(self) -> Any:
        """Build a simple feed-forward Q-network."""
        if not self._has_torch:
            raise RuntimeError("PyTorch not available.")

        layers: List[Any] = []
        in_dim = self.state_dim
        for h_dim in self.hidden_dims:
            layers.append(self._nn.Linear(in_dim, h_dim))
            layers.append(self._nn.ReLU())
            in_dim = h_dim
        layers.append(self._nn.Linear(in_dim, self.n_actions))

        return self._nn.Sequential(*layers)

    def choose_action(
        self, state: Union[TradeState, np.ndarray], training: bool = True
    ) -> int:
        """
        Select an action using epsilon-greedy policy.

        Parameters
        ----------
        state:
            Current state (TradeState or raw array).
        training:
            If ``True``, uses epsilon-greedy with exploration.

        Returns
        -------
        int
            Selected action.
        """
        if not self._has_torch:
            return Action.HOLD

        if isinstance(state, TradeState):
            state_arr = state.to_array()
        else:
            state_arr = state

        if training and np.random.random() < self.epsilon:
            return int(np.random.randint(0, self.n_actions))

        with self._torch.no_grad():
            state_t = self._torch.FloatTensor(state_arr).unsqueeze(0)
            q_values = self.q_network(state_t)
            return int(q_values.argmax(dim=1).item())

    def store_transition(
        self,
        state: np.ndarray,
        action: int,
        reward: float,
        next_state: np.ndarray,
        done: bool,
    ) -> None:
        """Store a transition in the replay buffer."""
        if len(self._replay_buffer) >= self._buffer_capacity:
            self._replay_buffer.pop(0)
        self._replay_buffer.append((state, action, reward, next_state, done))

    def train_step(self) -> Optional[float]:
        """
        Perform one training step using experience replay.

        Returns
        -------
        float or None
            Loss value, or None if buffer has insufficient samples.
        """
        if not self._has_torch or len(self._replay_buffer) < self.batch_size:
            return None

        # Sample batch
        batch = random.sample(self._replay_buffer, self.batch_size)
        states, actions, rewards, next_states, dones = zip(*batch)

        states_t = self._torch.FloatTensor(np.array(states))
        actions_t = self._torch.LongTensor(actions)
        rewards_t = self._torch.FloatTensor(rewards)
        next_states_t = self._torch.FloatTensor(np.array(next_states))
        dones_t = self._torch.FloatTensor(dones)

        # Current Q values
        current_q = (
            self.q_network(states_t).gather(1, actions_t.unsqueeze(1)).squeeze(1)
        )

        # Target Q values (Double DQN: use online net for action selection)
        with self._torch.no_grad():
            next_actions = self.q_network(next_states_t).argmax(dim=1)
            next_q = (
                self.target_network(next_states_t)
                .gather(1, next_actions.unsqueeze(1))
                .squeeze(1)
            )
            target_q = rewards_t + self.gamma * next_q * (1 - dones_t)

        # Loss + update
        loss = self._nn.MSELoss()(current_q, target_q)
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()

        # Update target network
        self._step_count += 1
        if self._step_count % self.target_update_freq == 0:
            self.target_network.load_state_dict(self.q_network.state_dict())

        # Decay epsilon
        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)

        return float(loss.item())

    def train(
        self,
        historical_data: pd.DataFrame,
        episodes: int = 1000,
        print_every: int = 100,
    ) -> List[EpisodeResult]:
        """
        Train the DQN agent on historical data.

        Parameters
        ----------
        historical_data:
            OHLCV DataFrame with indicator columns.
        episodes:
            Number of training episodes.
        print_every:
            Log progress every N episodes.

        Returns
        -------
        List[EpisodeResult]
            Episode summaries.
        """
        if not self._has_torch:
            raise RuntimeError("PyTorch is required for DQN training.")

        states = TradeExecutionRL._extract_states(historical_data)
        state_arrays = [s.to_array() for s in states]
        prices = (
            historical_data["close"].values
            if "close" in historical_data.columns
            else historical_data["Close"].values
        )

        results: List[EpisodeResult] = []

        for episode in range(1, episodes + 1):
            total_reward = 0.0
            n_trades = 0
            n_wins = 0
            n_losses = 0
            in_position = False
            entry_price = 0.0

            for t in range(len(states) - 1):
                state_arr = state_arrays[t]
                action = self.choose_action(state_arr, training=True)
                current_price = prices[t]

                reward = 0.0
                if action == Action.ENTER and not in_position:
                    in_position = True
                    entry_price = current_price
                    n_trades += 1
                    reward = -0.05  # Transaction cost
                elif action == Action.EXIT and in_position:
                    pnl_pct = (current_price - entry_price) / entry_price
                    reward = pnl_pct * 100 - 0.05
                    if pnl_pct > 0:
                        n_wins += 1
                        reward += 1.0
                    else:
                        n_losses += 1
                        reward -= 1.5
                    in_position = False
                elif action == Action.HOLD and in_position:
                    reward = -0.01

                total_reward += reward

                # Store transition and train
                next_arr = state_arrays[t + 1]
                done = t == len(states) - 2
                self.store_transition(state_arr, action, reward, next_arr, done)
                self.train_step()

            # Force close
            if in_position:
                pnl_pct = (prices[-1] - entry_price) / entry_price
                total_reward += pnl_pct * 100

            win_rate = n_wins / max(n_trades, 1)
            results.append(
                EpisodeResult(
                    episode=episode,
                    total_reward=total_reward,
                    n_trades=n_trades,
                    n_wins=n_wins,
                    n_losses=n_losses,
                    win_rate=win_rate,
                    final_q_table_size=len(self._replay_buffer),
                    epsilon=self.epsilon,
                )
            )

            if episode % print_every == 0:
                recent = [r.total_reward for r in results[-print_every:]]
                logger.info(
                    f"DQN Episode {episode}/{episodes} — "
                    f"reward={total_reward:.2f}, "
                    f"avg={sum(recent)/len(recent):.2f}, "
                    f"epsilon={self.epsilon:.3f}, "
                    f"buffer={len(self._replay_buffer)}"
                )

        return results

    def save(self, path: str) -> None:
        """Save the DQN network weights."""
        if not self._has_torch:
            raise RuntimeError("PyTorch not available.")
        self._torch.save(
            {
                "q_network": self.q_network.state_dict(),
                "target_network": self.target_network.state_dict(),
                "optimizer": self.optimizer.state_dict(),
                "epsilon": self.epsilon,
                "step_count": self._step_count,
            },
            path,
        )
        logger.info(f"DQN model saved to {path}")

    def load(self, path: str) -> None:
        """Load the DQN network weights."""
        if not self._has_torch:
            raise RuntimeError("PyTorch not available.")
        checkpoint = self._torch.load(path, map_location="cpu")
        self.q_network.load_state_dict(checkpoint["q_network"])
        self.target_network.load_state_dict(checkpoint["target_network"])
        self.optimizer.load_state_dict(checkpoint["optimizer"])
        self.epsilon = checkpoint["epsilon"]
        self._step_count = checkpoint["step_count"]
        logger.info(f"DQN model loaded from {path}")


# =============================================================================
# Convenience functions
# =============================================================================


def create_agent_for_market(
    market_type: str = "equity",
    use_dqn: bool = False,
) -> Union[TradeExecutionRL, DeepTradeExecutionRL]:
    """
    Factory function that creates a pre-configured RL agent.

    Parameters
    ----------
    market_type:
        ``"equity"``, ``"forex"``, ``"crypto"``, or ``"options"``.
    use_dqn:
        If ``True``, returns a ``DeepTradeExecutionRL`` instead of
        the tabular Q-Learning agent.

    Returns
    -------
    TradeExecutionRL or DeepTradeExecutionRL
        Configured agent.
    """
    configs = {
        "equity": {"n_bins_per_dim": 8, "epsilon_decay": 0.995, "lr": 0.1},
        "forex": {"n_bins_per_dim": 10, "epsilon_decay": 0.998, "lr": 0.05},
        "crypto": {"n_bins_per_dim": 12, "epsilon_decay": 0.999, "lr": 0.08},
        "options": {"n_bins_per_dim": 8, "epsilon_decay": 0.995, "lr": 0.1},
    }

    config = configs.get(market_type, configs["equity"])
    logger.info(f"Creating {market_type} agent — config: {config}")

    if use_dqn:
        return DeepTradeExecutionRL(
            learning_rate=1e-3,
            gamma=0.99,
            epsilon_decay=0.9995,
        )

    return TradeExecutionRL(**config)


def train_and_evaluate(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    episodes: int = 1000,
    use_dqn: bool = False,
) -> Dict[str, Any]:
    """
    End-to-end convenience function: train on one dataset, evaluate on another.

    Parameters
    ----------
    train_df:
        Training data (OHLCV + indicators).
    test_df:
        Out-of-sample test data.
    episodes:
        Number of training episodes.
    use_dqn:
        Use DQN instead of tabular Q-Learning.

    Returns
    -------
    Dict[str, Any]
        Training results + evaluation metrics.
    """
    agent = create_agent_for_market(use_dqn=use_dqn)

    # Train
    if use_dqn:
        episode_results = agent.train(train_df, episodes=episodes)
    else:
        episode_results = agent.train(train_df, episodes=episodes)

    # Evaluate
    eval_results = agent.evaluate_policy(test_df)

    return {
        "agent_type": "DQN" if use_dqn else "Q-Learning",
        "n_episodes": episodes,
        "training_results": episode_results,
        "evaluation": eval_results,
        "agent": agent,
    }
