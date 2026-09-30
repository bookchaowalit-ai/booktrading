"""
Market Intelligence — unified multi-market analysis.

Covers: Crypto, Stocks (US + Thai), Prediction Markets (Polymarket), Forex, Commodities,
        Airdrops, Degen/Meme coins, Binance Alpha, Cross-exchange Arbitrage.
"""

from app.market_intel.cluster_sell_adapter import (
    SOLANA_CLUSTER_SELL_ADAPTER_VERSION,
    ClusterSellAdapter,
    ClusterSellRoute,
    build_cluster_sell_observation,
    ingest_solana_sell_events,
    route_solana_sell_event,
)
from app.market_intel.evm_cluster_sell_adapter import (
    EVM_CLUSTER_SELL_ADAPTER_VERSION,
    EVMChainScopedClusterResolver,
    EVMClusterResolverObject,
    EVMClusterSellAdapter,
    EVMClusterSellRoute,
    adapt_evm_sell_event,
    build_evm_cluster_sell_observation,
    ingest_evm_sell_events,
    route_evm_sell_event,
)
from app.market_intel.evm_event_schema import (
    EVM_EVENT_SCHEMA_VERSION,
    EVM_EVENT_VERSION,
    EVMDecoderStatus,
    EVMEvent,
    EVMEventStatusRevision,
    EVMEventType,
    EVMFinalityStatus,
    EVMReorgStatus,
    EVMSellEvent,
    validate_evm_sell_event,
)
from app.market_intel.evm_event_schema import (
    append_status_revision as append_evm_status_revision,
)
from app.market_intel.evm_event_schema import (
    build_event_id as build_evm_event_id,
)
from app.market_intel.evm_event_schema import (
    compute_event_id as compute_evm_event_id,
)
from app.market_intel.evm_event_schema import (
    deterministic_event_id as deterministic_evm_event_id,
)
from app.market_intel.evm_event_schema import (
    event_identity_material as evm_event_identity_material,
)
from app.market_intel.evm_event_schema import (
    is_monitor_eligible as is_evm_monitor_eligible,
)
from app.market_intel.evm_event_schema import (
    make_status_revision as make_evm_status_revision,
)
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
from app.market_intel.solana_event_schema import (
    SOLANA_EVENT_SCHEMA_VERSION,
    DecoderStatus,
    FinalityStatus,
    ReorgStatus,
    SolanaEventStatusRevision,
    SolanaSellEvent,
    append_status_revision,
    compute_event_id,
    is_monitor_eligible,
    make_status_revision,
)
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
from app.market_intel.sources.evm_sell_events import (
    DecodedEVMSell,
    EVMProtocolDecoder,
    fixture_decoder,
    make_fixture_decoder,
    normalize_evm_sell_event,
    normalize_evm_sell_events,
)
from app.market_intel.sources.evm_sell_events import (
    build_decoder_registry as build_evm_decoder_registry,
)
from app.market_intel.sources.solana_sell_events import (
    DecodedSolanaSell,
    SolanaProtocolDecoder,
    build_decoder_registry,
    decode_pumpswap_sell,
    decode_raydium_sell,
    normalize_solana_sell_event,
    normalize_solana_sell_events,
)
from app.market_intel.wallet_intelligence import (
    CLUSTER_SELL_VERSION,
    MERGEABLE_RELATION_TYPES,
    WALLET_INTELLIGENCE_VERSION,
    ClusterSellAlert,
    ClusterSellMonitor,
    ClusterSellObservation,
    ConcentrationMetrics,
    WalletCluster,
    WalletClusteringResult,
    WalletRelation,
    WalletTransfer,
    build_wallet_clusters,
    calculate_concentration,
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
    # Solana normalized sell evidence
    "SOLANA_EVENT_SCHEMA_VERSION",
    "DecoderStatus",
    "FinalityStatus",
    "ReorgStatus",
    "SolanaEventStatusRevision",
    "SolanaSellEvent",
    "compute_event_id",
    "make_status_revision",
    "append_status_revision",
    "is_monitor_eligible",
    "DecodedSolanaSell",
    "SolanaProtocolDecoder",
    "build_decoder_registry",
    "decode_raydium_sell",
    "decode_pumpswap_sell",
    "normalize_solana_sell_event",
    "normalize_solana_sell_events",
    "SOLANA_CLUSTER_SELL_ADAPTER_VERSION",
    "ClusterSellRoute",
    "ClusterSellAdapter",
    "build_cluster_sell_observation",
    "route_solana_sell_event",
    "ingest_solana_sell_events",
    # EVM normalized sell evidence
    "EVM_EVENT_SCHEMA_VERSION",
    "EVM_EVENT_VERSION",
    "EVMEventType",
    "EVMDecoderStatus",
    "EVMFinalityStatus",
    "EVMReorgStatus",
    "EVMEventStatusRevision",
    "EVMEvent",
    "EVMSellEvent",
    "compute_evm_event_id",
    "build_evm_event_id",
    "deterministic_evm_event_id",
    "evm_event_identity_material",
    "make_evm_status_revision",
    "append_evm_status_revision",
    "is_evm_monitor_eligible",
    "validate_evm_sell_event",
    "DecodedEVMSell",
    "EVMProtocolDecoder",
    "build_evm_decoder_registry",
    "make_fixture_decoder",
    "fixture_decoder",
    "normalize_evm_sell_event",
    "normalize_evm_sell_events",
    "EVM_CLUSTER_SELL_ADAPTER_VERSION",
    "EVMChainScopedClusterResolver",
    "EVMClusterResolverObject",
    "EVMClusterSellAdapter",
    "EVMClusterSellRoute",
    "adapt_evm_sell_event",
    "build_evm_cluster_sell_observation",
    "route_evm_sell_event",
    "ingest_evm_sell_events",
    # Wallet intelligence
    "WALLET_INTELLIGENCE_VERSION",
    "CLUSTER_SELL_VERSION",
    "MERGEABLE_RELATION_TYPES",
    "WalletRelation",
    "WalletTransfer",
    "WalletCluster",
    "WalletClusteringResult",
    "ConcentrationMetrics",
    "ClusterSellObservation",
    "ClusterSellAlert",
    "ClusterSellMonitor",
    "build_wallet_clusters",
    "calculate_concentration",
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
