"""Local configuration loading for the Legal Corpus Compiler."""

from __future__ import annotations

import os
from pathlib import Path


def load_local_env(root: Path | None = None) -> Path | None:
    """Load an ignored local `.env` file without overriding environment values."""

    search_root = (root or Path.cwd()).resolve()
    candidates = [search_root / ".env"]
    for parent in search_root.parents:
        candidates.append(parent / ".env")
    for path in candidates:
        if not path.is_file():
            continue
        for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if not key or key in os.environ:
                continue
            os.environ[key] = value.strip().strip('"').strip("'")
        return path
    return None
