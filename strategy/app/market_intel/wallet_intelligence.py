"""Read-only wallet graph, concentration, and cluster-sell intelligence.

This module is a portable contract candidate for a future wallet-intelligence
data product. It does not call an RPC, infer ownership from funding alone, or
sign and submit transactions.
"""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from math import isfinite
from typing import Any

WALLET_INTELLIGENCE_VERSION = "wallet-intelligence.v1"
CLUSTER_SELL_VERSION = "cluster-sell-monitor.v1"
MERGEABLE_RELATION_TYPES = frozenset({"same_owner", "shared_control"})


def _required_text(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} is required")
    if len(text) > 256:
        raise ValueError(f"{field_name} is too long")
    return text.lower() if text.startswith("0x") else text


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError("observed_at must be a datetime")
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _confidence(value: Any) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("confidence must be a finite number") from exc
    if not isfinite(result) or result < 0 or result > 1:
        raise ValueError("confidence must be between 0 and 1")
    return result


def _positive_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer") from exc
    if result <= 0:
        raise ValueError(f"{field_name} must be positive")
    return result


def _non_negative_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer") from exc
    if result < 0:
        raise ValueError(f"{field_name} must not be negative")
    return result


def _chain(value: Any) -> str:
    return _required_text(value, "chain").lower()


def _cluster_id(chain: str, members: Iterable[str]) -> str:
    canonical = "|".join((_chain(chain), *sorted(set(members))))
    digest = sha256(canonical.encode("utf-8")).hexdigest()[:24]
    return f"cluster_{digest}"


@dataclass(frozen=True, slots=True)
class WalletRelation:
    """A graph relation; funding evidence is retained but not ownership proof."""

    chain: str
    source_wallet: str
    target_wallet: str
    relation_type: str
    source: str
    confidence: float
    observed_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "chain", _chain(self.chain))
        object.__setattr__(self, "source_wallet", _required_text(self.source_wallet, "source_wallet"))
        object.__setattr__(self, "target_wallet", _required_text(self.target_wallet, "target_wallet"))
        object.__setattr__(self, "relation_type", _required_text(self.relation_type, "relation_type").lower())
        object.__setattr__(self, "source", _required_text(self.source, "source"))
        object.__setattr__(self, "confidence", _confidence(self.confidence))
        object.__setattr__(self, "observed_at", _utc(self.observed_at))

    @property
    def mergeable(self) -> bool:
        """Whether this relation can join ownership clusters."""

        return self.relation_type in MERGEABLE_RELATION_TYPES

    def as_dict(self) -> dict[str, Any]:
        return {
            "chain": self.chain,
            "source_wallet": self.source_wallet,
            "target_wallet": self.target_wallet,
            "relation_type": self.relation_type,
            "source": self.source,
            "confidence": self.confidence,
            "observed_at": self.observed_at.isoformat(),
            "mergeable": self.mergeable,
        }


@dataclass(frozen=True, slots=True)
class WalletTransfer:
    """Normalized transfer input for a downstream graph/indexer consumer."""

    chain: str
    token_address: str
    tx_hash: str
    log_index: int
    from_wallet: str
    to_wallet: str
    amount: int
    block_number: int
    observed_at: datetime
    source: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "chain", _required_text(self.chain, "chain").lower())
        object.__setattr__(self, "token_address", _required_text(self.token_address, "token_address"))
        object.__setattr__(self, "tx_hash", _required_text(self.tx_hash, "tx_hash"))
        object.__setattr__(self, "log_index", _non_negative_int(self.log_index, "log_index"))
        object.__setattr__(self, "from_wallet", _required_text(self.from_wallet, "from_wallet"))
        object.__setattr__(self, "to_wallet", _required_text(self.to_wallet, "to_wallet"))
        object.__setattr__(self, "amount", _positive_int(self.amount, "amount"))
        object.__setattr__(self, "block_number", _non_negative_int(self.block_number, "block_number"))
        object.__setattr__(self, "observed_at", _utc(self.observed_at))
        object.__setattr__(self, "source", _required_text(self.source, "source"))

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": WALLET_INTELLIGENCE_VERSION,
            "chain": self.chain,
            "token_address": self.token_address,
            "tx_hash": self.tx_hash,
            "log_index": self.log_index,
            "from_wallet": self.from_wallet,
            "to_wallet": self.to_wallet,
            "amount": self.amount,
            "block_number": self.block_number,
            "observed_at": self.observed_at.isoformat(),
            "source": self.source,
        }


