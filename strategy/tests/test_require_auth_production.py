"""require_auth fails closed when AUTH_TOKEN is unset in production.

Dev mode (no AUTH_TOKEN, no ENVIRONMENT=production) keeps allowing every
caller so local development stays frictionless.
"""

import pytest
from starlette.requests import Request

import infrastructure.api.app as api_module


def _request(auth: str | None = None) -> Request:
    headers = [(b"authorization", auth.encode())] if auth else []
    return Request({"type": "http", "method": "GET", "path": "/", "headers": headers})


def test_dev_mode_without_token_allows(monkeypatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setattr(api_module, "API_TOKEN", None)
    assert api_module.require_auth(_request()) is True


@pytest.mark.parametrize("env", ["production", "PRODUCTION", "prod", " production "])
def test_production_without_token_fails_closed(monkeypatch, env):
    monkeypatch.setenv("ENVIRONMENT", env)
    monkeypatch.setattr(api_module, "API_TOKEN", "")
    assert api_module.require_auth(_request()) is False
    assert api_module.require_auth(_request("Bearer anything")) is False


def test_production_with_token_requires_match(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setattr(api_module, "API_TOKEN", "secret-test-token")
    assert api_module.require_auth(_request("Bearer secret-test-token")) is True
    assert api_module.require_auth(_request("Bearer wrong")) is False
    assert api_module.require_auth(_request()) is False


def test_non_production_environment_keeps_dev_mode(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setattr(api_module, "API_TOKEN", None)
    assert api_module.require_auth(_request()) is True
