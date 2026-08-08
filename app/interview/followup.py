"""
followup.py

Generates adaptive follow-up questions during an interview session.

This module orchestrates several collaborators to decide whether a
follow-up question is warranted for the candidate's most recent answer,
and if so, to generate exactly ONE follow-up question:
    - InterviewMemory: supplies the previous question/answer context.
    - DifficultyController: supplies the current difficulty level.
    - GeminiClient: performs the actual text generation, driven by the
      FOLLOWUP_PROMPT template from app/llm/prompts.py.

This module contains no API or UI logic.
"""

import logging
from typing import Any, Dict, List, Optional, Set

from app.llm.prompts import FOLLOWUP_PROMPT

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

MAX_FOLLOWUP_ATTEMPTS = 3

# Recognized values for evaluation.next_action that trigger a follow-up.
FOLLOW_UP_ACTION = "FOLLOW_UP"

# Fallback score thresholds used only when an evaluation carries no
# explicit 'next_action' field. A weak answer prompts a clarifying
# follow-up; an exceptionally strong answer prompts a deeper probe.
FALLBACK_WEAK_SCORE_THRESHOLD = 5.0
FALLBACK_STRONG_SCORE_THRESHOLD = 9.0


class FollowUpGeneratorError(Exception):
    """Raised when a follow-up question cannot be generated."""
    pass


