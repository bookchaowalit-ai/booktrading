"""
Market Intelligence — unified multi-market analysis.

Covers: Crypto, Stocks (US + Thai), Prediction Markets (Polymarket), Forex, Commodities,
        Airdrops, Degen/Meme coins, Binance Alpha, Cross-exchange Arbitrage.
"""

from app.market_intel.evm_provider import (
    EVM_PROVIDER_REGISTRY_VERSION,
    EVMProviderConfigurationError,
    EVMProviderEndpoint,
    EVMProviderIngestor,
    EVMProviderRegistry,
    EVMProviderRegistryEntry,
    EVMProviderResponse,
    EVMRetryPolicy,
    environment_secret_resolver,
)
from app.market_intel.evm_provider_dry_run import (
    DRY_RUN_TOKEN_ADDRESS,
    DRY_RUN_VERSION,
    run_evm_provider_dry_run,
)
from app.market_intel.evm_security import (
    EVM_EVIDENCE_VERSION,
    SUPPORTED_EVM_CHAINS,
    build_evm_risk_evidence,
    merge_evm_observations,
    normalize_goplus_response,
    normalize_honeypot_response,
    normalize_lp_custody,
    normalize_sell_simulation,
)
from app.market_intel.models import (
    MarketOpportunity,
    MarketQuote,
    MarketSummary,
    MarketType,
    OpportunityType,
    ScannerResult,
    Severity,
)
from app.market_intel.risk_gate import RiskDecision, RiskEvidence, RiskState, evaluate_risk
from app.market_intel.scanner import MarketScanner, get_scanner
from app.market_intel.sources import (
    AirdropSource,
    BaseSource,
    BinanceAlphaSource,
    CrossExchangeArbSource,
    CryptoSource,
    DegenSource,
    EVMOnchainSource,
    MacroSource,
    PredictionSource,
    SolanaOnchainSource,
    StockSource,
    WorldSource,
)

__all__ = [  # noqa: RUF022
    # Models
    "MarketType",
    "OpportunityType",
    "Severity",
    "MarketQuote",
    "MarketOpportunity",
    "MarketSummary",
    "ScannerResult",
    # Scanner
    "MarketScanner",
    "get_scanner",
    # Meme risk gate
    "RiskDecision",
    "RiskEvidence",
    "RiskState",
    "evaluate_risk",
    # EVM evidence adapters
    "EVM_EVIDENCE_VERSION",
    "SUPPORTED_EVM_CHAINS",
    "build_evm_risk_evidence",
    "merge_evm_observations",
    "normalize_goplus_response",
    "normalize_honeypot_response",
    "normalize_lp_custody",
    "normalize_sell_simulation",
    # EVM provider boundary
    "EVM_PROVIDER_REGISTRY_VERSION",
    "EVMProviderConfigurationError",
    "EVMProviderEndpoint",
    "EVMProviderIngestor",
    "EVMProviderRegistry",
    "EVMProviderRegistryEntry",
    "EVMProviderResponse",
    "EVMRetryPolicy",
    "environment_secret_resolver",
    "DRY_RUN_TOKEN_ADDRESS",
    "DRY_RUN_VERSION",
    "run_evm_provider_dry_run",
    # Sources
    "BaseSource",
    "CryptoSource",
    "PredictionSource",
    "StockSource",
    "MacroSource",
    "AirdropSource",
    "DegenSource",
    "EVMOnchainSource",
    "SolanaOnchainSource",
    "BinanceAlphaSource",
    "CrossExchangeArbSource",
    "WorldSource",
]
