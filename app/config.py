from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from app.runtime import get_project_dir, get_static_dir


@dataclass(frozen=True)
class Settings:
    project_dir: Path
    workspace_dir: Path
    data_dir: Path
    uploads_dir: Path
    static_dir: Path
    db_path: Path
    dds_dir: Path
    rdi_dir: Path
    pm_dir: Path
    mie_dir: Path
    anthropic_api_key: str | None
    anthropic_model: str
    openai_api_key: str | None
    openai_model: str
    google_api_key: str | None
    google_model: str
    xai_api_key: str | None
    xai_model: str
    default_provider: str
    host: str
    port: int
    excluded_tokens: tuple[str, ...]


def _path_setting(name: str, default: Path, base_dir: Path) -> Path:
    raw_value = os.getenv(name)
    if not raw_value:
        return default

    candidate = Path(raw_value)
    if candidate.is_absolute():
        return candidate
    return (base_dir / candidate).resolve()


def get_settings() -> Settings:
    project_dir = get_project_dir()
    load_dotenv(project_dir / ".env", override=False)
    workspace_dir = _path_setting("MCM5_WORKSPACE_DIR", project_dir.parent, project_dir)
    data_dir = project_dir / "data"
    uploads_dir = data_dir / "uploads"
    static_dir = get_static_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    uploads_dir.mkdir(parents=True, exist_ok=True)

    return Settings(
        project_dir=project_dir,
        workspace_dir=workspace_dir,
        data_dir=data_dir,
        uploads_dir=uploads_dir,
        static_dir=static_dir,
        db_path=_path_setting("MCM5_DB_PATH", data_dir / "mcm5.sqlite3", project_dir),
        dds_dir=_path_setting("MCM5_DDS_DIR", workspace_dir / "dds", project_dir),
        rdi_dir=_path_setting("MCM5_RDI_DIR", workspace_dir / "14 RDIs", project_dir),
        pm_dir=_path_setting("MCM5_PM_DIR", workspace_dir / "3 BDE (PM card's)", project_dir),
        mie_dir=_path_setting("MCM5_MIE_DIR", workspace_dir / "mid-range", project_dir),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-latest"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        google_api_key=os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"),
        google_model=os.getenv("GOOGLE_MODEL", "gemini-2.5-flash"),
        xai_api_key=os.getenv("XAI_API_KEY"),
        xai_model=os.getenv("XAI_MODEL", "grok-4.20-beta-latest-non-reasoning"),
        default_provider=os.getenv("LLM_PROVIDER", "auto").lower(),
        host=os.getenv("MCM5_HOST", "0.0.0.0"),
        port=int(os.getenv("MCM5_PORT", "8080")),
        excluded_tokens=("obsolet", "copia de", "plantilla", "~$"),
    )
