"""Deterministic risk evidence gate for meme/degen discovery.

The gate is deliberately read-only.  It does not call a provider, sign a
transaction, or claim that a token is safe.  It turns the evidence already
attached to a :class:`MarketQuote` into an auditable state and applies hard
vetoes before momentum or volume signals can become opportunities.

Missing, stale, conflicting, or provider-only evidence is an abstention.  A
positive state therefore means "eligible for this bounded research workflow"
and never means "will not rug".
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from math import isfinite
from typing import Any

POLICY_VERSION = "meme-risk.v1"
DEFAULT_MAX_AGE_SECONDS = 15 * 60
MIN_LIQUIDITY_USD = 5_000.0
MIN_LP_LOCKED_RATIO = 0.80
MAX_SAFE_TRANSFER_FEE_BPS = 1_000
SUPPORTED_CHAINS = frozenset({"solana", "bsc", "ethereum", "base", "arbitrum"})
EVM_CHAINS = frozenset({"bsc", "ethereum", "base", "arbitrum"})


class RiskState(StrEnum):
    """Research state emitted by the risk gate."""

    DETECTED = "detected"
    UNSUPPORTED = "unsupported"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    HIGH_RISK = "high_risk"
    WATCHLIST = "watchlist"
    PAPER_CANDIDATE = "paper_candidate"
    INVALIDATED = "invalidated"


@dataclass(frozen=True, slots=True)
class RiskEvidence:
    """Typed view over provider metadata used by the decision policy.

    The raw provider payload is retained in quote metadata.  This class only
    contains normalized fields needed by the deterministic gate, which keeps
    provider schema changes from silently changing the policy.
    """

    chain: str | None = None
    token_address: str | None = None
    checked_at: datetime | None = None
    decoder_status: str | None = None
    authority_checked: bool = False
    holder_concentration: float | None = None
    liquidity_usd: float | None = None
    active_depth_usd: float | None = None
    lp_locked_ratio: float | None = None
    lp_lock_expires_at: datetime | None = None
    lp_custody_verified: bool | None = None
    sell_simulation_status: str | None = None
    sell_simulation_proved: bool = False
    provider_conflict: bool = False
    provider_incomplete: bool = False
    risk_flags: tuple[str, ...] = field(default_factory=tuple)
    provider_sources: tuple[str, ...] = field(default_factory=tuple)
    independent_provider_count: int = 0
    event_type: str | None = None
    price_available: bool = False
    demand_observed: bool = False

    @classmethod
    def from_metadata(cls, metadata: Mapping[str, Any] | None) -> RiskEvidence:
        """Build the typed view without exposing provider-specific parsing."""

        return _normalize_evidence(_as_mapping(metadata))


@dataclass(frozen=True, slots=True)
class RiskDecision:
    """Stable, serializable result of :func:`evaluate_risk`."""

    state: RiskState
    eligible: bool
    confidence: float
    vetoes: tuple[str, ...] = field(default_factory=tuple)
    findings: tuple[str, ...] = field(default_factory=tuple)
    missing_evidence: tuple[str, ...] = field(default_factory=tuple)
    stale_evidence: bool = False
    provider_conflict: bool = False
    evidence_coverage: float = 0.0
    checked_at: str | None = None
    evidence_as_of: str | None = None
    policy_version: str = POLICY_VERSION

    @property
    def hard_veto(self) -> bool:
        """Whether the result must be excluded from opportunity ranking."""

        return self.state in {
            RiskState.UNSUPPORTED,
            RiskState.INSUFFICIENT_EVIDENCE,
            RiskState.HIGH_RISK,
            RiskState.DETECTED,
            RiskState.INVALIDATED,
        }

    def as_dict(self) -> dict[str, Any]:
        """Return JSON-safe metadata for a ``MarketQuote`` or lake row."""

        payload = asdict(self)
        payload["state"] = self.state.value
        payload["vetoes"] = list(self.vetoes)
        payload["findings"] = list(self.findings)
        payload["missing_evidence"] = list(self.missing_evidence)
        payload["hard_veto"] = self.hard_veto
        return payload


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _first(mapping: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value is not None:
            return value
    return None


def _coalesce(*values: Any) -> Any:
    """Return the first non-null value, preserving valid zero/false values."""

    for value in values:
        if value is not None:
            return value
    return None


def _as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "y", "1", "active", "enabled", "blocked", "failed"}:
            return True
        if normalized in {"false", "no", "n", "0", "inactive", "disabled", "passed", "success"}:
            return False
    return None


def _control_present(value: Any) -> bool:
    """Interpret provider control fields without treating ``"false"`` as active."""

    parsed = _as_bool(value)
    if parsed is not None:
        return parsed
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, frozenset, dict)):
        return bool(value)
    return value is not None


def _as_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if isfinite(result) else None


def _as_ratio(value: Any) -> float | None:
    """Normalize a ratio expressed as either 0..1 or a percentage."""

    result = _as_float(value)
    if result is not None and 1 < result <= 100:
        result /= 100
    return result if result is not None and 0 <= result <= 1 else None


def _as_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _normalize_flags(*values: Any) -> set[str]:
    flags: set[str] = set()
    for value in values:
        if isinstance(value, str):
            flags.add(value.strip().lower().replace("-", "_"))
        elif isinstance(value, Mapping):
            for key in ("flag", "name", "type", "extension"):
                nested = value.get(key)
                if nested is not None:
                    flags.update(_normalize_flags(nested))
        elif isinstance(value, (list, tuple, set, frozenset)):
            flags.update(_normalize_flags(*value))
    return {flag for flag in flags if flag}


def _merge_evidence(metadata: Mapping[str, Any]) -> tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]]:
    """Return normalized risk, on-chain, and contract sections."""

    risk = _as_mapping(metadata.get("risk_evidence"))
    onchain = _as_mapping(metadata.get("onchain_risk"))
    contract = _as_mapping(
        _first(
            risk,
            "contract",
            "contract_security",
            "evm_security",
        )
        or _first(metadata, "contract", "contract_security", "evm_security", "security")
    )
    return risk, onchain, contract


def _normalize_evidence(metadata: Mapping[str, Any]) -> RiskEvidence:
    risk, onchain, contract = _merge_evidence(metadata)
    authority = _as_mapping(_coalesce(risk.get("authority"), metadata.get("authority")))
    exit_evidence = _as_mapping(
        _first(risk, "exit", "simulation", "exit_simulation", "sell_simulation")
        or _first(metadata, "exit", "simulation", "exit_simulation", "sell_simulation")
    )
    liquidity_evidence = _as_mapping(
        _first(risk, "liquidity", "lp_lock", "liquidity_lock")
        or _first(metadata, "liquidity_evidence", "lp_lock", "liquidity_lock")
    )
    holder_evidence = _as_mapping(
        _first(risk, "holders", "holder_distribution") or _first(metadata, "holders", "holder_distribution")
    )

    chain = str(_first(risk, "chain") or metadata.get("chain") or "").strip().lower() or None
    token_address = _first(risk, "token_address", "address") or metadata.get("token_address")
    checked_at = _as_datetime(
        _first(
            risk,
            "checked_at",
            "inspected_at",
            "observed_at",
            "as_of",
        )
        or _first(onchain, "checked_at", "inspected_at", "observed_at", "as_of")
        or _first(metadata, "risk_checked_at", "risk_as_of", "checked_at", "observed_at")
    )

    flags = _normalize_flags(
        metadata.get("risk_flags"),
        risk.get("risk_flags"),
        onchain.get("risk_flags"),
        contract.get("risk_flags"),
        liquidity_evidence.get("risk_flags"),
        exit_evidence.get("risk_flags"),
    )
    extensions = _normalize_flags(onchain.get("extensions"), risk.get("extensions"))
    flags.update(
        {f"extension_{extension}" for extension in extensions if extension and extension not in {"none", "unknown"}}
    )
    if "permanentdelegate" in extensions:
        flags.add("permanent_delegate")
    if "transferhook" in extensions:
        flags.add("transfer_hook")
    if "defaultaccountstate" in extensions:
        flags.add("default_account_state")
    if "pausable" in extensions:
        flags.add("pausable")

    # Provider-specific aliases are intentionally normalized here rather than
    # being interpreted throughout the scanner.
    authority_checked = bool(
        onchain.get("status") == "observed"
        or _as_bool(_first(risk, "authority_checked", "authorities_checked")) is True
        or _as_bool(_first(contract, "verified", "security_checked", "owner_checked")) is True
        or bool(authority)
        or any(key in onchain for key in ("mintAuthority", "mint_authority", "freezeAuthority", "freeze_authority"))
        or any(key in contract for key in ("owner", "admin", "proxy_admin", "implementation"))
    )

    holder_concentration = _as_ratio(
        _coalesce(
            _first(
                holder_evidence,
                "top5_concentration",
                "top5_holder_concentration",
                "concentration",
            ),
            _first(risk, "top5_holder_concentration", "holder_concentration"),
            onchain.get("top5_holder_concentration"),
            metadata.get("top5_holder_concentration"),
        )
    )
    liquidity_usd = _as_float(
        _coalesce(
            _first(liquidity_evidence, "liquidity_usd", "usd", "total_usd"),
            _first(risk, "liquidity_usd"),
            metadata.get("liquidity_usd"),
        )
    )
    active_depth_usd = _as_float(
        _coalesce(
            _first(liquidity_evidence, "active_depth_usd", "executable_depth_usd"),
            _first(risk, "active_depth_usd"),
            metadata.get("active_depth_usd"),
        )
    )
    lp_locked_ratio = _as_ratio(
        _coalesce(
            _first(liquidity_evidence, "locked_ratio", "lp_locked_ratio", "lock_ratio"),
            _first(risk, "lp_locked_ratio", "locked_ratio"),
            metadata.get("lp_locked_ratio"),
        )
    )
    lp_lock_expires_at = _as_datetime(
        _coalesce(
            _first(liquidity_evidence, "expires_at", "unlock_at", "lock_expires_at"),
            _first(risk, "lp_lock_expires_at", "unlock_at"),
            metadata.get("lp_lock_expires_at"),
        )
    )
    lp_custody_verified = _as_bool(
        _coalesce(
            _first(liquidity_evidence, "custody_verified", "locker_verified", "nft_custody_verified"),
            _first(risk, "lp_custody_verified", "custody_verified"),
            metadata.get("lp_custody_verified"),
        )
    )

    simulation_evidence = _as_mapping(
        _coalesce(
            exit_evidence.get("simulation"),
            exit_evidence.get("sell"),
            exit_evidence.get("sell_check"),
        )
    )
    sell_evidence = simulation_evidence
    sell_status = _first(
        sell_evidence,
        "status",
        "result",
    )
    sell_status = _coalesce(
        sell_status,
        _first(exit_evidence, "sell_status", "status", "result"),
        _first(risk, "sell_simulation_status"),
        metadata.get("sell_simulation_status"),
    )
    sell_status = str(sell_status).strip().lower() if sell_status is not None else None
    sell_proved = bool(
        _as_bool(
            _coalesce(
                _first(sell_evidence, "success", "sell_success", "sell_proved", "passed"),
                _first(exit_evidence, "sell_success", "sell_proved", "passed"),
                _first(exit_evidence, "simulation_success"),
                _first(metadata, "sell_success", "sell_proved"),
            )
        )
        is True
        or sell_status in {"passed", "pass", "success", "succeeded", "ok"}
    )

    conflict_value = _coalesce(
        _first(risk, "provider_conflict", "conflict"),
        _first(metadata, "provider_conflict", "evidence_conflict"),
    )
    provider_conflict = _as_bool(conflict_value) is True
    conflicts = _first(risk, "conflicts") or _first(metadata, "evidence_conflicts")
    if isinstance(conflicts, (list, tuple, set, frozenset)) and conflicts:
        provider_conflict = True
    provider_failures = _coalesce(risk.get("provider_failures"), metadata.get("provider_failures"))
    provider_incomplete = (
        _as_bool(_coalesce(risk.get("provider_incomplete"), metadata.get("provider_incomplete"))) is True
    )
    if isinstance(provider_failures, (list, tuple, set, frozenset, Mapping)) and provider_failures:
        provider_incomplete = True

    observations = _as_mapping(_coalesce(metadata.get("provider_observations"), risk.get("provider_observations")))
    independent_sources = _as_float(_first(risk, "independent_provider_count"))
    if independent_sources is None:
        independent_sources = _as_float(_first(metadata, "independent_provider_count"))
    if independent_sources is None:
        provider_values = _coalesce(metadata.get("provider_sources"), risk.get("provider_sources"))
        if isinstance(provider_values, (list, tuple, set, frozenset)):
            independent_sources = float(len({str(item) for item in provider_values if str(item).strip()}))
        else:
            independent_sources = float(len(observations)) if observations else 0.0

    # Detect materially different provider observations.  Two API names are
    # not automatically independent; this only quarantines clear conflicts.
    for field_name in ("price", "liquidity", "liquidity_usd"):
        values = [_as_float(_as_mapping(item).get(field_name)) for item in observations.values()]
        values = [value for value in values if value is not None and value >= 0]
        if len(values) >= 2:
            low, high = min(values), max(values)
            if (low == 0 and high > 0) or (low > 0 and (high - low) / low > 0.50):
                provider_conflict = True

    decoder_status = _first(risk, "decoder_status") or _first(metadata, "decoder_status")
    if decoder_status is not None:
        decoder_status = str(decoder_status).strip().lower()

    demand_observed = bool(
        (_as_float(metadata.get("volume_24h")) or 0) > 0
        or (_as_float(metadata.get("unique_buyers")) or 0) > 0
        or (_as_float(risk.get("unique_buyers")) or 0) > 0
    )
    return RiskEvidence(
        chain=chain,
        token_address=str(token_address) if token_address else None,
        checked_at=checked_at,
        decoder_status=decoder_status,
        authority_checked=authority_checked,
        holder_concentration=holder_concentration,
        liquidity_usd=liquidity_usd,
        active_depth_usd=active_depth_usd,
        lp_locked_ratio=lp_locked_ratio,
        lp_lock_expires_at=lp_lock_expires_at,
        lp_custody_verified=lp_custody_verified,
        sell_simulation_status=sell_status,
        sell_simulation_proved=sell_proved,
        provider_conflict=provider_conflict,
        provider_incomplete=provider_incomplete,
        risk_flags=tuple(sorted(flags)),
        provider_sources=tuple(
            sorted(_normalize_flags(_coalesce(metadata.get("provider_sources"), risk.get("provider_sources"))))
        ),
        independent_provider_count=int(independent_sources or 0),
        event_type=str(metadata.get("event_type")) if metadata.get("event_type") else None,
        price_available=(_as_float(_coalesce(metadata.get("price"), metadata.get("price_usd"))) or 0) > 0,
        demand_observed=demand_observed,
    )


def _configured_max_age() -> int:
    raw = os.getenv("MARKET_INTEL_RISK_MAX_AGE_SECONDS")
    try:
        value = int(raw) if raw else DEFAULT_MAX_AGE_SECONDS
    except ValueError:
        value = DEFAULT_MAX_AGE_SECONDS
    return max(60, min(value, 24 * 60 * 60))


def _has_any(metadata: Mapping[str, Any], *keys: str) -> bool:
    risk, onchain, contract = _merge_evidence(metadata)
    sections = (metadata, risk, onchain, contract)
    return any(key in section and section.get(key) is not None for section in sections for key in keys)


def _explicit_vetoes(
    metadata: Mapping[str, Any], evidence: RiskEvidence, *, now: datetime
) -> tuple[set[str], set[str]]:
    risk, onchain, contract = _merge_evidence(metadata)
    authority = _as_mapping(_coalesce(risk.get("authority"), metadata.get("authority")))
    liquidity_evidence = _as_mapping(
        _coalesce(
            risk.get("liquidity"),
            risk.get("lp_lock"),
            risk.get("liquidity_lock"),
            metadata.get("liquidity_evidence"),
            metadata.get("lp_lock"),
            metadata.get("liquidity_lock"),
        )
    )
    exit_evidence = _as_mapping(
        _first(risk, "exit", "simulation", "exit_simulation", "sell_simulation")
        or _first(metadata, "exit", "simulation", "exit_simulation", "sell_simulation")
    )
    simulation_evidence = _as_mapping(
        _coalesce(
            exit_evidence.get("simulation"),
            exit_evidence.get("sell"),
            exit_evidence.get("sell_check"),
        )
    )
    flags = set(evidence.risk_flags)
    vetoes: set[str] = set()
    findings: set[str] = set()

    def flag(name: str, *aliases: str, veto: bool = True) -> None:
        keys = (name, *aliases)
        present = name in flags or any(
            _control_present(section.get(key))
            for section in (
                metadata,
                risk,
                onchain,
                contract,
                authority,
                exit_evidence,
                simulation_evidence,
                liquidity_evidence,
            )
            for key in keys
        )
        if present:
            (vetoes if veto else findings).add(name)

    flag("honeypot_detected", "honeypot", "is_honeypot", "is_honeypot_detected")
    flag("sell_blocked", "sell_restricted", "cannot_sell", "cannot_sell_all", "transfer_blocked", "sell_revert")
    flag("blacklist_control_active", "blacklist_active", "blacklist", "is_blacklisted")
    flag("pause_control_active", "pause_active", "paused", "is_paused", "is_pausable")
    flag("mint_authority_present", "mint_authority", "mintable", "is_mintable")
    flag("freeze_authority_present", "freeze_authority", "freezable", "is_freezable")
    flag("permanent_delegate", "permanentDelegate")
    flag("transfer_hook", "transferHook")
    flag("upgrade_authority_present", "upgrade_authority", "upgradeAuthority", "can_upgrade", "upgradable")
    flag("proxy_admin_present", "proxy_admin", "proxyAdmin")
    flag("mutable_tax", "tax_mutable", "taxCanChange", "slippage_modifiable")
    flag("default_frozen", "defaultFrozen")
    flag("holder_concentration_high", "top5_holder_concentration_high")
    flag("owner_can_change_balance", "can_take_back_ownership", "hidden_owner")
    flag("selfdestruct_enabled", "selfdestruct", "self_destruct")
    flag("lp_emergency_withdrawal", "emergency_withdrawal", "can_emergency_withdraw")

    # Token-2022 transfer fees and EVM taxes are policy vetoes only when the
    # actual rate is known to exceed the bounded exit threshold.
    fee_values = [
        _as_float(_first(section, "transfer_fee_bps", "sell_tax_bps", "tax_bps"))
        for section in (risk, contract, simulation_evidence, metadata)
    ]
    fee_values = [value for value in fee_values if value is not None]
    fee_bps = max(fee_values) if fee_values else None
    if fee_bps is not None and fee_bps > MAX_SAFE_TRANSFER_FEE_BPS:
        vetoes.add("transfer_fee_above_policy")
    elif "transfer_fee_config" in flags or "extension_transferfeeconfig" in flags:
        findings.add("transfer_fee_config_present")

    if evidence.holder_concentration is not None:
        if evidence.holder_concentration >= 0.50:
            vetoes.add("holder_concentration_high")
        elif evidence.holder_concentration >= 0.20:
            findings.add("holder_concentration_elevated")

    if evidence.liquidity_usd is not None and evidence.liquidity_usd < MIN_LIQUIDITY_USD:
        vetoes.add("liquidity_below_policy")
    if evidence.active_depth_usd is not None and evidence.active_depth_usd < MIN_LIQUIDITY_USD:
        vetoes.add("active_depth_below_policy")

    lp_locked_value = _coalesce(
        _first(liquidity_evidence, "lp_locked", "locked"),
        _first(risk, "lp_locked", "locked"),
        metadata.get("lp_locked"),
    )
    if _as_bool(lp_locked_value) is False:
        vetoes.add("lp_not_locked")
    elif evidence.lp_locked_ratio is not None:
        if evidence.lp_locked_ratio < MIN_LP_LOCKED_RATIO:
            vetoes.add("lp_lock_below_policy")
        elif evidence.lp_lock_expires_at and evidence.lp_lock_expires_at <= now + timedelta(hours=24):
            # A lock that expires inside a 24h research horizon is not a
            # durable exit control even when its current ratio is high.
            vetoes.add("lp_lock_expiring_soon")

    if evidence.sell_simulation_status in {"failed", "reverted", "blocked", "honeypot"}:
        vetoes.add("sell_simulation_failed")
    if evidence.provider_conflict:
        findings.add("provider_conflict")
    if evidence.provider_incomplete:
        findings.add("provider_unavailable")
    if evidence.decoder_status in {"unsupported", "unknown", "inconclusive", "unverified"}:
        findings.add(f"decoder_{evidence.decoder_status}")
    return vetoes, findings


def evaluate_risk(
    metadata: Mapping[str, Any] | None,
    *,
    now: datetime | None = None,
    max_age_seconds: int | None = None,
) -> RiskDecision:
    """Evaluate one quote's evidence without network or trading side effects."""

    metadata = _as_mapping(metadata)
    evidence = _normalize_evidence(metadata)
    now = now or datetime.now(UTC)
    now = now if now.tzinfo else now.replace(tzinfo=UTC)
    max_age = max_age_seconds if max_age_seconds is not None else _configured_max_age()
    max_age = max(60, int(max_age))

    vetoes, findings = _explicit_vetoes(metadata, evidence, now=now)
    missing: set[str] = set()
    stale = False

    if not evidence.chain or not evidence.token_address:
        missing.add("chain_and_token_identity")
    if evidence.chain not in SUPPORTED_CHAINS:
        state = RiskState.UNSUPPORTED
        return RiskDecision(
            state=state,
            eligible=False,
            confidence=0.0,
            vetoes=tuple(sorted(vetoes)),
            findings=tuple(sorted(findings | {"chain_or_protocol_unsupported"})),
            missing_evidence=tuple(sorted(missing)),
            evidence_coverage=0.0,
            policy_version=POLICY_VERSION,
        )

    if evidence.decoder_status in {"unsupported"} or _as_bool(metadata.get("protocol_supported")) is False:
        return RiskDecision(
            state=RiskState.UNSUPPORTED,
            eligible=False,
            confidence=0.0,
            vetoes=tuple(sorted(vetoes)),
            findings=tuple(sorted(findings | {"chain_or_protocol_unsupported"})),
            missing_evidence=tuple(sorted(missing)),
            evidence_coverage=0.0,
            policy_version=POLICY_VERSION,
        )

    if evidence.checked_at is None:
        missing.add("freshness_timestamp")
    else:
        age = (now - evidence.checked_at).total_seconds()
        if age < -60 or age > max_age:
            stale = True
            findings.add("evidence_stale_or_clock_skewed")

    if not evidence.authority_checked:
        missing.add("authority_controls")
    if evidence.liquidity_usd is None:
        missing.add("liquidity")
    if not evidence.sell_simulation_proved:
        missing.add("sell_simulation")
    if evidence.holder_concentration is None:
        missing.add("holder_distribution")
    if evidence.independent_provider_count < 2:
        missing.add("independent_provider_confirmation")
    if evidence.lp_locked_ratio is None:
        missing.add("liquidity_custody")
    if evidence.lp_custody_verified is False:
        missing.add("liquidity_custody_verification")
    risk, _, _ = _merge_evidence(metadata)
    custody_required = (
        _as_bool(
            _coalesce(
                _first(risk, "lp_custody_verification_required", "custody_verification_required"),
                metadata.get("lp_custody_verification_required"),
            )
        )
        is True
    )
    if custody_required and evidence.lp_custody_verified is not True:
        missing.add("liquidity_custody_verification")
    if evidence.provider_conflict:
        missing.add("provider_reconciliation")
    if evidence.provider_incomplete:
        missing.add("provider_availability")

    # Discovery events have their own state so a raw event cannot be confused
    # with a priced opportunity.  A known veto still wins over this state.
    event_only = bool(evidence.event_type and not evidence.price_available and evidence.liquidity_usd is None)
    required = 8
    covered = required - len(missing)
    coverage = max(0.0, min(1.0, covered / required))

    if metadata.get("invalidated") or metadata.get("reorged"):
        state = RiskState.INVALIDATED
    elif vetoes:
        state = RiskState.HIGH_RISK
    elif event_only and len(missing) >= 3:
        state = RiskState.DETECTED
    elif stale or missing:
        state = RiskState.INSUFFICIENT_EVIDENCE
    else:
        paper_ready = bool(
            _as_bool(metadata.get("paper_candidate_eligible")) is True
            or _as_bool(_as_mapping(metadata.get("risk_evidence")).get("paper_candidate_eligible")) is True
        )
        state = RiskState.PAPER_CANDIDATE if paper_ready and evidence.demand_observed else RiskState.WATCHLIST

    eligible = state in {RiskState.WATCHLIST, RiskState.PAPER_CANDIDATE}
    confidence = coverage
    if state == RiskState.HIGH_RISK:
        confidence = min(1.0, max(0.5, coverage))
    elif state in {RiskState.DETECTED, RiskState.INSUFFICIENT_EVIDENCE, RiskState.UNSUPPORTED, RiskState.INVALIDATED}:
        confidence = min(0.35, coverage)

    checked_at = evidence.checked_at.isoformat() if evidence.checked_at else None
    return RiskDecision(
        state=state,
        eligible=eligible,
        confidence=round(confidence, 4),
        vetoes=tuple(sorted(vetoes)),
        findings=tuple(sorted(findings)),
        missing_evidence=tuple(sorted(missing)),
        stale_evidence=stale,
        provider_conflict=evidence.provider_conflict,
        evidence_coverage=round(coverage, 4),
        checked_at=checked_at,
        evidence_as_of=checked_at,
        policy_version=POLICY_VERSION,
    )