class FollowUpGenerator:
    """
    Decides whether the candidate's last answer warrants a follow-up
    question and, if so, generates exactly one such question.
    """

    def __init__(
        self,
        gemini_client: Any,
        memory: Any,
        difficulty_controller: Any,
        max_attempts: int = MAX_FOLLOWUP_ATTEMPTS,
    ):
        """
        Initialize the FollowUpGenerator.

        Args:
            gemini_client: An instance of GeminiClient (app/llm/gemini.py)
                used to perform the underlying text generation.
            memory: An instance of InterviewMemory
                (app/interview/memory.py), used to read the previous
                question/answer and full question history.
            difficulty_controller: An instance of DifficultyController
                (app/interview/difficulty_controller.py), used to read
                the current difficulty level for prompt grounding.
            max_attempts: Maximum number of generation attempts before
                giving up on a valid follow-up question.
        """
        self.gemini_client = gemini_client
        self.memory = memory
        self.difficulty_controller = difficulty_controller
        self.max_attempts = max_attempts

    # ------------------------------------------------------------------
    # Decision logic
    # ------------------------------------------------------------------

    def should_generate_followup(self, evaluation: Any) -> bool:
        """
        Determine whether a follow-up question should be generated for
        the given evaluation.

        Primarily checks an explicit `next_action` field on the
        evaluation (e.g., evaluation.next_action == 'FOLLOW_UP', or
        evaluation['next_action'] == 'FOLLOW_UP' for dict-shaped
        evaluations). If no `next_action` is present, falls back to a
        score-based heuristic: a weak answer (at or below
        FALLBACK_WEAK_SCORE_THRESHOLD) or an exceptionally strong answer
        (at or above FALLBACK_STRONG_SCORE_THRESHOLD) triggers a follow-up.

        Args:
            evaluation: The evaluation result for the candidate's last
                answer. May be an EvaluationResult instance, a plain
                dict, or any object exposing these fields.

        Returns:
            True if a follow-up question should be generated, False otherwise.
        """
        if evaluation is None:
            return False

        next_action = self._extract_field(evaluation, "next_action")
        if isinstance(next_action, str):
            return next_action.strip().upper() == FOLLOW_UP_ACTION

        overall_score = self._extract_field(evaluation, "overall_score")
        if isinstance(overall_score, (int, float)):
            return (
                overall_score <= FALLBACK_WEAK_SCORE_THRESHOLD
                or overall_score >= FALLBACK_STRONG_SCORE_THRESHOLD
            )

        logger.warning(
            "Evaluation has no usable 'next_action' or 'overall_score' field; "
            "defaulting to no follow-up."
        )
        return False

    def _extract_field(self, evaluation: Any, field_name: str) -> Any:
        """
        Extract a field's value from an evaluation object regardless of
        whether it is a dict or an attribute-based object (e.g., a
        dataclass instance).

        Args:
            evaluation: The evaluation object to read from.
            field_name: The name of the field to extract.

        Returns:
            The field's value, or None if not present.
        """
        if isinstance(evaluation, dict):
            return evaluation.get(field_name)
        return getattr(evaluation, field_name, None)

    def _summarize_evaluation(self, evaluation: Any) -> str:
        """
        Build a compact, human-readable summary of an evaluation for
        inclusion in the follow-up prompt.

        Args:
            evaluation: The evaluation result to summarize.

        Returns:
            A short string summarizing scores, strengths, and weaknesses.
        """
        overall_score = self._extract_field(evaluation, "overall_score")
        strengths = self._extract_field(evaluation, "strengths") or []
        weaknesses = self._extract_field(evaluation, "weaknesses") or []
        notes = self._extract_field(evaluation, "interviewer_notes") or ""

        return (
            f"Overall Score: {overall_score}. "
            f"Strengths: {', '.join(strengths) if strengths else 'None noted'}. "
            f"Weaknesses: {', '.join(weaknesses) if weaknesses else 'None noted'}. "
            f"Notes: {notes}"
        )

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    def build_prompt(
        self,
        previous_question: str,
        candidate_answer: str,
        evaluation: Any,
        difficulty: str,
    ) -> str:
        """
        Build the full follow-up prompt sent to the LLM, based on
        FOLLOWUP_PROMPT.

        Args:
            previous_question: The question that was originally asked.
            candidate_answer: The candidate's answer to that question.
            evaluation: The evaluation result for that answer, used to
                determine whether to simplify or go deeper.
            difficulty: The current difficulty level for the interview.

        Returns:
            The fully formatted follow-up prompt string.
        """
        evaluation_summary = self._summarize_evaluation(evaluation)

        return FOLLOWUP_PROMPT.format(
            previous_question=previous_question,
            candidate_answer=candidate_answer,
            evaluation=evaluation_summary,
            difficulty=difficulty,
        )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _is_valid_followup(self, followup_text: str, previous_questions: Set[str]) -> bool:
        """
        Validate a generated follow-up question before accepting it.

        Args:
            followup_text: The candidate follow-up question text.
            previous_questions: A set of lowercased, stripped question
                texts already asked in this session.

        Returns:
            True if the follow-up is non-empty and not a repeat of any
            previous question, False otherwise.
        """
        if not followup_text or not followup_text.strip():
            return False
        return followup_text.strip().lower() not in previous_questions

    # ------------------------------------------------------------------
    # Core generation
    # ------------------------------------------------------------------

    def generate_followup(self, evaluation: Any) -> Optional[str]:
        """
        Generate a follow-up question for the candidate's most recent
        answer, if warranted.

        Workflow:
            1. Check evaluation.next_action (via should_generate_followup()).
            2. If a follow-up is warranted, build the follow-up prompt
               using the previous question/answer from InterviewMemory
               and the current difficulty from DifficultyController.
            3. Generate and validate exactly one follow-up question.
            4. Otherwise, return None.

        Args:
            evaluation: The evaluation result for the candidate's last
                answer.

        Returns:
            The generated follow-up question text, or None if no
            follow-up is warranted.

        Raises:
            FollowUpGeneratorError: If a follow-up is warranted but a
                valid question could not be produced within max_attempts.
        """
        if not self.should_generate_followup(evaluation):
            return None

        previous_question = self.memory.get_last_question()
        candidate_answer = self.memory.get_last_answer()

        if not previous_question or not candidate_answer:
            logger.warning(
                "Cannot generate follow-up: missing previous question or answer in memory."
            )
            return None

        difficulty = getattr(self.difficulty_controller, "current_difficulty", None)

        previous_questions: Set[str] = {
            turn.question.strip().lower()
            for turn in getattr(self.memory, "turns", [])
            if getattr(turn, "question", None)
        }

        prompt = self.build_prompt(previous_question, candidate_answer, evaluation, difficulty)

        for attempt in range(1, self.max_attempts + 1):
            raw_response = self.gemini_client.generate(prompt, temperature=0.7)
            followup_text = raw_response.strip()

            if self._is_valid_followup(followup_text, previous_questions):
                return followup_text

            logger.warning(
                "Generated follow-up failed validation on attempt %d/%d: %r",
                attempt,
                self.max_attempts,
                followup_text,
            )

        raise FollowUpGeneratorError(
            f"Failed to generate a valid follow-up question after {self.max_attempts} attempts."
        )