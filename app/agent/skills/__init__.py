from pathlib import Path
from typing import List

SKILLS_DIR = Path(__file__).parent
SKILL_EXTENSIONS = [".txt", ".md"]


def _normalize_skill_name(skill_name: str) -> str:
    normalized = skill_name.strip()
    if not normalized:
        raise ValueError("skill_name cannot be empty")

    skill_path = Path(normalized)
    if skill_path.suffix:
        return normalized
    return f"{normalized}.txt"


def list_skills() -> List[str]:
    return sorted(
        [path.stem for path in SKILLS_DIR.iterdir() if path.is_file() and path.suffix in SKILL_EXTENSIONS]
    )


def load_skill(skill_name: str) -> str:
    normalized_name = _normalize_skill_name(skill_name)
    candidate = SKILLS_DIR / normalized_name

    if candidate.exists() and candidate.is_file():
        return candidate.read_text(encoding="utf-8").strip()

    # Try any supported extension if the skill name was provided without one.
    for extension in SKILL_EXTENSIONS:
        alt = SKILLS_DIR / f"{Path(skill_name).stem}{extension}"
        if alt.exists() and alt.is_file():
            return alt.read_text(encoding="utf-8").strip()

    available = ", ".join(list_skills()) or "(none)"
    raise FileNotFoundError(
        f"Skill '{skill_name}' not found in {SKILLS_DIR}. Available skills: {available}"
    )
