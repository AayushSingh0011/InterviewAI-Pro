import json
from pathlib import Path


# Project root:
# interview-agent/
PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"

CANDIDATES_FILE = DATA_DIR / "candidates.json"
CURRICULUM_FILE = DATA_DIR / "curriculum.json"


def load_json_file(file_path: Path):
    """Load and return JSON data from a file."""

    if not file_path.exists():
        raise FileNotFoundError(
            f"Data file not found: {file_path}"
        )

    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)


def load_candidates():
    """Load all candidate profiles."""

    return load_json_file(CANDIDATES_FILE)


def load_curriculum():
    """Load the complete cohort curriculum."""

    return load_json_file(CURRICULUM_FILE)


def get_candidate(candidate_id: str):
    """Find a candidate by ID."""

    candidates = load_candidates()

    # Handle either:
    # {"candidates": [...]}
    # or directly [...]
    if isinstance(candidates, dict):
        candidates = candidates.get("candidates", [])

    for candidate in candidates:
        if str(candidate.get("id")) == str(candidate_id):
            return candidate

    return None