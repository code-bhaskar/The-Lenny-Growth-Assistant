from __future__ import annotations

from pathlib import Path

from app.core.config import SKILLS_DIR


SKILL_PATHS = {
    "grounded_qa": SKILLS_DIR / "grounded_qa" / "SKILL.md",
    "ship30": SKILLS_DIR / "ship30" / "SKILL.md",
    "artifacts": SKILLS_DIR / "artifacts" / "SKILL.md",
}


def load_skill_text(name: str) -> str:
    path = SKILL_PATHS[name]
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def load_all_skills() -> str:
    parts = []
    for name in ("grounded_qa", "ship30", "artifacts"):
        text = load_skill_text(name).strip()
        if text:
            parts.append(f"## {name}\n{text}")
    return "\n\n".join(parts)
