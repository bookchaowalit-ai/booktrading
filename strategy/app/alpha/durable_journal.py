"""Local SQLite control state for paper reviews and evidence-backed settlement."""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.alpha.models import AlphaOutcome, AlphaSettlement, SettlementProof

MAX_SETTLEMENT_BYTES = 20 * 1024 * 1024
_EPSILON = 1e-9
_REQUEST_ID_RE = re.compile(r"[0-9a-f]{64}")
_ACCOUNT_SCOPE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_CURRENCY_RE = re.compile(r"^[A-Z][A-Z0-9._-]{1,15}$")


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


class DurablePaperJournal:
    """Serialize paper exposure, settlement, and retries in one local DB.

    The database owns ONLY decisions from this lane. A paper trade reserves
    worst-case purchase risk until ``settle_binary`` verifies a local evidence
    object and records the resulting P&L. No broker, wallet, or exchange
    balance is represented here.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS alpha_policy (
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1), body TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS alpha_reviews (
                    request_id TEXT PRIMARY KEY,
                    instrument TEXT NOT NULL,
                    action TEXT NOT NULL,
                    risk REAL NOT NULL CHECK(risk >= 0),
                    result TEXT NOT NULL,
                    settlement_json TEXT,
                    settled_at TEXT,
                    account_scope TEXT NOT NULL DEFAULT 'paper-default',
                    quote_currency TEXT NOT NULL DEFAULT 'USD',
                    activity_mode TEXT NOT NULL DEFAULT 'paper',
                    starting_capital REAL
                );
                """
            )
            columns = {row[1] for row in db.execute("PRAGMA table_info(alpha_reviews)")}
            if "settlement_json" not in columns:
                db.execute("ALTER TABLE alpha_reviews ADD COLUMN settlement_json TEXT")
            if "settled_at" not in columns:
                db.execute("ALTER TABLE alpha_reviews ADD COLUMN settled_at TEXT")
            if "account_scope" not in columns:
                db.execute("ALTER TABLE alpha_reviews ADD COLUMN account_scope TEXT NOT NULL DEFAULT 'paper-default'")
            if "quote_currency" not in columns:
                db.execute("ALTER TABLE alpha_reviews ADD COLUMN quote_currency TEXT NOT NULL DEFAULT 'USD'")
            if "activity_mode" not in columns:
                db.execute("ALTER TABLE alpha_reviews ADD COLUMN activity_mode TEXT NOT NULL DEFAULT 'paper'")
            if "starting_capital" not in columns:
                db.execute("ALTER TABLE alpha_reviews ADD COLUMN starting_capital REAL")

    def review(
        self,
        request: dict,
        policy: dict,
        evaluate: Callable[[float, int], dict],
        *,
        account_scope: str = "paper-default",
        quote_currency: str = "USD",
        activity_mode: str = "paper",
        starting_capital: float | None = None,
    ) -> dict:
        """Atomically derive exposure, evaluate, and store one immutable result."""

        account_scope, quote_currency, activity_mode, starting_capital = _binding(
            account_scope, quote_currency, activity_mode, starting_capital
        )
        request_material = {
            "request": request,
            "portfolio_binding": {
                "account_scope": account_scope,
                "quote_currency": quote_currency,
                "activity_mode": activity_mode,
                "starting_capital": starting_capital,
            },
        }
        request_id = hashlib.sha256(canonical(request_material).encode()).hexdigest()
        db = sqlite3.connect(self.path, timeout=15)
        try:
            db.execute("BEGIN IMMEDIATE")
            old_policy = db.execute("SELECT body FROM alpha_policy WHERE singleton=1").fetchone()
            encoded_policy = canonical(policy)
            if old_policy and old_policy[0] != encoded_policy:
                raise ValueError("journal policy differs; review policy migration explicitly")
            cached = db.execute(
                "SELECT result, account_scope, quote_currency, activity_mode, starting_capital "
                "FROM alpha_reviews WHERE request_id=?",
                (request_id,),
            ).fetchone()
            if cached:
                if tuple(cached[1:]) != (account_scope, quote_currency, activity_mode, starting_capital):
                    raise ValueError("journal request binding differs; review it under a new request")
                result = json.loads(cached[0])
                result["journal_retry"] = True
                db.commit()
                return result
            exposure, positions = _open_exposure(db, account_scope, quote_currency, activity_mode)
            _check_starting_capital(db, account_scope, quote_currency, activity_mode, starting_capital)
            result = evaluate(exposure, positions)
            decision = result["decision"]
            instrument = decision["platform_id"] + ":" + result["observation"]["metadata"]["ticker"]
            duplicate = db.execute(
                """
                SELECT 1 FROM alpha_reviews
                WHERE instrument=? AND action='TRADE_PAPER' AND settled_at IS NULL
                  AND account_scope=? AND quote_currency=? AND activity_mode=?
                """,
                (instrument, account_scope, quote_currency, activity_mode),
            ).fetchone()
            if duplicate:
                decision["action"] = "WAIT"
                decision["reason_codes"] = ["instrument_already_reserved"]
                for event in result["journal_events"]:
                    if event["event_type"] == "alpha_decision":
                        event["evaluation"]["action"] = "WAIT"
                        event["evaluation"]["reason_codes"] = ["instrument_already_reserved"]
                        event["decision"]["action"] = "WAIT"
                        event["decision"]["reason_codes"] = ["instrument_already_reserved"]
                        event["decision"]["outcome"] = "not_taken"
            risk = decision["risk_amount"] if decision["action"] == "TRADE_PAPER" else 0.0
            result["journal_request_id"] = request_id
            result["journal_retry"] = False
            result["portfolio"] = {
                "scope": "paper_account",
                "account_scope": account_scope,
                "quote_currency": quote_currency,
                "activity_mode": activity_mode,
                "starting_capital": starting_capital,
                "open_risk_before": exposure,
                "open_risk_after": exposure + risk,
                "open_positions_after": positions + int(decision["action"] == "TRADE_PAPER"),
                "settlement_supported": True,
            }
            encoded = canonical(result)
            db.execute("INSERT OR IGNORE INTO alpha_policy VALUES (1,?)", (encoded_policy,))
            db.execute(
                """
                INSERT INTO alpha_reviews
                    (request_id, instrument, action, risk, result, settlement_json, settled_at,
                     account_scope, quote_currency, activity_mode, starting_capital)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    request_id,
                    instrument,
                    decision["action"],
                    risk,
                    encoded,
                    None,
                    None,
                    account_scope,
                    quote_currency,
                    activity_mode,
                    starting_capital,
                ),
            )
            db.commit()
            return result
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def settle_binary(
        self,
        request_id: str,
        *,
        payout_per_unit: float,
        proof: SettlementProof | Mapping[str, Any],
        read_evidence: Callable[[str], bytes],
        settled_at: datetime,
    ) -> dict[str, Any]:
        """Verify a binary payout proof, settle one trade, and release its risk.

        The reader is injected so the journal can remain offline and bounded;
        the implementation never fetches a provider URL. The proof bytes must
        contain a binary ``payout_per_unit``/``payout`` or an equivalent
        ``outcome`` label, and the digest must match before any row is updated.
        """

        normalized_request_id = _request_id(request_id)
        payout = _binary_payout(payout_per_unit)
        settlement_time = _timestamp(settled_at, "settled_at")
        settlement_proof = _coerce_proof(proof)
        if settlement_proof.observed_at > settlement_time:
            raise ValueError("settlement evidence cannot be observed after settlement")
        if not callable(read_evidence):
            raise TypeError("read_evidence must be callable")

        db = sqlite3.connect(self.path, timeout=15)
        try:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                """
                SELECT instrument, action, risk, result, settlement_json,
                       account_scope, quote_currency, activity_mode, starting_capital
                FROM alpha_reviews WHERE request_id=?
                """,
                (normalized_request_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"unknown journal request_id: {normalized_request_id}")
            (
                instrument,
                action,
                stored_risk,
                encoded_result,
                encoded_settlement,
                account_scope,
                quote_currency,
                activity_mode,
                starting_capital,
            ) = row
            if action != "TRADE_PAPER":
                raise ValueError("only TRADE_PAPER reviews can be settled")
            if encoded_settlement is not None:
                stored_settlement = json.loads(encoded_settlement)
                if _same_settlement(stored_settlement, payout, settlement_proof, settlement_time):
                    result = json.loads(encoded_result)
                    result["journal_retry"] = True
                    db.commit()
                    return result
                raise ValueError("journal request already has a different settlement")

            evidence_bytes = read_evidence(settlement_proof.object_key)
            if not isinstance(evidence_bytes, (bytes, bytearray)):
                raise TypeError("read_evidence must return bytes")
            evidence_bytes = bytes(evidence_bytes)
            if len(evidence_bytes) > MAX_SETTLEMENT_BYTES:
                raise ValueError("settlement evidence exceeds byte limit")
            digest = hashlib.sha256(evidence_bytes).hexdigest()
            if digest != settlement_proof.raw_sha256:
                raise ValueError("settlement evidence checksum mismatch")
            payload = _json_object(evidence_bytes)
            observed_payout = _extract_binary_payout(payload)
            if not math.isclose(observed_payout, payout, rel_tol=0.0, abs_tol=_EPSILON):
                raise ValueError("settlement payout does not match the supplied proof")

            result = json.loads(encoded_result)
            decision = result["decision"]
            observation = result["observation"]
            if decision.get("action") != "TRADE_PAPER":
                raise ValueError("stored review is not an open paper trade")
            entry_price = _finite(observation.get("price"), "observation.price", minimum=0.0)
            cost_per_unit = _finite(observation.get("cost_per_unit"), "observation.cost_per_unit", minimum=0.0)
            target_units = _finite(decision.get("metadata", {}).get("target_units"), "target_units", minimum=0.0)
            if target_units <= 0.0:
                raise ValueError("target_units must be positive")
            expected_risk = (entry_price + cost_per_unit) * target_units
            decision_risk = _finite(decision.get("risk_amount"), "decision.risk_amount", minimum=0.0)
            database_risk = _finite(stored_risk, "database risk", minimum=0.0)
            if abs(expected_risk - decision_risk) > _EPSILON or abs(expected_risk - database_risk) > _EPSILON:
                raise ValueError("stored risk and cost basis do not reconcile")
            _check_optional_ticker(payload, settlement_proof, observation, instrument)

            realized_pnl = (payout - entry_price - cost_per_unit) * target_units
            outcome = AlphaOutcome.WIN if payout == 1.0 else AlphaOutcome.LOSS
            settlement = AlphaSettlement(
                outcome=outcome,
                realized_pnl=realized_pnl,
                settled_at=settlement_time,
                note=settlement_proof.summary,
                evidence=(settlement_proof,),
            )
            reconciliation = {
                "status": "reconciled",
                "instrument": instrument,
                "entry_price": entry_price,
                "cost_per_unit": cost_per_unit,
                "target_units": target_units,
                "reserved_risk": database_risk,
                "released_risk": database_risk,
                "payout_per_unit": payout,
                "realized_pnl": realized_pnl,
            }
            _update_decision_event(result, settlement)
            result["settlement"] = settlement.as_dict()
            result["reconciliation"] = reconciliation
            portfolio = result.setdefault("portfolio", {})
            portfolio["settlement_supported"] = True
            portfolio["account_scope"] = account_scope
            portfolio["quote_currency"] = quote_currency
            portfolio["activity_mode"] = activity_mode
            portfolio["starting_capital"] = starting_capital
            portfolio["open_risk_at_review"] = portfolio.get("open_risk_after")
            open_risk_before_settlement, open_positions_before_settlement = _open_exposure(
                db, account_scope, quote_currency, activity_mode
            )
            (
                portfolio["open_risk_after_settlement"],
                portfolio["open_positions_after_settlement"],
            ) = (
                max(0.0, open_risk_before_settlement - database_risk),
                max(0, open_positions_before_settlement - 1),
            )
            reconciliation["open_risk_after"] = portfolio["open_risk_after_settlement"]
            reconciliation["open_positions_after"] = portfolio["open_positions_after_settlement"]
            from app.portfolio.alpha import alpha_settlement_to_paper_trade
            from app.portfolio.finance import paper_trade_to_finance_projection

            paper_trade = alpha_settlement_to_paper_trade(result)
            finance_projection = paper_trade_to_finance_projection(paper_trade)
            result["paper_trade"] = paper_trade.as_dict()
            result["finance_projection"] = finance_projection.as_dict()
            settled_pnl = _settled_pnl(db, account_scope, quote_currency, activity_mode) + realized_pnl
            reserved_after = portfolio["open_risk_after_settlement"]
            portfolio["capital"] = {
                "account_scope": account_scope,
                "currency": quote_currency,
                "activity_mode": activity_mode,
                "starting_capital": starting_capital,
                "realized_pnl": settled_pnl,
                "reserved_risk": reserved_after,
                "available_capital": (
                    None if starting_capital is None else starting_capital + settled_pnl - reserved_after
                ),
            }
            reconciliation["available_capital_after_settlement"] = portfolio["capital"]["available_capital"]
            result["journal_retry"] = False
            encoded = canonical(result)
            db.execute(
                """
                UPDATE alpha_reviews
                SET result=?, settlement_json=?, settled_at=?
                WHERE request_id=?
                """,
                (encoded, canonical(settlement.as_dict()), settlement.settled_at.isoformat(), normalized_request_id),
            )
            db.commit()
            return result
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def reconcile(self, request_id: str) -> dict[str, Any]:
        """Return the current reservation state without exposing raw evidence."""

        normalized_request_id = _request_id(request_id)
        with sqlite3.connect(self.path, timeout=15) as db:
            row = db.execute(
                """
                SELECT instrument, action, risk, result, settlement_json, settled_at,
                       account_scope, quote_currency, activity_mode, starting_capital
                FROM alpha_reviews WHERE request_id=?
                """,
                (normalized_request_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"unknown journal request_id: {normalized_request_id}")
            (
                instrument,
                action,
                risk,
                encoded_result,
                encoded_settlement,
                settled_at,
                account_scope,
                quote_currency,
                activity_mode,
                starting_capital,
            ) = row
            open_risk, open_positions = _open_exposure(db, account_scope, quote_currency, activity_mode)
            response: dict[str, Any] = {
                "journal_request_id": normalized_request_id,
                "instrument": instrument,
                "action": action,
                "open_risk_after": open_risk,
                "open_positions_after": open_positions,
                "portfolio": {
                    "account_scope": account_scope,
                    "quote_currency": quote_currency,
                    "activity_mode": activity_mode,
                    "starting_capital": starting_capital,
                },
            }
            if encoded_settlement is None:
                response.update(
                    {
                        "status": "pending_settlement" if action == "TRADE_PAPER" else "not_settleable",
                        "reserved_risk": risk,
                        "settled_at": None,
                    }
                )
                return response
            result = json.loads(encoded_result)
            response.update(
                {
                    "status": "reconciled",
                    "settlement": json.loads(encoded_settlement),
                    "reconciliation": result.get("reconciliation", {}),
                    "paper_trade": result.get("paper_trade"),
                    "finance_projection": result.get("finance_projection"),
                    "capital": result.get("portfolio", {}).get("capital"),
                    "settled_at": settled_at,
                }
            )
            return response


def _request_id(value: object) -> str:
    if not isinstance(value, str) or _REQUEST_ID_RE.fullmatch(value.lower()) is None:
        raise ValueError("request_id must be a SHA-256 hexadecimal identifier")
    return value.lower()


def _timestamp(value: datetime, field_name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)


def _finite(value: object, field_name: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be numeric")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be numeric") from exc
    if not math.isfinite(number) or (minimum is not None and number < minimum):
        raise ValueError(f"{field_name} must be finite and valid")
    return number


def _binary_payout(value: object) -> float:
    number = _finite(value, "payout_per_unit", minimum=0.0)
    if not math.isclose(number, 0.0, rel_tol=0.0, abs_tol=_EPSILON) and not math.isclose(
        number, 1.0, rel_tol=0.0, abs_tol=_EPSILON
    ):
        raise ValueError("binary settlement payout must be 0 or 1")
    return 1.0 if math.isclose(number, 1.0, rel_tol=0.0, abs_tol=_EPSILON) else 0.0


def _coerce_proof(value: SettlementProof | Mapping[str, Any]) -> SettlementProof:
    if isinstance(value, SettlementProof):
        return value
    if not isinstance(value, Mapping):
        raise TypeError("proof must be a SettlementProof or mapping")
    payload = dict(value)
    observed_at = payload.get("observed_at")
    if isinstance(observed_at, str):
        payload["observed_at"] = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    return SettlementProof(**payload)


def _json_object(value: bytes) -> Mapping[str, Any]:
    try:
        payload = json.loads(value.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("settlement evidence must be UTF-8 JSON") from exc
    if not isinstance(payload, Mapping):
        raise ValueError("settlement evidence must contain a JSON object")
    return payload


def _extract_binary_payout(payload: Mapping[str, Any]) -> float:
    containers: list[Mapping[str, Any]] = [payload]
    for key in ("settlement", "result"):
        nested = payload.get(key)
        if isinstance(nested, Mapping):
            containers.append(nested)
    values: list[float] = []
    labels: list[float] = []
    for container in containers:
        for key in ("payout_per_unit", "payout"):
            if key in container:
                values.append(_binary_payout(container[key]))
        if "outcome" in container:
            label = str(container["outcome"]).strip().lower()
            if label in {"yes", "win", "won", "true", "1"}:
                labels.append(1.0)
            elif label in {"no", "loss", "lost", "false", "0"}:
                labels.append(0.0)
            else:
                raise ValueError("settlement outcome label must be binary")
    candidates = values + labels
    if not candidates:
        raise ValueError("settlement evidence has no binary payout")
    if any(not math.isclose(candidate, candidates[0], rel_tol=0.0, abs_tol=_EPSILON) for candidate in candidates[1:]):
        raise ValueError("settlement evidence contains conflicting payout labels")
    return candidates[0]


def _check_optional_ticker(
    payload: Mapping[str, Any], proof: SettlementProof, observation: Mapping[str, Any], instrument: str
) -> None:
    expected = observation.get("metadata", {}).get("ticker")
    payload_ticker = payload.get("ticker")
    if payload_ticker is None:
        nested = payload.get("settlement")
        if isinstance(nested, Mapping):
            payload_ticker = nested.get("ticker")
    proof_ticker = proof.metadata.get("ticker")
    for actual in (payload_ticker, proof_ticker):
        if actual is not None and actual != expected:
            raise ValueError(f"settlement evidence ticker does not match {instrument}")


def _same_settlement(stored: Mapping[str, Any], payout: float, proof: SettlementProof, settled_at: datetime) -> bool:
    stored_payout = stored.get("payout_per_unit")
    if stored_payout is None:
        stored_payout = 1.0 if stored.get("outcome") == AlphaOutcome.WIN.value else 0.0
    return (
        math.isclose(float(stored_payout), payout, rel_tol=0.0, abs_tol=_EPSILON)
        and stored.get("settled_at") == settled_at.isoformat()
        and stored.get("evidence") == [proof.as_dict()]
    )


def _update_decision_event(result: dict[str, Any], settlement: AlphaSettlement) -> None:
    updated = False
    for event in result.get("journal_events", []):
        if event.get("event_type") != "alpha_decision":
            continue
        decision = event.setdefault("decision", {})
        decision.update(
            {
                "outcome": settlement.outcome.value,
                "realized_pnl": settlement.realized_pnl,
                "settled_at": settlement.settled_at.isoformat(),
                "note": settlement.note,
                "settlement_evidence": [item.as_dict() for item in settlement.evidence],
            }
        )
        updated = True
    if not updated:
        raise ValueError("journal result has no alpha_decision event to settle")


def _open_exposure(
    db: sqlite3.Connection,
    account_scope: str | None = None,
    quote_currency: str | None = None,
    activity_mode: str | None = None,
) -> tuple[float, int]:
    clauses = ["action='TRADE_PAPER'", "settled_at IS NULL"]
    parameters: list[str] = []
    if account_scope is not None:
        clauses.append("account_scope=?")
        parameters.append(account_scope)
    if quote_currency is not None:
        clauses.append("quote_currency=?")
        parameters.append(quote_currency)
    if activity_mode is not None:
        clauses.append("activity_mode=?")
        parameters.append(activity_mode)
    exposure, positions = db.execute(
        f"SELECT COALESCE(SUM(risk),0), COUNT(*) FROM alpha_reviews WHERE {' AND '.join(clauses)}",
        parameters,
    ).fetchone()
    return float(exposure), int(positions)


def _binding(
    account_scope: str,
    quote_currency: str,
    activity_mode: str,
    starting_capital: float | None,
) -> tuple[str, str, str, float | None]:
    if (
        not isinstance(account_scope, str)
        or not _ACCOUNT_SCOPE_RE.fullmatch(account_scope.strip())
        or account_scope.strip().lower().startswith("0x")
    ):
        raise ValueError("account_scope must be a non-address alias")
    account_scope = account_scope.strip()
    if not isinstance(quote_currency, str):
        raise ValueError("quote_currency must be a currency-style code")
    quote_currency = quote_currency.strip().upper()
    if not _CURRENCY_RE.fullmatch(quote_currency):
        raise ValueError("quote_currency must be a currency-style code")
    if activity_mode != "paper":
        raise ValueError("DurablePaperJournal only supports activity_mode='paper'")
    if starting_capital is not None:
        starting_capital = _finite(starting_capital, "starting_capital", minimum=0.0)
    return account_scope, quote_currency, activity_mode, starting_capital


def _check_starting_capital(
    db: sqlite3.Connection,
    account_scope: str,
    quote_currency: str,
    activity_mode: str,
    starting_capital: float | None,
) -> None:
    if starting_capital is None:
        return
    existing = db.execute(
        """
        SELECT starting_capital FROM alpha_reviews
        WHERE account_scope=? AND quote_currency=? AND activity_mode=?
          AND starting_capital IS NOT NULL
        LIMIT 1
        """,
        (account_scope, quote_currency, activity_mode),
    ).fetchone()
    if existing is not None and abs(float(existing[0]) - starting_capital) > _EPSILON:
        raise ValueError("starting_capital differs for the paper account")


def _settled_pnl(
    db: sqlite3.Connection,
    account_scope: str,
    quote_currency: str,
    activity_mode: str,
) -> float:
    total = 0.0
    rows = db.execute(
        """
        SELECT result FROM alpha_reviews
        WHERE account_scope=? AND quote_currency=? AND activity_mode=? AND settled_at IS NOT NULL
        """,
        (account_scope, quote_currency, activity_mode),
    ).fetchall()
    for (encoded_result,) in rows:
        result = json.loads(encoded_result)
        reconciliation = result.get("reconciliation", {})
        total += _finite(reconciliation.get("realized_pnl", 0.0), "stored realized_pnl")
    return total
