from __future__ import annotations

from datetime import datetime
from pathlib import Path


def notes_path(notes_dir: Path, day: str) -> Path:
    return notes_dir / f"{day}.md"


def append_note(notes_dir: Path, day: str, text: str) -> Path:
    path = notes_path(notes_dir, day)
    timestamp = datetime.now().isoformat(timespec="minutes")
    with path.open("a", encoding="utf-8") as file:
        file.write(f"- [{timestamp}] {text.strip()}\n")
    return path


def read_notes(notes_dir: Path, day: str) -> str:
    path = notes_path(notes_dir, day)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")
