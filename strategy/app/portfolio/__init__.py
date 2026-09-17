"""Shared paper portfolio, platform capability, and reward accounting."""

from app.portfolio.alpha import alpha_settlement_to_finance_projection, alpha_settlement_to_paper_trade
from app.portfolio.finance import (
    FinanceProjection,
    paper_trade_to_finance_projection,
    portfolio_finance_projections,
    reward_to_finance_projection,
)
from app.portfolio.integrations import (
    PortfolioIntegrationError,
    WorldPortfolioReplayResult,
    replay_world_to_portfolio,
    world_report_to_paper_trades,
)
from app.portfolio.ledger import LedgerConflictError, PaperPortfolioLedger
from app.portfolio.models import (
    ActivityMode,
    CapabilityStatus,
    PaperCapitalAccount,
    PaperTrade,
    PaperTradeStatus,
    PlatformCapability,
    PlatformDomain,
    PortfolioSnapshot,
    RewardEntry,
    RewardKind,
    RewardStatus,
)
from app.portfolio.registry import (
    REGISTRY_VERSION,
    PlatformRegistry,
    PlatformRegistryError,
    default_platform_registry,
)
from app.portfolio.replay import (
    FIXTURE_VERSION,
    PortfolioReplayError,
    PortfolioReplayReport,
    load_portfolio_fixture,
    replay_portfolio_fixture,
)
from app.portfolio.rewards import (
    AirdropRewardConversionError,
    AirdropRewardConversionReport,
    convert_airdrop_tasks,
    sync_airdrop_tracker_to_ledger,
)

__all__ = [
    "FIXTURE_VERSION",
    "REGISTRY_VERSION",
    "ActivityMode",
    "AirdropRewardConversionError",
    "AirdropRewardConversionReport",
    "CapabilityStatus",
    "FinanceProjection",
    "LedgerConflictError",
    "PaperCapitalAccount",
    "PaperPortfolioLedger",
    "PaperTrade",
    "PaperTradeStatus",
    "PlatformCapability",
    "PlatformDomain",
    "PlatformRegistry",
    "PlatformRegistryError",
    "PortfolioIntegrationError",
    "PortfolioReplayError",
    "PortfolioReplayReport",
    "PortfolioSnapshot",
    "RewardEntry",
    "RewardKind",
    "RewardStatus",
    "WorldPortfolioReplayResult",
    "alpha_settlement_to_finance_projection",
    "alpha_settlement_to_paper_trade",
    "convert_airdrop_tasks",
    "default_platform_registry",
    "load_portfolio_fixture",
    "paper_trade_to_finance_projection",
    "portfolio_finance_projections",
    "replay_portfolio_fixture",
    "replay_world_to_portfolio",
    "reward_to_finance_projection",
    "sync_airdrop_tracker_to_ledger",
    "world_report_to_paper_trades",
]
