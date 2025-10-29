"""Orchestrazione dell'ingest per FAIR-III."""

from .alpha import AlphaFetcher
from .alphavantage import AlphaVantageFXFetcher
from .aqr import AQRFetcher
from .binance import BinanceFetcher
from .bis import BISFetcher
from .boe import BOEFetcher
from .cboe import CBOEFetcher
from .coingecko import CoinGeckoFetcher
from .curvo import CurvoFetcher
from .ecb import ECBFetcher
from .eodhd import EODHDFetcher
from .fred import FREDFetcher
from .french import FrenchFetcher
from .lbma import LBMAFetcher
from .nareit import NareitFetcher
from .oecd import OECDFetcher
from .portfolio_visualizer import PortfolioVisualizerFetcher
from .portfoliocharts import PortfolioChartsFetcher
from .registry import (
    BaseCSVFetcher,
    IngestArtifact,
    available_sources,
    create_fetcher,
    run_ingest,
)
from .stooq import StooqFetcher
from .testfolio import TestfolioPresetFetcher
from .tiingo import TiingoFetcher
from .us_market_data import USMarketDataFetcher
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
    "CurvoFetcher",
    "ECBFetcher",
    "EODHDFetcher",
    "FREDFetcher",
    "FrenchFetcher",
    "LBMAFetcher",
    "NareitFetcher",
    "OECDFetcher",
    "PortfolioChartsFetcher",
    "PortfolioVisualizerFetcher",
    "StooqFetcher",
    "TestfolioPresetFetcher",
    "TiingoFetcher",
    "USMarketDataFetcher",
    "WorldBankFetcher",
    "YahooFetcher",
    "BaseCSVFetcher",
    "IngestArtifact",
    "available_sources",
    "create_fetcher",
    "run_ingest",
]
