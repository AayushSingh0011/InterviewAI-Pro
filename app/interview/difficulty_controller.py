"""
difficulty_controller.py

Controls the adaptive difficulty of an interview session based on the
candidate's running performance.

This module contains no LLM, API, UI, or persistence logic — it is a pure
Python state-management layer that reads the running average score from
InterviewMemory and adjusts the current difficulty level accordingly.
"""

from typing import Any, List, Optional

# Difficulty levels, in ascending order.
DIFFICULTY_LEVELS: List[str] = ["Easy", "Medium", "Hard"]

DEFAULT_INITIAL_DIFFICULTY = "Easy"
DEFAULT_INCREASE_THRESHOLD = 7.0
DEFAULT_DECREASE_THRESHOLD = 4.0


class DifficultyControllerError(Exception):
    """Raised when an invalid difficulty level is used or configured."""
    pass


class DifficultyController:
    """
    Determines and tracks the current interview difficulty level based on
    the candidate's running average score, as reported by InterviewMemory.
    """

    def __init__(
        self,
        memory: Any,
        initial_difficulty: str = DEFAULT_INITIAL_DIFFICULTY,
        increase_threshold: float = DEFAULT_INCREASE_THRESHOLD,
        decrease_threshold: float = DEFAULT_DECREASE_THRESHOLD,
    ):
        """
        Initialize the DifficultyController.

        Args:
            memory: An instance of InterviewMemory
                (app/interview/memory.py), used to read the running
                average score via get_average_score().
            initial_difficulty: The difficulty level to start the
                interview at, and the level restored by reset(). Must be
                one of 'Easy', 'Medium', 'Hard'.
            increase_threshold: Minimum average score (on a 0-10 scale)
                required to trigger a difficulty increase.
            decrease_threshold: Maximum average score (on a 0-10 scale)
                that triggers a difficulty decrease.

        Raises:
            DifficultyControllerError: If initial_difficulty is not a
                recognized difficulty level.
        """
        self._validate_level(initial_difficulty)

        self.memory = memory
        self.initial_difficulty = initial_difficulty
        self.current_difficulty = initial_difficulty
        self.increase_threshold = increase_threshold
        self.decrease_threshold = decrease_threshold

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _validate_level(self, level: str) -> None:
        """
        Validate that a given difficulty level is recognized.

        Args:
            level: The difficulty level string to validate.

        Raises:
            DifficultyControllerError: If the level is not one of
                'Easy', 'Medium', 'Hard'.
        """
        if level not in DIFFICULTY_LEVELS:
            raise DifficultyControllerError(
                f"Invalid difficulty level: '{level}'. "
                f"Must be one of {DIFFICULTY_LEVELS}."
            )

    def _current_index(self) -> int:
        """
        Get the index of the current difficulty level within
        DIFFICULTY_LEVELS.

        Returns:
            The zero-based index of the current difficulty level.
        """
        return DIFFICULTY_LEVELS.index(self.current_difficulty)

    # ------------------------------------------------------------------
    # Core calculation
    # ------------------------------------------------------------------

    def calculate_difficulty(self) -> str:
        """
        Calculate the appropriate difficulty level based on the
        candidate's current running average score.

        Reads the average score from InterviewMemory and adjusts the
        current difficulty:
            - Increases difficulty if the average score meets or exceeds
              `increase_threshold`.
            - Decreases difficulty if the average score falls at or below
              `decrease_threshold`.
            - Leaves difficulty unchanged if the score falls between the
              two thresholds, or if no score is available yet.

        Returns:
            The resulting difficulty level: one of 'Easy', 'Medium', 'Hard'.
        """
        average_score: Optional[float] = self.memory.get_average_score()

        if average_score is None:
            return self.current_difficulty

        if average_score >= self.increase_threshold:
            return self.increase_difficulty()

        if average_score <= self.decrease_threshold:
            return self.decrease_difficulty()

        return self.current_difficulty

    # ------------------------------------------------------------------
    # Manual adjustment
    # ------------------------------------------------------------------

    def increase_difficulty(self) -> str:
        """
        Move the current difficulty up one level, if not already at the
        highest level.

        Returns:
            The resulting difficulty level: one of 'Easy', 'Medium', 'Hard'.
        """
        next_index = min(self._current_index() + 1, len(DIFFICULTY_LEVELS) - 1)
        self.current_difficulty = DIFFICULTY_LEVELS[next_index]
        return self.current_difficulty

    def decrease_difficulty(self) -> str:
        """
        Move the current difficulty down one level, if not already at the
        lowest level.

        Returns:
            The resulting difficulty level: one of 'Easy', 'Medium', 'Hard'.
        """
        next_index = max(self._current_index() - 1, 0)
        self.current_difficulty = DIFFICULTY_LEVELS[next_index]
        return self.current_difficulty

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def reset(self) -> str:
        """
        Reset the difficulty level back to the configured initial
        difficulty.

        Returns:
            The restored initial difficulty level.
        """
        self.current_difficulty = self.initial_difficulty
        return self.current_difficulty