@dataclass(frozen=True, slots=True)
class WalletCluster:
    """A deterministic ownership hypothesis, not a legal ownership claim."""

    chain: str
    cluster_id: str
    members: tuple[str, ...]
    merge_evidence: tuple[str, ...]
    confidence: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": WALLET_INTELLIGENCE_VERSION,
            "chain": self.chain,
            "cluster_id": self.cluster_id,
            "members": list(self.members),
            "member_count": len(self.members),
            "merge_evidence": list(self.merge_evidence),
            "confidence": self.confidence,
        }


@dataclass(frozen=True, slots=True)
class WalletClusteringResult:
    """Cluster output plus relations deliberately excluded from merging."""

    chain: str
    wallet_to_cluster: Mapping[str, str]
    clusters: tuple[WalletCluster, ...]
    retained_relations: tuple[WalletRelation, ...]

    def cluster_for(self, wallet: str) -> str:
        canonical = _required_text(wallet, "wallet")
        existing = self.wallet_to_cluster.get(canonical)
        return existing or _cluster_id(self.chain, (canonical,))

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": WALLET_INTELLIGENCE_VERSION,
            "chain": self.chain,
            "clusters": [cluster.as_dict() for cluster in self.clusters],
            "retained_relations": [relation.as_dict() for relation in self.retained_relations],
        }


class _UnionFind:
    def __init__(self, values: Iterable[str]):
        self.parent = {value: value for value in values}
        self.rank = {value: 0 for value in self.parent}

    def find(self, value: str) -> str:
        parent = self.parent[value]
        if parent != value:
            self.parent[value] = self.find(parent)
        return self.parent[value]

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return
        if self.rank[left_root] < self.rank[right_root]:
            left_root, right_root = right_root, left_root
        self.parent[right_root] = left_root
        if self.rank[left_root] == self.rank[right_root]:
            self.rank[left_root] += 1


def build_wallet_clusters(
    wallets: Iterable[str],
    relations: Iterable[WalletRelation],
    *,
    chain: str,
    min_merge_confidence: float = 0.90,
) -> WalletClusteringResult:
    """Build deterministic clusters without treating funding as ownership.

    Only explicit ``same_owner`` and ``shared_control`` relations above the
    confidence threshold can merge wallets. ``funded_by``, ``common_funder``,
    and exchange relations remain available as graph evidence.
    """

    normalized_chain = _chain(chain)
    threshold = _confidence(min_merge_confidence)
    normalized_wallets = {_required_text(wallet, "wallet") for wallet in wallets}
    normalized_relations = tuple(relations)
    for relation in normalized_relations:
        if relation.chain != normalized_chain:
            raise ValueError("all wallet relations must belong to the requested chain")
        normalized_wallets.update((relation.source_wallet, relation.target_wallet))

    union_find = _UnionFind(normalized_wallets)
    applied: dict[str, list[WalletRelation]] = defaultdict(list)
    retained: list[WalletRelation] = []
    for relation in normalized_relations:
        if relation.mergeable and relation.confidence >= threshold:
            union_find.union(relation.source_wallet, relation.target_wallet)
            root = union_find.find(relation.source_wallet)
            applied[root].append(relation)
        else:
            retained.append(relation)

    groups: dict[str, list[str]] = defaultdict(list)
    for wallet in sorted(normalized_wallets):
        groups[union_find.find(wallet)].append(wallet)

    clusters: list[WalletCluster] = []
    wallet_to_cluster: dict[str, str] = {}
    for members in sorted(groups.values(), key=lambda item: tuple(item)):
        cluster_id = _cluster_id(normalized_chain, members)
        evidence = [
            relation
            for relation_list in applied.values()
            for relation in relation_list
            if relation.source_wallet in members and relation.target_wallet in members
        ]
        confidence = min((relation.confidence for relation in evidence), default=0.0)
        cluster = WalletCluster(
            chain=normalized_chain,
            cluster_id=cluster_id,
            members=tuple(members),
            merge_evidence=tuple(
                sorted(
                    f"{relation.relation_type}:{min(relation.source_wallet, relation.target_wallet)}"
                    f"<->{max(relation.source_wallet, relation.target_wallet)}"
                    for relation in evidence
                )
            ),
            confidence=confidence,
        )
        clusters.append(cluster)
        wallet_to_cluster.update({wallet: cluster_id for wallet in members})

    return WalletClusteringResult(
        chain=normalized_chain,
        wallet_to_cluster=wallet_to_cluster,
        clusters=tuple(sorted(clusters, key=lambda item: item.cluster_id)),
        retained_relations=tuple(retained),
    )


