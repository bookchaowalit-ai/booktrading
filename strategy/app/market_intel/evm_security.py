"""Read-only EVM security evidence adapters.

This module deliberately does not call an RPC, indexer, simulator, or locker
API.  It accepts provider payloads that were fetched by an outer ingestion
boundary and converts them into the small, auditable evidence contract used by
``risk_gate``.  Provider fields are often strings (``"0"``/``"1"``), nested,
or absent; unknown values remain unknown so the risk gate can abstain.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import Any

EVM_EVIDENCE_VERSION = "evm-security.v1"
EVM_PROVIDERS = frozenset({"goplus", "honeypot", "simulation", "lp_custody", "rpc"})
SUPPORTED_EVM_CHAINS = frozenset({"ethereum", "bsc", "base", "arbitrum"})


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _normalize_chain(chain: str) -> str:
    normalized = str(chain).strip().lower()
    if normalized not in SUPPORTED_EVM_CHAINS:
        raise ValueError(f"unsupported EVM chain: {chain}")
    return normalized


def _first(mapping: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value is not None:
            return value
    return None


def _nested(mapping: Mapping[str, Any], *paths: tuple[str, ...]) -> Any:
    for path in paths:
        current: Any = mapping
        for key in path:
            current = _as_mapping(current).get(key)
            if current is None:
                break
        if current is not None:
            return current
    return None


def _unwrap(payload: Mapping[str, Any] | None, *, token_address: str | None = None) -> Mapping[str, Any]:
    """Unwrap common provider envelopes without assuming a response shape."""

    current = _as_mapping(payload)
    for key in ("result", "data", "token", "tokenSecurity", "token_security"):
        nested = current.get(key)
        if isinstance(nested, Mapping):
            current = nested
    if token_address:
        normalized_address = token_address.lower()
        for key, value in current.items():
            if str(key).lower() == normalized_address and isinstance(value, Mapping):
                current = value
                break
    return current


def _as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "active", "enabled", "blocked", "failed"}:
            return True
        if normalized in {"0", "false", "no", "n", "inactive", "disabled", "passed", "success"}:
            return False
    return None


def _as_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result and result not in {float("inf"), float("-inf")} else None


def _as_ratio(value: Any) -> float | None:
    result = _as_float(value)
    if result is not None and 1 < result <= 100:
        result /= 100
    return result if result is not None and 0 <= result <= 1 else None


def _as_bps(value: Any, *, percent: bool = True) -> float | None:
    """Normalize a percent or bps provider tax into basis points."""

    result = _as_float(value)
    if result is None or result < 0:
        return None
    # GoPlus/Honeypot commonly expose a percent (e.g. 5 = 5%).  Values over
    # 100 are treated as bps so a provider can send 1500 directly.
    return result * 100 if percent and result <= 100 else result


def _as_iso(value: Any) -> str | None:
    if isinstance(value, datetime):
        parsed = value if value.tzinfo else value.replace(tzinfo=UTC)
        return parsed.isoformat()
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=UTC).isoformat()
        except (OverflowError, OSError, ValueError):
            return None
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return value.strip()
    return (parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)).isoformat()


def _flag_list(*values: Any) -> list[str]:
    result: set[str] = set()
    for value in values:
        if isinstance(value, str):
            normalized = value.strip().lower().replace("-", "_")
            if normalized:
                result.add(normalized)
        elif isinstance(value, Mapping):
            result.update(_flag_list(value.get("name"), value.get("flag"), value.get("type")))
        elif isinstance(value, (list, tuple, set, frozenset)):
            result.update(_flag_list(*value))
    return sorted(result)


def _status(value: Any) -> str | None:
    if value is None:
        return None
    return str(value).strip().lower().replace(" ", "_") or None


def normalize_goplus_response(
    payload: Mapping[str, Any] | None,
    *,
    chain: str,
    token_address: str,
    checked_at: Any = None,
) -> dict[str, Any]:
    """Normalize a GoPlus-like token-security response.

    Only explicit provider controls become booleans.  Missing fields are
    omitted, which prevents an unavailable endpoint from looking safe.
    """

    source = _unwrap(payload, token_address=token_address)
    contract: dict[str, Any] = {}
    aliases = {
        "verified": ("is_open_source", "open_source", "verified", "contract_verified"),
        "honeypot": ("is_honeypot", "honeypot"),
        "mintable": ("is_mintable", "mintable", "can_mint"),
        "blacklist_active": ("is_blacklisted", "blacklist", "blacklist_enabled", "blacklist_active"),
        "pause_active": ("transfer_pausable", "is_pausable", "paused", "pause_active"),
        "is_proxy": ("is_proxy", "proxy", "upgradable", "is_upgradable"),
        "hidden_owner": ("hidden_owner", "owner_hidden"),
        "owner_can_change_balance": ("can_take_back_ownership", "owner_can_change_balance"),
        "selfdestruct": ("selfdestruct", "self_destruct"),
        "tax_mutable": ("slippage_modifiable", "tax_mutable", "tax_can_change"),
        "sell_blocked": ("cannot_sell_all", "cannot_sell", "sell_restricted", "transfer_blocked"),
    }
    for name, keys in aliases.items():
        value = _as_bool(_first(source, *keys))
        if value is not None:
            contract[name] = value

    proxy_admin = _first(source, "proxy_admin", "proxyAdmin", "admin")
    if proxy_admin is None and contract.get("is_proxy"):
        proxy_admin = _first(source, "owner_address", "owner")
    if proxy_admin not in (None, "", "0x0000000000000000000000000000000000000000"):
        contract["proxy_admin"] = str(proxy_admin)
    implementation = _first(source, "implementation", "implementation_address", "logic_address")
    if implementation:
        contract["implementation"] = str(implementation)

    taxes = [
        _as_bps(_first(source, "buy_tax", "buyTax", "buy_fee")),
        _as_bps(_first(source, "sell_tax", "sellTax", "sell_fee")),
        _as_bps(_first(source, "tax_bps", "transfer_fee_bps"), percent=False),
    ]
    taxes = [tax for tax in taxes if tax is not None]
    if taxes:
        contract["tax_bps"] = max(taxes)

    findings = _flag_list(
        "blacklist_control_active" if contract.get("blacklist_active") else None,
        "pause_control_active" if contract.get("pause_active") else None,
        "upgrade_authority_present" if contract.get("is_proxy") or contract.get("implementation") else None,
        "owner_can_change_balance" if contract.get("owner_can_change_balance") else None,
        "selfdestruct_enabled" if contract.get("selfdestruct") else None,
        "mutable_tax" if contract.get("tax_mutable") else None,
        "sell_blocked" if contract.get("sell_blocked") else None,
    )
    if findings:
        contract["risk_flags"] = findings

    checked = _as_iso(checked_at or _first(source, "checked_at", "updated_at", "as_of"))
    result: dict[str, Any] = {
        "provider": "goplus",
        "provider_version": EVM_EVIDENCE_VERSION,
        "chain": _normalize_chain(chain),
        "token_address": token_address,
        "contract": contract,
        "checked_at": checked,
    }
    return {key: value for key, value in result.items() if value not in (None, {}, [])}


def normalize_honeypot_response(
    payload: Mapping[str, Any] | None,
    *,
    chain: str,
    token_address: str,
    checked_at: Any = None,
) -> dict[str, Any]:
    """Normalize Honeypot.is-style simulation and honeypot fields."""

    source = _unwrap(payload, token_address=token_address)
    honeypot_result = _as_mapping(_first(source, "honeypotResult", "honeypot_result"))
    simulation_result = _as_mapping(_first(source, "simulationResult", "simulation_result"))
    is_honeypot = _as_bool(_first(honeypot_result, "isHoneypot", "is_honeypot"))
    simulation_success = _as_bool(_first(simulation_result, "simulationSuccess", "simulation_success", "success"))
    sell_success = _as_bool(_first(simulation_result, "sellSuccess", "sell_success", "canSell", "can_sell"))
    status = "failed" if is_honeypot is True or sell_success is False else None
    if status is None and simulation_success is False:
        status = "inconclusive"
    if status is None and sell_success is True:
        status = "passed"
    if status is None:
        status = _status(_first(source, "status", "simulation_status")) or "inconclusive"

    simulation: dict[str, Any] = {"status": status}
    if sell_success is not None:
        simulation["sell_success"] = sell_success
    if simulation_success is not None:
        simulation["simulation_success"] = simulation_success
    reason = _first(
        honeypot_result,
        "honeypotReason",
        "honeypot_reason",
        "reason",
    ) or _first(simulation_result, "error", "revertReason", "revert_reason")
    if reason:
        simulation["failure_reason"] = str(reason)
    buy_tax = _as_bps(_first(simulation_result, "buyTax", "buy_tax"))
    sell_tax = _as_bps(_first(simulation_result, "sellTax", "sell_tax"))
    if buy_tax is not None:
        simulation["buy_tax_bps"] = buy_tax
    if sell_tax is not None:
        simulation["sell_tax_bps"] = sell_tax

    contract: dict[str, Any] = {}
    if is_honeypot is not None:
        contract["honeypot"] = is_honeypot
    if is_honeypot is True:
        contract["risk_flags"] = ["honeypot_detected"]
    checked = _as_iso(checked_at or _first(source, "checked_at", "updated_at", "as_of"))
    result: dict[str, Any] = {
        "provider": "honeypot",
        "provider_version": EVM_EVIDENCE_VERSION,
        "chain": _normalize_chain(chain),
        "token_address": token_address,
        "exit": {"simulation": simulation},
        "contract": contract,
        "checked_at": checked,
    }
    return {key: value for key, value in result.items() if value not in (None, {}, [])}


def normalize_sell_simulation(
    payload: Mapping[str, Any] | None,
    *,
    chain: str,
    token_address: str,
    checked_at: Any = None,
) -> dict[str, Any]:
    """Normalize a read-only buy/sell simulation result.

    A missing success bit is explicitly ``inconclusive``.  This is important
    because a provider timeout or unsupported route must never become a pass.
    """

    source = _unwrap(payload, token_address=token_address)
    sell_success = _as_bool(_first(source, "sell_success", "sellSuccess", "can_sell", "canSell"))
    simulation_success = _as_bool(_first(source, "simulation_success", "simulationSuccess", "success"))
    status = _status(_first(source, "status", "result", "simulation_status"))
    if sell_success is False or status in {"failed", "reverted", "blocked", "honeypot", "error"}:
        status = "failed"
    elif simulation_success is False:
        status = "inconclusive"
    elif sell_success is True and status not in {"failed", "reverted", "blocked", "honeypot"}:
        status = "passed"
    elif status not in {"passed", "success", "succeeded", "ok"}:
        status = "inconclusive"

    simulation: dict[str, Any] = {"status": status}
    if sell_success is not None:
        simulation["sell_success"] = sell_success
    if simulation_success is not None:
        simulation["simulation_success"] = simulation_success
    for output_key, aliases in {
        "amount_in": ("amount_in", "amountIn"),
        "amount_out": ("amount_out", "amountOut"),
        "gas_used": ("gas_used", "gasUsed"),
        "price_impact_bps": ("price_impact_bps", "priceImpactBps"),
        "route": ("route", "path"),
        "failure_reason": ("failure_reason", "failureReason", "error", "revertReason", "revert_reason"),
    }.items():
        value = _first(source, *aliases)
        if value not in (None, ""):
            simulation[output_key] = value

    result: dict[str, Any] = {
        "provider": "simulation",
        "provider_version": EVM_EVIDENCE_VERSION,
        "chain": _normalize_chain(chain),
        "token_address": token_address,
        "exit": {"simulation": simulation},
        "checked_at": _as_iso(checked_at or _first(source, "checked_at", "updated_at", "as_of")),
    }
    return {key: value for key, value in result.items() if value not in (None, {}, [])}


def normalize_lp_custody(
    payload: Mapping[str, Any] | None,
    *,
    chain: str,
    token_address: str,
    checked_at: Any = None,
) -> dict[str, Any]:
    """Normalize LP lock/burn/NFT custody evidence.

    ``lp_burned`` is retained as a finding but does not imply a locked ratio;
    the caller must provide a measurable ratio or verified custody proof.
    """

    source = _unwrap(payload, token_address=token_address)
    liquidity: dict[str, Any] = {}
    ratio = _as_ratio(_first(source, "lp_locked_ratio", "locked_ratio", "lock_ratio", "locked_percent"))
    if ratio is not None:
        liquidity["lp_locked_ratio"] = ratio
    for output_key, aliases in {
        "liquidity_usd": ("liquidity_usd", "usd", "total_usd", "tvl_usd"),
        "active_depth_usd": ("active_depth_usd", "executable_depth_usd"),
        "lock_expires_at": ("lock_expires_at", "expires_at", "unlock_at", "unlockTime"),
        "custody_verified": ("custody_verified", "verified", "locker_verified", "nft_custody_verified"),
        "lp_locked": ("lp_locked", "locked", "lock_active"),
        "lp_burned": ("lp_burned", "burned"),
        "emergency_withdrawal": ("emergency_withdrawal", "can_emergency_withdraw"),
    }.items():
        value = _first(source, *aliases)
        if output_key in {"custody_verified", "lp_locked", "lp_burned", "emergency_withdrawal"}:
            value = _as_bool(value)
        elif output_key == "lock_expires_at":
            value = _as_iso(value)
        elif output_key in {"liquidity_usd", "active_depth_usd"}:
            value = _as_float(value)
        if value is not None:
            liquidity[output_key] = value
    flags = _flag_list(
        "lp_burned" if liquidity.get("lp_burned") else None,
        "emergency_withdrawal" if liquidity.get("emergency_withdrawal") else None,
    )
    if flags:
        liquidity["risk_flags"] = flags
    result: dict[str, Any] = {
        "provider": "lp_custody",
        "provider_version": EVM_EVIDENCE_VERSION,
        "chain": _normalize_chain(chain),
        "token_address": token_address,
        "liquidity": liquidity,
        "checked_at": _as_iso(checked_at or _first(source, "checked_at", "updated_at", "as_of")),
    }
    return {key: value for key, value in result.items() if value not in (None, {}, [])}


def _merge_sections(observations: list[Mapping[str, Any]], section: str) -> tuple[dict[str, Any], list[str]]:
    merged: dict[str, Any] = {}
    conflicts: list[str] = []
    for observation in observations:
        values = _as_mapping(observation.get(section))
        for key, value in values.items():
            if value is None:
                continue
            if key in merged and merged[key] != value:
                conflicts.append(f"{section}.{key}")
                continue
            merged[key] = value
    return merged, conflicts


def merge_evm_observations(
    observations: Iterable[Mapping[str, Any]],
    *,
    chain: str,
    token_address: str,
    checked_at: Any = None,
    liquidity: Mapping[str, Any] | None = None,
    holders: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge canonical adapter outputs while preserving provider conflicts.

    Conflicting provider claims are carried into ``risk_evidence`` and are
    later quarantined by ``risk_gate``.  The merge never resolves a failed
    sell simulation by counting a second provider's logo.
    """

    items = [_as_mapping(item) for item in observations]
    if not items:
        raise ValueError("at least one EVM observation is required")
    contract, contract_conflicts = _merge_sections(items, "contract")
    exit_sections = [_as_mapping(_as_mapping(item.get("exit")).get("simulation")) for item in items]
    simulation: dict[str, Any] = {}
    conflicts = list(contract_conflicts)
    for item in exit_sections:
        for key, value in item.items():
            if value is None:
                continue
            if key in simulation and simulation[key] != value:
                conflicts.append(f"exit.simulation.{key}")
                continue
            simulation[key] = value
    liquidity_sections, liquidity_conflicts = _merge_sections(items, "liquidity")
    conflicts.extend(liquidity_conflicts)
    if liquidity:
        for key, value in liquidity.items():
            if value is not None:
                if key in liquidity_sections and liquidity_sections[key] != value:
                    conflicts.append(f"liquidity.{key}")
                else:
                    liquidity_sections[key] = value

    providers = sorted(
        {
            str(item.get("provider_id") or item.get("provider"))
            for item in items
            if item.get("provider_id") or item.get("provider")
        }
    )
    independence_groups = sorted(
        {
            str(item.get("independence_group") or item.get("provider_id") or item.get("provider"))
            for item in items
            if item.get("provider_id") or item.get("provider")
        }
    )
    as_of_values = [item.get("checked_at") for item in items if item.get("checked_at")]
    evidence: dict[str, Any] = {
        "evidence_version": EVM_EVIDENCE_VERSION,
        "checked_at": _as_iso(checked_at) or (max(as_of_values) if as_of_values else None),
        "contract": contract,
        "exit": {"simulation": simulation},
        "liquidity": liquidity_sections,
        "provider_sources": providers,
        "independent_provider_count": len(independence_groups),
        "independence_groups": independence_groups,
        "lp_custody_verification_required": True,
    }
    provenance = [dict(_as_mapping(item.get("provenance"))) for item in items if _as_mapping(item.get("provenance"))]
    if provenance:
        evidence["provenance"] = provenance
    if holders:
        evidence["holders"] = dict(holders)
    if conflicts:
        evidence["provider_conflict"] = True
        evidence["conflicts"] = sorted(set(conflicts))
    result: dict[str, Any] = {
        "chain": _normalize_chain(chain),
        "token_address": token_address,
        "decoder_status": "verified",
        "risk_evidence": evidence,
        "provider_sources": providers,
        "provider_observations": {
            str(item.get("provider_id") or item.get("provider")): {
                "checked_at": item.get("checked_at"),
                **({"independence_group": item.get("independence_group")} if item.get("independence_group") else {}),
                **({"provenance": dict(_as_mapping(item.get("provenance")))} if item.get("provenance") else {}),
            }
            for item in items
            if item.get("provider_id") or item.get("provider")
        },
    }
    return result


