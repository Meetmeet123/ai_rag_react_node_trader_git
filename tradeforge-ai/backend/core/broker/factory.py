"""
Broker factory — dynamically instantiates a broker connector from a persisted
:class:`BrokerConfig` document.

The factory decrypts credentials as needed and returns the appropriate concrete
broker implementation.  Unknown / unsupported brokers return a safe stub so the
execution engine never crashes on configuration mismatches.
"""

from __future__ import annotations


from loguru import logger

from core.broker.base import BaseBroker
from core.broker.paper_broker import PaperBroker
from core.broker.upstox import UpstoxBroker
from core.security import decrypt_value
from database.models import BrokerConfig, BrokerName


def create_broker_from_config(config: BrokerConfig) -> BaseBroker:
    """Create a broker connector from a persisted config.

    Args:
        config: A :class:`BrokerConfig` document.

    Returns:
        A concrete :class:`BaseBroker` implementation.

    Raises:
        NotImplementedError: For unsupported broker names that are known but
        not yet implemented (e.g. Angel One, Zerodha, Fyers).
    """
    broker_name = config.broker

    if broker_name == BrokerName.UPSTOX:
        return UpstoxBroker(
            api_key=config.api_key,
            api_secret=decrypt_value(config.api_secret),
            redirect_uri=getattr(config, "redirect_uri", None),
            access_token=decrypt_value(config.access_token),
            client_id=config.client_id,
        )

    if broker_name == BrokerName.PAPER:
        return PaperBroker()

    if broker_name in (
        BrokerName.ANGEL_ONE,
        BrokerName.ZERODHA,
        BrokerName.FYERS,
    ):
        logger.warning("Broker '{}' is not implemented yet", broker_name.value)
        raise NotImplementedError(
            f"Broker '{broker_name.value}' is not implemented yet"
        )

    logger.warning("Unknown broker '{}', falling back to paper broker", broker_name)
    return PaperBroker()


def get_default_broker() -> BaseBroker:
    """Return a default paper broker instance."""
    return PaperBroker()
