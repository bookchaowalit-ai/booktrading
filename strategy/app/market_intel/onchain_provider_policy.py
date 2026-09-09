"""Read-only S3-compatible policy and secret-binding checks.

The checker never writes, deletes, or prints credential values. Provider
policy calls are opt-in at the CLI boundary and can be exercised with an
injected fake client in tests.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse

PUBLIC_ACCESS_BLOCK_FLAGS = (
    "BlockPublicAcls",
    "IgnorePublicAcls",
    "BlockPublicPolicy",
    "RestrictPublicBuckets",
)
REQUIRED_PREFIXES = ("landing/", "bronze/", "bronze_compacted/", "control/")


class ProviderPolicyError(RuntimeError):
    """Raised when a provider policy check cannot be constructed safely."""


def secret_binding_report(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Report credential-source names without reading or returning values."""

    source = os.environ if env is None else env
    families = {
        "static_keys": ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"),
        "web_identity": ("AWS_ROLE_ARN", "AWS_WEB_IDENTITY_TOKEN_FILE"),
        "container_role": (
            "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
            "AWS_CONTAINER_CREDENTIALS_FULL_URI",
        ),
        "profile": ("AWS_PROFILE",),
    }
    sources: dict[str, dict[str, Any]] = {}
    for family, names in families.items():
        present = [name for name in names if str(source.get(name) or "").strip()]
        sources[family] = {
            "configured": len(present) == len(names),
            "present_names": present,
        }
    configured = any(item["configured"] for item in sources.values())
    return {
        "status": "configured" if configured else "unverified",
        "configured": configured,
        "sources": sources,
        "values_read": False,
        "credential_values_returned": False,
        "provider": "boto3_standard_chain",
    }


def verify_s3_bucket_policy(client: Any, bucket: str) -> dict[str, Any]:
    """Verify required bucket controls using read-only S3 control-plane calls."""

    if not bucket or "/" in bucket:
        raise ProviderPolicyError("bucket must be a plain bucket name")
    checks = {
        "versioning": _check_versioning(client, bucket),
        "encryption": _check_encryption(client, bucket),
        "public_access_block": _check_public_access_block(client, bucket),
        "ownership": _check_ownership(client, bucket),
        "lifecycle": _check_lifecycle(client, bucket),
        "policy_public_status": _check_policy_public_status(client, bucket),
    }
    passed = all(bool(check.get("ok")) for check in checks.values())
    return {
        "status": "pass" if passed else "fail",
        "bucket": bucket,
        "checks": checks,
        "read_only": True,
        "object_storage_writes": False,
        "deletes": False,
    }


def client_for_s3_uri(uri: str) -> tuple[Any, str]:
    """Create a boto3 S3 client and return its redaction-safe bucket name."""

    parsed = urlparse(uri)
    if parsed.scheme != "s3" or not parsed.netloc:
        raise ProviderPolicyError("provider policy checks require an s3:// URI")
    if parsed.username or parsed.password:
        raise ProviderPolicyError("S3 URI must not include credentials")
    try:
        import boto3
    except ImportError as exc:  # pragma: no cover - deployment dependency
        raise ProviderPolicyError("provider policy checks require boto3") from exc
    endpoint = os.getenv("SOLANA_DEGEN_S3_ENDPOINT") or os.getenv("DATA_LAKE_S3_ENDPOINT")
    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
    if not region and endpoint:
        region = "auto"
    kwargs: dict[str, Any] = {}
    if endpoint:
        kwargs["endpoint_url"] = endpoint
    if region:
        kwargs["region_name"] = region
    return boto3.client("s3", **kwargs), parsed.netloc


def _check_versioning(client: Any, bucket: str) -> dict[str, Any]:
    response = _call(client, "get_bucket_versioning", Bucket=bucket)
    if response["error"]:
        return response
    status = response["response"].get("Status")
    return {"ok": status == "Enabled", "status": status or "Disabled"}