def build_evm_risk_evidence(
    *,
    chain: str,
    token_address: str,
    goplus: Mapping[str, Any] | None = None,
    honeypot: Mapping[str, Any] | None = None,
    simulation: Mapping[str, Any] | None = None,
    lp_custody: Mapping[str, Any] | None = None,
    liquidity: Mapping[str, Any] | None = None,
    holders: Mapping[str, Any] | None = None,
    checked_at: Any = None,
) -> dict[str, Any]:
    """Build canonical risk metadata from already-fetched EVM observations."""

    observations: list[dict[str, Any]] = []
    if goplus is not None:
        observations.append(
            normalize_goplus_response(
                goplus,
                chain=chain,
                token_address=token_address,
                checked_at=checked_at,
            )
        )
    if honeypot is not None:
        observations.append(
            normalize_honeypot_response(
                honeypot,
                chain=chain,
                token_address=token_address,
                checked_at=checked_at,
            )
        )
    if simulation is not None:
        observations.append(
            normalize_sell_simulation(
                simulation,
                chain=chain,
                token_address=token_address,
                checked_at=checked_at,
            )
        )
    if lp_custody is not None:
        observations.append(
            normalize_lp_custody(
                lp_custody,
                chain=chain,
                token_address=token_address,
                checked_at=checked_at,
            )
        )
    if not observations:
        raise ValueError("at least one EVM provider payload is required")
    return merge_evm_observations(
        observations,
        chain=chain,
        token_address=token_address,
        checked_at=checked_at,
        liquidity=liquidity,
        holders=holders,
    )


# Aliases make the adapter discoverable to callers using provider terminology.
normalize_goplus = normalize_goplus_response
normalize_honeypot = normalize_honeypot_response
normalize_simulation = normalize_sell_simulation
normalize_lp_lock = normalize_lp_custody
merge_evidence = merge_evm_observations


__all__ = [
    "EVM_EVIDENCE_VERSION",
    "EVM_PROVIDERS",
    "SUPPORTED_EVM_CHAINS",
    "build_evm_risk_evidence",
    "merge_evidence",
    "merge_evm_observations",
    "normalize_goplus",
    "normalize_goplus_response",
    "normalize_honeypot",
    "normalize_honeypot_response",
    "normalize_lp_custody",
    "normalize_lp_lock",
    "normalize_sell_simulation",
    "normalize_simulation",
]
