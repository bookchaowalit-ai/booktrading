"""Polymarket epoch dates must be UTC and tz-aware, like its ISO dates."""

import os
import time
from datetime import UTC, datetime

import pytest

from app.polymarket.client import PolymarketClient


@pytest.fixture
def bangkok_host():
    if not hasattr(time, "tzset"):
        pytest.skip("needs time.tzset")
    old = os.environ.get("TZ")
    os.environ["TZ"] = "Asia/Bangkok"  # UTC+7, no DST
    time.tzset()
    yield
    if old is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = old
    time.tzset()


def test_epoch_and_iso_dates_agree(bangkok_host):
    client = PolymarketClient()
    from_epoch = client._parse_date(1_700_000_000)
    from_iso = client._parse_date("2023-11-14T22:13:20Z")
    assert from_epoch == datetime(2023, 11, 14, 22, 13, 20, tzinfo=UTC)
    assert from_epoch == from_iso
    # Mixed naive/aware values raised TypeError when compared.
    assert (from_epoch < from_iso) is False