def _check_encryption(client: Any, bucket: str) -> dict[str, Any]:
    response = _call(client, "get_bucket_encryption", Bucket=bucket)
    if response["error"]:
        return response
    config = response["response"].get("ServerSideEncryptionConfiguration") or {}
    rules = config.get("Rules") if isinstance(config, dict) else None
    algorithms: list[str] = []
    for rule in rules or []:
        if not isinstance(rule, dict):
            continue
        default = rule.get("ApplyServerSideEncryptionByDefault") or {}
        if isinstance(default, dict) and default.get("SSEAlgorithm"):
            algorithms.append(str(default["SSEAlgorithm"]))
    return {"ok": bool(algorithms), "algorithms": sorted(set(algorithms))}


def _check_public_access_block(client: Any, bucket: str) -> dict[str, Any]:
    response = _call(client, "get_public_access_block", Bucket=bucket)
    if response["error"]:
        return response
    config = response["response"].get("PublicAccessBlockConfiguration") or {}
    flags = {name: bool(config.get(name)) for name in PUBLIC_ACCESS_BLOCK_FLAGS}
    return {"ok": all(flags.values()), "flags": flags}


def _check_ownership(client: Any, bucket: str) -> dict[str, Any]:
    response = _call(client, "get_bucket_ownership_controls", Bucket=bucket)
    if response["error"]:
        return response
    rules = response["response"].get("OwnershipControls", {}).get("Rules", [])
    values = [str(rule.get("ObjectOwnership")) for rule in rules if isinstance(rule, dict)]
    return {"ok": "BucketOwnerEnforced" in values, "object_ownership": values}


def _check_lifecycle(client: Any, bucket: str) -> dict[str, Any]:
    response = _call(client, "get_bucket_lifecycle_configuration", Bucket=bucket)
    if response["error"]:
        return response
    rules = response["response"].get("Rules") or []
    enabled_rules = [rule for rule in rules if isinstance(rule, dict) and rule.get("Status") == "Enabled"]
    covered = {prefix: any(_rule_covers_prefix(rule, prefix) for rule in enabled_rules) for prefix in REQUIRED_PREFIXES}
    return {
        "ok": bool(enabled_rules) and all(covered.values()),
        "enabled_rules": len(enabled_rules),
        "covered": covered,
    }


def _check_policy_public_status(client: Any, bucket: str) -> dict[str, Any]:
    response = _call(client, "get_bucket_policy_status", Bucket=bucket)
    if response["error"]:
        if response.get("code") in {"NoSuchBucketPolicy", "NoSuchPolicy", "404"}:
            return {"ok": False, "status": "unknown", "reason": "bucket_policy_status_unavailable"}
        return response
    status = response["response"].get("PolicyStatus") or {}
    is_public = status.get("IsPublic")
    return {"ok": is_public is False, "is_public": is_public}


def _rule_covers_prefix(rule: dict[str, Any], required_prefix: str) -> bool:
    rule_filter = rule.get("Filter")
    if not rule_filter:
        return True
    if not isinstance(rule_filter, dict):
        return False
    prefix = rule_filter.get("Prefix")
    return prefix in (None, "") or str(prefix).startswith(required_prefix) or required_prefix.startswith(str(prefix))


def _call(client: Any, method: str, **kwargs: Any) -> dict[str, Any]:
    try:
        response = getattr(client, method)(**kwargs)
    except Exception as exc:  # provider SDK error is intentionally redacted
        return {
            "ok": False,
            "error": True,
            "status": "error",
            "code": _error_code(exc),
            "provider_message_exposed": False,
        }
    return {"error": False, "response": response}


def _error_code(exc: Exception) -> str:
    response = getattr(exc, "response", {})
    if isinstance(response, dict):
        error = response.get("Error")
        if isinstance(error, dict) and error.get("Code"):
            return str(error["Code"])
        metadata = response.get("ResponseMetadata")
        if isinstance(metadata, dict) and metadata.get("HTTPStatusCode"):
            return str(metadata["HTTPStatusCode"])
    return type(exc).__name__
