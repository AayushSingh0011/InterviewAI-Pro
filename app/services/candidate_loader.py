"""
candidate_loader.py

Service responsible for loading and querying candidate data from a local
candidates.json file.

This module contains no LLM, API, or UI logic — it is a pure data-access
layer used by app/interview/* and app/services/interview_service.py
to retrieve candidate profiles and progress used to drive the interview flow.

Expected candidates.json structure:
{
    "candidates": {
        "c001": {
            "name": "Jane Doe",
            "role": "Backend Developer",
            "completed_topics": ["Loops", "Functions"],
            "skipped_topics": ["Decorators"],
            "attempts": [
                {"day": "1", "question": "...", "score": 8}
            ],
            "progress": {
                "current_day": "2",
                "percent_complete": 40
            }
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

DEFAULT_CANDIDATES_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "candidates.json"


# ---------------------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------------------

class CandidateError(Exception):
    """Base exception for all candidate-related errors."""
    pass


class CandidateFileNotFoundError(CandidateError):
    """Raised when the candidates.json file does not exist at the given path."""
    pass


class CandidateParseError(CandidateError):
    """Raised when the candidates.json file contains invalid JSON."""
    pass


class CandidateValidationError(CandidateError):
    """Raised when the candidate data does not match the expected structure."""
    pass


class CandidateNotFoundError(CandidateError):
    """Raised when a requested candidate ID does not exist."""
    pass


# ---------------------------------------------------------------------------
# CandidateLoader
# ---------------------------------------------------------------------------

class CandidateLoader:
    """
    Loads and provides structured, read-only access to candidate data
    defined in candidates.json.

    The candidate data is loaded automatically upon instantiation.
    """

    def __init__(self, candidates_path: Union[str, Path] = DEFAULT_CANDIDATES_PATH):
        """
        Initialize the CandidateLoader and load candidate data immediately.

        Args:
            candidates_path: Path to the candidates.json file. Defaults to
                '<project_root>/data/candidates.json'.

        Raises:
            CandidateFileNotFoundError: If the candidates file does not exist.
            CandidateParseError: If the candidates file contains invalid JSON.
            CandidateValidationError: If the candidate data is malformed.
        """
        self.candidates_path: Path = Path(candidates_path)
        self._candidates: Dict[str, Any] = {}
        self.load_candidates()

    # ------------------------------------------------------------------
    # Core loading
    # ------------------------------------------------------------------

    def load_candidates(self) -> Dict[str, Any]:
        """
        Load and validate candidate data from the JSON file into memory.

        Returns:
            The full candidates dictionary.

        Raises:
            CandidateFileNotFoundError: If the candidates file does not exist.
            CandidateParseError: If the file contains invalid JSON.
            CandidateValidationError: If the parsed data is not structured
                as expected (missing or invalid 'candidates' key).
        """
        if not self.candidates_path.exists():
            raise CandidateFileNotFoundError(
                f"Candidates file not found at: {self.candidates_path}"
            )

        try:
            with self.candidates_path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except json.JSONDecodeError as exc:
            logger.exception("Invalid JSON in candidates file.")
            raise CandidateParseError(
                f"Failed to parse candidates JSON: {exc}"
            ) from exc
        except OSError as exc:
            logger.exception("Failed to read candidates file.")
            raise CandidateError(
                f"Failed to read candidates file: {exc}"
            ) from exc

        if not isinstance(data, dict) or "candidates" not in data or not isinstance(data["candidates"], dict):
            raise CandidateValidationError(
                "Candidates JSON must be an object containing a 'candidates' object."
            )

        self._candidates = data
        logger.info("Candidates loaded successfully from: %s", self.candidates_path)
        return self._candidates

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_candidate_data(self, candidate_id: str) -> Dict[str, Any]:
        """
        Retrieve the raw data dictionary for a specific candidate.

        Args:
            candidate_id: Unique identifier of the candidate.

        Returns:
            The dictionary of data for the requested candidate.

        Raises:
            CandidateNotFoundError: If the candidate ID does not exist.
        """
        candidates = self._candidates.get("candidates", {})
        candidate_data = candidates.get(str(candidate_id))

        if candidate_data is None:
            raise CandidateNotFoundError(
                f"Candidate '{candidate_id}' was not found."
            )

        return candidate_data

    # ------------------------------------------------------------------
    # Public accessors
    # ------------------------------------------------------------------

    def get_candidate(self, candidate_id: str) -> Dict[str, Any]:
        """
        Get the complete profile data for a specific candidate.

        Args:
            candidate_id: Unique identifier of the candidate.

        Returns:
            A dictionary containing the candidate's full profile
            (name, role, completed_topics, skipped_topics, attempts, progress).

        Raises:
            CandidateNotFoundError: If the candidate ID does not exist.
        """
        return self._get_candidate_data(candidate_id)

    def get_completed_topics(self, candidate_id: str) -> List[str]:
        """
        Get the list of topics a candidate has completed.

        Args:
            candidate_id: Unique identifier of the candidate.

        Returns:
            A list of completed topic strings.

        Raises:
            CandidateNotFoundError: If the candidate ID does not exist.
        """
        return self._get_candidate_data(candidate_id).get("completed_topics", [])

    def get_skipped_topics(self, candidate_id: str) -> List[str]:
        """
        Get the list of topics a candidate has skipped.

        Args:
            candidate_id: Unique identifier of the candidate.

        Returns:
            A list of skipped topic strings.

        Raises:
            CandidateNotFoundError: If the candidate ID does not exist.
        """
        return self._get_candidate_data(candidate_id).get("skipped_topics", [])

    def get_attempts(self, candidate_id: str) -> List[Dict[str, Any]]:
        """
        Get the list of interview attempts recorded for a candidate.

        Args:
            candidate_id: Unique identifier of the candidate.

        Returns:
            A list of attempt dictionaries (e.g., day, question, score).

        Raises:
            CandidateNotFoundError: If the candidate ID does not exist.
        """
        return self._get_candidate_data(candidate_id).get("attempts", [])

    def get_progress(self, candidate_id: str) -> Dict[str, Any]:
        """
        Get the current progress data for a candidate.

        Args:
            candidate_id: Unique identifier of the candidate.

        Returns:
            A dictionary describing the candidate's progress
            (e.g., current_day, percent_complete).

        Raises:
            CandidateNotFoundError: If the candidate ID does not exist.
        """
        return self._get_candidate_data(candidate_id).get("progress", {})