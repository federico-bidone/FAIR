"""Orchestrazione dell'ingest per FAIR-III."""

from .alpha import AlphaFetcher
from .alphavantage import AlphaVantageFXFetcher
from .aqr import AQRFetcher
from .binance import BinanceFetcher
from .bis import BISFetcher
from .boe import BOEFetcher
from .cboe import CBOEFetcher
from .coingecko import CoinGeckoFetcher
from .ecb import ECBFetcher
from .fred import FREDFetcher
from .french import FrenchFetcher
from .lbma import LBMAFetcher
from .nareit import NareitFetcher
from .oecd import OECDFetcher
from .portfolio_visualizer import PortfolioVisualizerFetcher
from .registry import (
    BaseCSVFetcher,
    IngestArtifact,
    available_sources,
    create_fetcher,
    run_ingest,
)
from .stooq import StooqFetcher
from .tiingo import TiingoFetcher
from .worldbank import WorldBankFetcher
from .yahoo import YahooFetcher

__all__ = [
    "AlphaFetcher",
    "AlphaVantageFXFetcher",
    "AQRFetcher",
    "BinanceFetcher",
    "BISFetcher",
    "BOEFetcher",
    "CBOEFetcher",
    "CoinGeckoFetcher",
    "ECBFetcher",
    "FREDFetcher",
    "FrenchFetcher",
    "LBMAFetcher",
    "NareitFetcher",
    "OECDFetcher",
    "PortfolioVisualizerFetcher",
    "TiingoFetcher",
    "StooqFetcher",
    "WorldBankFetcher",
    "YahooFetcher",
    "BaseCSVFetcher",
    "IngestArtifact",
    "available_sources",
    "create_fetcher",
    "run_ingest",
]
