#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from humungousaur.config import AgentConfig
from humungousaur.connectors import ConnectorRuntime
from humungousaur.connectors.registry import DEFAULT_CONNECTOR_REGISTRY


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp_dir:
        config = AgentConfig(workspace=Path(tmp_dir), data_dir=Path(tmp_dir) / "artifacts").normalized()
        runtime = ConnectorRuntime(config)
        results = []
        for provider in DEFAULT_CONNECTOR_REGISTRY.providers():
            record = provider.to_record()
            failures: list[str] = []
            if not record.get("provider_id"):
                failures.append("missing provider id")
            if not record.get("display_name"):
                failures.append("missing display name")
            if not record.get("auth_type"):
                failures.append("missing auth type")
            if "credential_fields" not in record:
                failures.append("missing credential fields")
            if not record.get("icon"):
                failures.append("missing fallback icon")
            if not str(record.get("brand_color", "")).startswith("#"):
                failures.append("missing brand color")
            logo_asset = str(record.get("logo_asset") or "")
            if logo_asset and not _asset_exists(logo_asset):
                failures.append(f"missing bundled logo asset: {logo_asset}")

            configured = False
            connected = False
            auth_prepare = "not_applicable"
            if provider.auth_type == "oauth2_authorization_code":
                try:
                    runtime.prepare_authorization(provider.provider_id)
                    failures.append("oauth authorization unexpectedly prepared without client id")
                except ValueError as exc:
                    if "managed OAuth is not configured" not in str(exc):
                        failures.append(f"unexpected oauth missing-client error: {exc}")
                runtime.configure_client(provider.provider_id, client_id=f"{provider.provider_id}-client")
                prepared = runtime.prepare_authorization(provider.provider_id)
                if not str(prepared.get("authorization_url", "")).startswith(provider.auth_url):
                    failures.append("oauth authorization url did not use provider auth url")
                auth_prepare = "prepared_with_dummy_client"
            else:
                fields = tuple(record.get("credential_fields") or ())
                secret = "dummy-secret" if len(fields) > 1 else ""
                runtime.configure_client(provider.provider_id, client_id=f"{provider.provider_id}-profile", client_secret=secret)
                try:
                    runtime.prepare_authorization(provider.provider_id)
                    failures.append("non-oauth connector unexpectedly prepared oauth authorization")
                except ValueError:
                    pass

            status = runtime.status(provider_id=provider.provider_id)["connectors"][0]
            configured = bool(status["configured"])
            connected = bool(status["connected"])
            serialized_status = json.dumps(status, sort_keys=True)
            if "dummy-secret" in serialized_status:
                failures.append("secret leaked in public status")
            if provider.auth_type != "oauth2_authorization_code" and not connected:
                failures.append("non-oauth connector did not become connection-ready after dummy setup")
            if provider.auth_type == "oauth2_authorization_code" and connected:
                failures.append("oauth connector reported connected before token exchange")
            disconnected = runtime.disconnect(provider.provider_id)
            if provider.auth_type != "oauth2_authorization_code" and not disconnected.get("removed"):
                failures.append("non-oauth disconnect did not remove credential profile")

            results.append(
                {
                    "provider_id": provider.provider_id,
                    "display_name": provider.display_name,
                    "auth_type": provider.auth_type,
                    "configured": configured,
                    "connected": connected,
                    "auth_prepare": auth_prepare,
                    "logo_asset": logo_asset,
                    "status": "passed" if not failures else "failed",
                    "failures": failures,
                }
            )

    failed = [item for item in results if item["status"] != "passed"]
    print(json.dumps({"provider_count": len(results), "failed_count": len(failed), "results": results}, indent=2))
    return 1 if failed else 0


def _asset_exists(asset: str) -> bool:
    return (
        (ROOT / "apps" / "macos" / "Sources" / "Resources" / "ConnectorLogos" / asset).exists()
        and (ROOT / "apps" / "windows" / "Humungousaur.App" / "Assets" / "ConnectorLogos" / asset).exists()
    )


if __name__ == "__main__":
    raise SystemExit(main())
