import json
import subprocess
import sys
from pathlib import Path

STRATEGY_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = STRATEGY_ROOT / "scripts" / "world_market_import.py"


def _world_response() -> bytes:
    return (
        json.dumps(
            {
                "events": [
                    {
                        "ticker": "BTC15M",
                        "title": "BTC direction in 15 minutes",
                        "markets": [
                            {
                                "ticker": "BTC15M-UP",
                                "question": "Will BTC be up at settlement?",
                                "status": "active",
                                "yes_bid": 0.42,
                                "yes_ask": 0.44,
                                "no_bid": 0.48,
                                "no_ask": 0.50,
                                "yes_ask_size": 2,
                                "no_ask_size": 3,
                                "volume": 5_000,
                                "liquidity": 2_000,
                                "strikeDate": "2026-09-12T12:00:00Z",
                                "resolutionSource": "provider_rulebook",
                            }
                        ],
                    }
                ]
            },
            separators=(",", ":"),
        ).encode()
        + b"\n"
    )


def _run_import(payload: Path, lake: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--payload",
            str(payload),
            "--landing-dir",
            str(lake),
            "--received-at",
            "2026-09-12T10:00:00Z",
            "--json",
        ],
        cwd=STRATEGY_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_local_import_lands_exact_bytes_and_reports_paper_signal(tmp_path):
    payload = tmp_path / "world-events.json"
    raw = _world_response()
    payload.write_bytes(raw)
    lake = tmp_path / "lake"

    result = _run_import(payload, lake)

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["mode"] == "local_json_paper_import"
    assert report["execution_enabled"] is False
    assert report["markets_scanned"] == 1
    assert report["quality_eligible_market_count"] == 1
    assert report["signals"][0]["ticker"] == "BTC15M-UP"
    assert report["signals"][0]["side"] == "BUY_BOTH_REVIEW"
    assert report["landing"]["status"] == "written"

    landed = lake / report["landing"]["raw_key"]
    assert landed.read_bytes() == raw


def test_local_import_retry_reuses_checksum_identity(tmp_path):
    payload = tmp_path / "world-events.json"
    payload.write_bytes(_world_response())
    lake = tmp_path / "lake"

    first = _run_import(payload, lake)
    second = _run_import(payload, lake)

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    first_report = json.loads(first.stdout)
    second_report = json.loads(second.stdout)
    assert second_report["landing"]["status"] == "existing"
    assert second_report["landing"]["event_id"] == first_report["landing"]["event_id"]
    assert second_report["landing"]["raw_sha256"] == first_report["landing"]["raw_sha256"]


def test_local_import_rejects_invalid_json_before_landing(tmp_path):
    payload = tmp_path / "invalid.json"
    payload.write_bytes(b"{not-json")
    lake = tmp_path / "lake"

    result = _run_import(payload, lake)

    assert result.returncode == 2
    assert "invalid JSON" in result.stderr
    assert not lake.exists() or not any(lake.rglob("*"))
