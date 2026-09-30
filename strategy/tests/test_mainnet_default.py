"""Real-money trading must be opt-in: unset BINANCE_TH_USE_TESTNET means safety mode."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

STRATEGY_ROOT = Path(__file__).resolve().parents[1]
MODULES = ["app.real_grid_bot", "app.dca_bot", "app.trend_bot"]


def _mainnet_flag(module: str, env_value):
    env = {k: v for k, v in os.environ.items() if k != "BINANCE_TH_USE_TESTNET"}
    if env_value is not None:
        env["BINANCE_TH_USE_TESTNET"] = env_value
    out = subprocess.run(
        [sys.executable, "-c", f"import {module} as m; print(m.BINANCE_TH_MAINNET)"],
        cwd=STRATEGY_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    return out.stdout.strip().splitlines()[-1]


@pytest.mark.parametrize("module", MODULES)
@pytest.mark.parametrize(
    ("env_value", "expected"),
    [(None, "False"), ("true", "False"), ("", "False"), ("maybe", "False"), ("false", "True"), (" FALSE ", "True")],
)
def test_mainnet_requires_explicit_opt_in(module, env_value, expected):
    assert _mainnet_flag(module, env_value) == expected
