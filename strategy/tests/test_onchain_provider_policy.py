from __future__ import annotations

import json

import pytest

from app.market_intel.onchain_provider_policy import (
    ProviderPolicyError,
    secret_binding_report,
    verify_s3_bucket_policy,
)


class FakePolicyClient:
    def __init__(self, *, public: bool = False):
        self.public = public

    def get_bucket_versioning(self, **_kwargs):
        return {"Status": "Enabled"}

    def get_bucket_encryption(self, **_kwargs):
        return {
            "ServerSideEncryptionConfiguration": {
                "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
            }
        }

    def get_public_access_block(self, **_kwargs):
        return {
            "PublicAccessBlockConfiguration": {
                name: True
                for name in (
                    "BlockPublicAcls",
                    "IgnorePublicAcls",
                    "BlockPublicPolicy",
                    "RestrictPublicBuckets",
                )
            }
        }

    def get_bucket_ownership_controls(self, **_kwargs):
        return {"OwnershipControls": {"Rules": [{"ObjectOwnership": "BucketOwnerEnforced"}]}}

    def get_bucket_lifecycle_configuration(self, **_kwargs):
        return {"Rules": [{"ID": "market-data-retention", "Status": "Enabled"}]}

    def get_bucket_policy_status(self, **_kwargs):
        return {"PolicyStatus": {"IsPublic": self.public}}


def test_provider_policy_passes_required_read_only_controls():
    report = verify_s3_bucket_policy(FakePolicyClient(), "booktrading-onchain")

    assert report["status"] == "pass"
    assert report["read_only"] is True
    assert report["object_storage_writes"] is False
    assert report["checks"]["lifecycle"]["ok"] is True


def test_provider_policy_blocks_public_bucket():
    report = verify_s3_bucket_policy(FakePolicyClient(public=True), "booktrading-onchain")

    assert report["status"] == "fail"
    assert report["checks"]["policy_public_status"]["ok"] is False


def test_secret_binding_reports_names_without_values():
    report = secret_binding_report(
        {
            "AWS_ROLE_ARN": "arn:aws:iam::123:role/booktrading",
            "AWS_WEB_IDENTITY_TOKEN_FILE": "/var/run/token",
        }
    )

    assert report["status"] == "configured"
    assert report["values_read"] is False
    assert report["credential_values_returned"] is False
    assert "arn:aws" not in json.dumps(report)


def test_secret_binding_does_not_claim_unconfigured_chain():
    report = secret_binding_report({})

    assert report["status"] == "unverified"
    assert report["configured"] is False


def test_provider_policy_rejects_non_bucket_and_uri_credentials():
    with pytest.raises(ProviderPolicyError):
        verify_s3_bucket_policy(FakePolicyClient(), "bucket/prefix")