@dataclass(frozen=True, slots=True)
class ConcentrationMetrics:
    """Raw and cluster-adjusted concentration for an observed token supply."""

    chain: str
    denominator_supply: int
    observed_supply: int
    excluded_supply: int
    coverage: float
    raw_top5_share: float
    cluster_top5_share: float
    cluster_hhi: float
    cluster_balances: tuple[tuple[str, int], ...]
    excluded_wallets: tuple[str, ...]

    @property
    def effective_concentration(self) -> float:
        return self.cluster_top5_share

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": WALLET_INTELLIGENCE_VERSION,
            "chain": self.chain,
            "denominator_supply": self.denominator_supply,
            "observed_supply": self.observed_supply,
            "excluded_supply": self.excluded_supply,
            "coverage": self.coverage,
            "raw_top5_share": self.raw_top5_share,
            "cluster_top5_share": self.cluster_top5_share,
            "effective_concentration": self.effective_concentration,
            "cluster_hhi": self.cluster_hhi,
            "cluster_balances": [
                {"cluster_id": cluster_id, "balance": balance}
                for cluster_id, balance in self.cluster_balances
            ],
            "excluded_wallets": list(self.excluded_wallets),
            "basis": "explicit-exclusion-and-ownership-cluster",
        }


def calculate_concentration(
    balances: Mapping[str, int],
    clustering: WalletClusteringResult | None = None,
    *,
    total_supply: int | None = None,
    excluded_wallets: Collection[str] = (),
    chain: str = "unknown",
) -> ConcentrationMetrics:
    """Calculate concentration without guessing pool, bridge, or CEX roles."""

    normalized_balances: dict[str, int] = {}
    for wallet, balance in balances.items():
        canonical_wallet = _required_text(wallet, "wallet")
        normalized_balance = _non_negative_int(balance, "balance")
        normalized_balances[canonical_wallet] = normalized_balances.get(canonical_wallet, 0) + normalized_balance

    denominator = (
        _positive_int(total_supply, "total_supply")
        if total_supply is not None
        else sum(normalized_balances.values())
    )
    if denominator <= 0:
        raise ValueError("balances must contain positive observed supply or total_supply")

    excluded = {_required_text(wallet, "excluded_wallet") for wallet in excluded_wallets}
    excluded_supply = sum(
        balance for wallet, balance in normalized_balances.items() if wallet in excluded
    )
    eligible_balances = {
        wallet: balance for wallet, balance in normalized_balances.items() if wallet not in excluded
    }
    observed_supply = sum(eligible_balances.values())
    if observed_supply > denominator:
        raise ValueError("observed balances exceed total_supply")

    cluster_result = clustering or build_wallet_clusters(eligible_balances, (), chain=chain)
    cluster_totals: dict[str, int] = defaultdict(int)
    for wallet, balance in eligible_balances.items():
        cluster_totals[cluster_result.cluster_for(wallet)] += balance

    raw_top5 = sum(sorted(eligible_balances.values(), reverse=True)[:5]) / denominator
    cluster_values = sorted(cluster_totals.values(), reverse=True)
    cluster_top5 = sum(cluster_values[:5]) / denominator
    cluster_hhi = sum((balance / denominator) ** 2 for balance in cluster_values)
    return ConcentrationMetrics(
        chain=cluster_result.chain,
        denominator_supply=denominator,
        observed_supply=observed_supply,
        excluded_supply=excluded_supply,
        coverage=observed_supply / denominator,
        raw_top5_share=raw_top5,
        cluster_top5_share=cluster_top5,
        cluster_hhi=cluster_hhi,
        cluster_balances=tuple(sorted(cluster_totals.items())),
        excluded_wallets=tuple(sorted(excluded)),
    )


