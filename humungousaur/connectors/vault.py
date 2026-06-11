from __future__ import annotations

import json
from pathlib import Path

from humungousaur.config import AgentConfig


class ConnectorVault:
    def set_secret(self, secret_ref: str, value: str) -> str:
        raise NotImplementedError

    def get_secret(self, secret_ref: str) -> str | None:
        raise NotImplementedError

    def delete_secret(self, secret_ref: str) -> None:
        raise NotImplementedError


class LocalFileConnectorVault(ConnectorVault):
    """Portable fallback vault.

    Desktop OS keychain backends can replace this class without changing tools,
    collectors, or provider adapters. The fallback keeps secrets out of public
    connector profile rows and uses 0600 permissions where supported.
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    @classmethod
    def for_config(cls, config: AgentConfig) -> "LocalFileConnectorVault":
        return cls(config.normalized().data_dir / "connectors" / "secrets.json")

    def set_secret(self, secret_ref: str, value: str) -> str:
        payload = self._read()
        payload[str(secret_ref)] = str(value or "")
        self._write(payload)
        return str(secret_ref)

    def get_secret(self, secret_ref: str) -> str | None:
        if not secret_ref:
            return None
        value = self._read().get(str(secret_ref))
        return str(value) if value else None

    def delete_secret(self, secret_ref: str) -> None:
        if not secret_ref:
            return
        payload = self._read()
        payload.pop(str(secret_ref), None)
        self._write(payload)

    def _read(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        if not isinstance(loaded, dict):
            return {}
        return {str(key): str(value) for key, value in loaded.items() if isinstance(value, str)}

    def _write(self, payload: dict[str, str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        try:
            self.path.chmod(0o600)
        except OSError:
            pass
