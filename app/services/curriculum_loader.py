"""
curriculum_loader.py

Service responsible for loading and querying the interview curriculum
from a local curriculum.json file.

This module contains no LLM or API logic — it is a pure data-access
layer used by app/interview/* and app/services/interview_service.py
to drive question generation based on structured curriculum data.

Expected curriculum.json structure:
{
    "days": {
        "1": {
            "title": "Python Fundamentals",
            "topics": ["Data Types", "Loops", "Functions"],
            "learning_objectives": ["Understand mutability", "Write clean functions"],
            "tools": ["Python", "VS Code"]
        },
        "2": {
            "title": "Data Structures",
            "topics": ["Lists", "Dictionaries", "Sets"],
            "learning_objectives": ["Choose the right data structure"],
            "tools": ["Python"]
        }
    }
}
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Union

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

DEFAULT_CURRICULUM_PATH = Path("data/curriculum.json")


class CurriculumLoaderError(Exception):
    """Raised when the curriculum file cannot be loaded or parsed."""
    pass


class CurriculumLoader:
    """
    Loads and provides structured access to the interview curriculum
    defined in curriculum.json.
    """

    def __init__(self, curriculum_path: Union[str, Path] = DEFAULT_CURRICULUM_PATH):
        """
        Initialize the CurriculumLoader.

        Args:
            curriculum_path: Path to the curriculum.json file.
        """
        self.curriculum_path = Path(curriculum_path)
        self._curriculum: Dict[str, Any] = {}
        self.load_curriculum()

    # ------------------------------------------------------------------
    # Core loading
    # ------------------------------------------------------------------

    def load_curriculum(self) -> Dict[str, Any]:
        """
        Load the curriculum data from the JSON file into memory.

        Returns:
            The full curriculum dictionary.

        Raises:
            CurriculumLoaderError: If the file is missing, unreadable,
                or contains invalid JSON.
        """
        if not self.curriculum_path.exists():
            raise CurriculumLoaderError(
                f"Curriculum file not found at: {self.curriculum_path}"
            )

        try:
            with open(self.curriculum_path, "r", encoding="utf-8") as file:
                self._curriculum = json.load(file)
            logger.info("Curriculum loaded from: %s", self.curriculum_path)
            return self._curriculum

        except json.JSONDecodeError as exc:
            logger.exception("Invalid JSON in curriculum file.")
            raise CurriculumLoaderError(
                f"Failed to parse curriculum JSON: {exc}"
            ) from exc

        except OSError as exc:
            logger.exception("Failed to read curriculum file.")
            raise CurriculumLoaderError(
                f"Failed to read curriculum file: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_day_data(self, day: Union[str, int]) -> Dict[str, Any]:
        """
        Retrieve the raw data dictionary for a specific curriculum day.

        Args:
            day: Day identifier (e.g., 1 or "1").

        Returns:
            The dictionary of data for the requested day, or an empty
            dictionary if the day does not exist.
        """
        days = self._curriculum.get("days", {})
        return days.get(str(day), {})

    # ------------------------------------------------------------------
    # Public accessors
    # ------------------------------------------------------------------

    def get_all_days(self) -> List[Dict[str, Any]]:
        """
        Get a summary of all curriculum days.

        Returns:
            A list of dictionaries, each containing 'day' and 'title'
            for every day defined in the curriculum.
        """
        days = self._curriculum.get("days", {})
        return [
            {"day": day_id, "title": day_data.get("title", "")}
            for day_id, day_data in days.items()
        ]

    def get_topics(self, day: Union[str, int]) -> List[str]:
        """
        Get the list of topics for a specific curriculum day.

        Args:
            day: Day identifier (e.g., 1 or "1").

        Returns:
            A list of topic strings. Empty list if the day is not found.
        """
        return self._get_day_data(day).get("topics", [])

    def get_learning_objectives(self, day: Union[str, int]) -> List[str]:
        """
        Get the learning objectives for a specific curriculum day.

        Args:
            day: Day identifier (e.g., 1 or "1").

        Returns:
            A list of learning objective strings. Empty list if the day
            is not found.
        """
        return self._get_day_data(day).get("learning_objectives", [])

    def get_tools(self, day: Union[str, int]) -> List[str]:
        """
        Get the list of tools/technologies relevant to a specific
        curriculum day.

        Args:
            day: Day identifier (e.g., 1 or "1").

        Returns:
            A list of tool strings. Empty list if the day is not found.
        """
        return self._get_day_data(day).get("tools", [])

    def get_completed_topics(self, candidate: Dict[str, Any]) -> List[str]:
        """
        Get the list of topics a candidate has already completed.

        Args:
            candidate: A candidate profile dictionary expected to contain
                a "completed_topics" key, e.g.:
                {"id": "c001", "name": "Jane Doe", "completed_topics": [...]}

        Returns:
            A list of completed topic strings. Empty list if none found.
        """
        return candidate.get("completed_topics", [])