@dataclass(frozen=True, slots=True)
class ClusterSellObservation:
    """One normalized sell event from a read-only event consumer."""

    chain: str
    token_address: str
    cluster_id: str
    wallet: str
    amount_token: int
    quote_value_usd: float
    tx_hash: str
    log_index: int
    block_number: int
    observed_at: datetime
    source: str
    cluster_balance_before: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "chain", _required_text(self.chain, "chain").lower())
        object.__setattr__(self, "token_address", _required_text(self.token_address, "token_address"))
        object.__setattr__(self, "cluster_id", _required_text(self.cluster_id, "cluster_id"))
        object.__setattr__(self, "wallet", _required_text(self.wallet, "wallet"))
        object.__setattr__(self, "amount_token", _positive_int(self.amount_token, "amount_token"))
        try:
            quote_value = float(self.quote_value_usd)
        except (TypeError, ValueError) as exc:
            raise ValueError("quote_value_usd must be a finite number") from exc
        if not isfinite(quote_value) or quote_value < 0:
            raise ValueError("quote_value_usd must not be negative")
        object.__setattr__(self, "quote_value_usd", quote_value)
        object.__setattr__(self, "tx_hash", _required_text(self.tx_hash, "tx_hash"))
        object.__setattr__(self, "log_index", _non_negative_int(self.log_index, "log_index"))
        object.__setattr__(self, "block_number", _non_negative_int(self.block_number, "block_number"))
        object.__setattr__(self, "observed_at", _utc(self.observed_at))
        object.__setattr__(self, "source", _required_text(self.source, "source"))
        object.__setattr__(
            self,
            "cluster_balance_before",
            _positive_int(self.cluster_balance_before, "cluster_balance_before"),
        )

    @property
    def event_key(self) -> tuple[str, str, str, str, int, int]:
        return (self.chain, self.token_address, self.cluster_id, self.tx_hash, self.log_index, self.block_number)

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": CLUSTER_SELL_VERSION,
            "chain": self.chain,
            "token_address": self.token_address,
            "cluster_id": self.cluster_id,
            "wallet": self.wallet,
            "amount_token": self.amount_token,
            "quote_value_usd": self.quote_value_usd,
            "tx_hash": self.tx_hash,
            "log_index": self.log_index,
            "block_number": self.block_number,
            "observed_at": self.observed_at.isoformat(),
            "source": self.source,
            "cluster_balance_before": self.cluster_balance_before,
        }


@dataclass(frozen=True, slots=True)
class ClusterSellAlert:
    """A bounded alert, not a trade instruction."""

    alert_id: str
    chain: str
    token_address: str
    cluster_id: str
    window_start: datetime
    window_end: datetime
    event_count: int
    unique_wallets: int
    sell_amount_token: int
    quote_value_usd: float
    baseline_cluster_balance: int
    sell_share: float
    severity: str
    reasons: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": CLUSTER_SELL_VERSION,
            "alert_id": self.alert_id,
            "chain": self.chain,
            "token_address": self.token_address,
            "cluster_id": self.cluster_id,
            "window_start": self.window_start.isoformat(),
            "window_end": self.window_end.isoformat(),
            "event_count": self.event_count,
            "unique_wallets": self.unique_wallets,
            "sell_amount_token": self.sell_amount_token,
            "quote_value_usd": self.quote_value_usd,
            "baseline_cluster_balance": self.baseline_cluster_balance,
            "sell_share": self.sell_share,
            "severity": self.severity,
            "reasons": list(self.reasons),
            "trade_instruction": False,
        }


