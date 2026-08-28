from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from app.config import Settings

PROFILE_READY_MARKER = ".codex-linkedin-ready"


def has_persistent_user_data_dir(settings: Settings) -> bool:
    path: Path = settings.linkedin_user_data_dir
    return (path / PROFILE_READY_MARKER).exists()


def load_storage_state(settings: Settings) -> str | dict[str, Any] | None:
    if settings.linkedin_storage_state_b64:
        decoded = base64.b64decode(settings.linkedin_storage_state_b64).decode("utf-8")
        return json.loads(decoded)

    path = settings.linkedin_storage_state_path
    if path.exists():
        return str(path)
    return None


async def save_storage_state(context: Any, settings: Settings) -> None:
    if settings.linkedin_storage_state_b64:
        return
    path: Path = settings.linkedin_storage_state_path
    path.parent.mkdir(parents=True, exist_ok=True)
    await context.storage_state(path=str(path))