def annotate_risk(metadata: dict[str, Any], *, now: datetime | None = None) -> RiskDecision:
    """Attach a risk decision to mutable quote metadata and return it."""

    decision = evaluate_risk(metadata, now=now)
    metadata["risk_decision"] = decision.as_dict()
    metadata["risk_state"] = decision.state.value
    metadata["risk_vetoes"] = list(decision.vetoes)
    metadata["risk_findings"] = list(decision.findings)
    metadata["risk_missing_evidence"] = list(decision.missing_evidence)
    metadata["risk_evidence_coverage"] = decision.evidence_coverage
    metadata["risk_policy_version"] = decision.policy_version
    return decision


def opportunity_allowed(metadata: Mapping[str, Any]) -> bool:
    """Return true only for watchlist/paper states after a fresh evaluation."""

    state = metadata.get("risk_state")
    if state not in {RiskState.WATCHLIST.value, RiskState.PAPER_CANDIDATE.value}:
        return False
    decision = _as_mapping(metadata.get("risk_decision"))
    return bool(decision.get("eligible") is True and decision.get("hard_veto") is False)


# Explicit aliases make the contract discoverable to callers that use the
# product language rather than the implementation name.
evaluate_meme_risk = evaluate_risk
apply_risk_gate = annotate_risk


__all__ = [
    "DEFAULT_MAX_AGE_SECONDS",
    "EVM_CHAINS",
    "MIN_LIQUIDITY_USD",
    "POLICY_VERSION",
    "SUPPORTED_CHAINS",
    "RiskDecision",
    "RiskEvidence",
    "RiskState",
    "annotate_risk",
    "apply_risk_gate",
    "evaluate_meme_risk",
    "evaluate_risk",
    "opportunity_allowed",
]
