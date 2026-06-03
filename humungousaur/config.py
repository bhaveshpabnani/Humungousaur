from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class AgentConfig:
    workspace: Path = Path.cwd()
    data_dir: Path = Path("artifacts")
    max_file_bytes: int = 200_000
    max_search_results: int = 50
    dry_run: bool = False
    planner_provider: str = "model"
    model_provider: str = "auto"
    model_name: str = "gpt-5-mini"
    model_base_url: str | None = None
    model_api_key_env: str | None = None
    model_timeout_seconds: float = 45.0
    allowed_read_roots: tuple[Path, ...] = field(default_factory=tuple)
    allowed_write_roots: tuple[Path, ...] = field(default_factory=tuple)

    def normalized(self) -> "AgentConfig":
        workspace = self.workspace.expanduser().resolve()
        data_dir = (workspace / self.data_dir).resolve() if not self.data_dir.is_absolute() else self.data_dir.resolve()
        read_roots = self.allowed_read_roots or (workspace,)
        write_roots = self.allowed_write_roots or (data_dir,)
        return AgentConfig(
            workspace=workspace,
            data_dir=data_dir,
            max_file_bytes=self.max_file_bytes,
            max_search_results=self.max_search_results,
            dry_run=self.dry_run,
            planner_provider=self.planner_provider,
            model_provider=self.model_provider,
            model_name=self.model_name,
            model_base_url=self.model_base_url,
            model_api_key_env=self.model_api_key_env,
            model_timeout_seconds=self.model_timeout_seconds,
            allowed_read_roots=tuple(path.expanduser().resolve() for path in read_roots),
            allowed_write_roots=tuple(path.expanduser().resolve() for path in write_roots),
        )

    @property
    def notes_dir(self) -> Path:
        return self.data_dir / "notes"

    @property
    def audit_db_path(self) -> Path:
        return self.data_dir / "audit.sqlite3"

    @property
    def memory_db_path(self) -> Path:
        return self.data_dir / "memory.sqlite3"

    @property
    def approvals_db_path(self) -> Path:
        return self.data_dir / "approvals.sqlite3"

    @property
    def permission_settings_path(self) -> Path:
        return self.data_dir / "permissions.json"

    @property
    def file_index_db_path(self) -> Path:
        return self.data_dir / "file_index.sqlite3"

    @property
    def browser_sessions_db_path(self) -> Path:
        return self.data_dir / "browser_sessions.sqlite3"

    @property
    def cognition_db_path(self) -> Path:
        return self.data_dir / "cognition.sqlite3"

    @property
    def persona_path(self) -> Path:
        return self.data_dir / "persona.json"

    @property
    def skill_library_path(self) -> Path:
        return self.data_dir / "skills.json"

    @property
    def specialist_registry_path(self) -> Path:
        return self.data_dir / "specialists.json"