class ClusterSellMonitor:
    """Windowed cluster sell monitor with explicit thresholds and no trading side effects."""

    def __init__(
        self,
        *,
        window_seconds: int = 300,
        min_sell_share: float = 0.05,
        min_unique_wallets: int = 2,
        critical_sell_share: float = 0.20,
        max_events_per_key: int = 500,
    ) -> None:
        if window_seconds < 1:
            raise ValueError("window_seconds must be positive")
        if min_unique_wallets < 1:
            raise ValueError("min_unique_wallets must be positive")
        if max_events_per_key < 1:
            raise ValueError("max_events_per_key must be positive")
        self.window = timedelta(seconds=window_seconds)
        self.min_sell_share = _confidence(min_sell_share)
        self.min_unique_wallets = min_unique_wallets
        self.critical_sell_share = _confidence(critical_sell_share)
        if self.critical_sell_share < self.min_sell_share:
            raise ValueError("critical_sell_share must be >= min_sell_share")
        self.max_events_per_key = max_events_per_key
        self._events: dict[tuple[str, str, str], deque[ClusterSellObservation]] = defaultdict(deque)
        self._seen_events: set[tuple[str, str, str, str, int, int]] = set()

    def ingest(self, observation: ClusterSellObservation) -> ClusterSellAlert | None:
        """Add one event and return an alert when the configured policy fires."""

        if observation.event_key in self._seen_events:
            return None
        self._seen_events.add(observation.event_key)
        key = (observation.chain, observation.token_address, observation.cluster_id)
        events = self._events[key]
        cutoff = observation.observed_at - self.window
        while events and events[0].observed_at < cutoff:
            self._seen_events.discard(events.popleft().event_key)
        events.append(observation)
        while len(events) > self.max_events_per_key:
            self._seen_events.discard(events.popleft().event_key)

        amount = sum(event.amount_token for event in events)
        baseline = max(event.cluster_balance_before for event in events)
        sell_share = amount / baseline
        unique_wallets = len({event.wallet for event in events})
        critical = sell_share >= self.critical_sell_share
        threshold_reached = sell_share >= self.min_sell_share
        multi_wallet = unique_wallets >= self.min_unique_wallets
        if not threshold_reached or not (multi_wallet or critical):
            return None

        severity = "critical" if critical else "high"
        window_start = events[0].observed_at
        window_end = events[-1].observed_at
        identity = "|".join(
            (
                observation.chain,
                observation.token_address,
                observation.cluster_id,
                window_start.isoformat(),
                window_end.isoformat(),
            )
        )
        alert_id = f"sell_{sha256(identity.encode('utf-8')).hexdigest()[:24]}"
        reasons = [f"cluster_sell_share>={sell_share:.6f}", f"unique_sellers={unique_wallets}"]
        return ClusterSellAlert(
            alert_id=alert_id,
            chain=observation.chain,
            token_address=observation.token_address,
            cluster_id=observation.cluster_id,
            window_start=window_start,
            window_end=window_end,
            event_count=len(events),
            unique_wallets=unique_wallets,
            sell_amount_token=amount,
            quote_value_usd=sum(event.quote_value_usd for event in events),
            baseline_cluster_balance=baseline,
            sell_share=sell_share,
            severity=severity,
            reasons=tuple(reasons),
        )


__all__ = [
    "CLUSTER_SELL_VERSION",
    "MERGEABLE_RELATION_TYPES",
    "WALLET_INTELLIGENCE_VERSION",
    "ClusterSellAlert",
    "ClusterSellMonitor",
    "ClusterSellObservation",
    "ConcentrationMetrics",
    "WalletCluster",
    "WalletClusteringResult",
    "WalletRelation",
    "WalletTransfer",
    "build_wallet_clusters",
    "calculate_concentration",
]
