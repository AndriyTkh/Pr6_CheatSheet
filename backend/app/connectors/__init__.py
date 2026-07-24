"""External data sources (§6a). No provider key ever leaves the server (§11)."""

from app.connectors.prozorro import Identifier, LotRow, ProzorroClient

__all__ = ["Identifier", "LotRow", "ProzorroClient"]
