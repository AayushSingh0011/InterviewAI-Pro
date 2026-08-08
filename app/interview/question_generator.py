"""
question_generator.py

Generates interview questions for the current step of an interview session.

This module orchestrates three collaborators to produce exactly ONE
validated interview question per call:
    - InterviewPlanner: supplies the current topic/day/difficulty.
    - InterviewMemory: supplies conversation history and is updated with
      the newly generated question.
    - GeminiClient: performs the actual text generation, driven by the
      QUESTION_PROMPT template from app/llm/prompts.py.

This module contains no API, UI, or persistence logic.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.llm.prompts import QUESTION_PROMPT

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

MAX_GENERATION_ATTEMPTS = 3


class QuestionGeneratorError(Exception):
    """Base exception for question generation failures."""
    pass


class InterviewCompletedError(QuestionGeneratorError):
    """Raised when a question is requested but the interview plan is exhausted."""
    pass


class QuestionValidationError(QuestionGeneratorError):
    """Raised when a generated question fails validation after all retry attempts."""
    pass


@dataclass
class GeneratedQuestion:
    """
    Structured representation of a single generated interview question.

    Attributes:
        order: Position of this question within the overall interview plan.
        day: Curriculum day identifier this question belongs to.
        day_title: Human-readable title of the curriculum day.
        topic: The specific topic this question assesses.
        difficulty: The difficulty level of this question.
        question: The final, validated question text shown to the candidate.
        raw_response: The unparsed raw text returned by the LLM, kept for
            debugging/auditing purposes.
    """

    order: int
    day: Optional[str]
    day_title: Optional[str]
    topic: Optional[str]
    difficulty: Optional[str]
    question: str
    raw_response: str = field(default="", repr=False)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert this result into a plain, JSON-serializable dictionary.

        Returns:
            A dictionary containing all structured fields of the
            generated question (excluding the raw LLM response).
        """
        return {
            "order": self.order,
            "day": self.day,
            "day_title": self.day_title,
            "topic": self.topic,
            "difficulty": self.difficulty,
            "question": self.question,
        }

    def to_json(self) -> str:
        """
        Serialize this result into a JSON string.

        Returns:
            A JSON-formatted string representation of this question.
        """
        return json.dumps(self.to_dict(), ensure_ascii=False)


class QuestionGenerator:
    """
    Generates exactly one interview question per call, grounded in the
    current position of the interview plan and aware of everything asked
    so far.
    """

    def __init__(
        self,
        gemini_client: Any,
        planner: Any,
        memory: Any,
        max_attempts: int = MAX_GENERATION_ATTEMPTS,
    ):
        """
        Initialize the QuestionGenerator.

        Args:
            gemini_client: An instance of GeminiClient (app/llm/gemini.py)
                used to perform the underlying text generation.
            planner: An instance of InterviewPlanner
                (app/interview/interview_planner.py), already holding a
                created plan, used to determine the current topic/difficulty.
            memory: An instance of InterviewMemory
                (app/interview/memory.py), used to read history and to be
                updated once a question is generated.
            max_attempts: Maximum number of generation attempts before
                raising QuestionValidationError.
        """
        self.gemini_client = gemini_client
        self.planner = planner
        self.memory = memory
        self.max_attempts = max_attempts

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    def build_prompt(
        self,
        candidate_profile: Dict[str, Any],
        target_topic: str,
        completed_topics: List[str],
        skipped_topics: List[str],
        difficulty: str,
        previous_questions: List[str],
    ) -> str:
        """
        Build the full prompt sent to the LLM, based on QUESTION_PROMPT.

        Args:
            candidate_profile: The candidate's profile dictionary.
            target_topic: The specific topic the question must cover, as
                determined by the InterviewPlanner for the current step.
            completed_topics: Topics the candidate has already completed.
            skipped_topics: Topics the candidate has previously skipped.
            difficulty: The difficulty level for this question.
            previous_questions: All question texts asked so far in this
                session, used to prevent repetition.

        Returns:
            The fully formatted prompt string, including an explicit
            instruction for the model to respond in structured JSON.
        """
        base_prompt = QUESTION_PROMPT.format(
            candidate_profile=candidate_profile,
            curriculum_topics=[target_topic],
            completed_topics=completed_topics,
            skipped_topics=skipped_topics,
            difficulty=difficulty,
            previous_questions=previous_questions,
        )

        json_instruction = (
            "\n\nRespond strictly in JSON format with no markdown, code fences, "
            "or additional commentary, using exactly this shape:\n"
            '{"question": "<the interview question text>"}'
        )

        return base_prompt + json_instruction

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_question(self, question: str, previous_questions: List[str]) -> bool:
        """
        Validate a generated question before accepting it.

        Args:
            question: The candidate question text to validate.
            previous_questions: All question texts already asked in this
                session, used to detect repetition.

        Returns:
            True if the question is non-empty and not a repeat of any
            previous question (case-insensitive comparison), False otherwise.
        """
        if not question or not question.strip():
            return False

        normalized = question.strip().lower()
        previous_normalized = {q.strip().lower() for q in previous_questions if q}

        if normalized in previous_normalized:
            return False

        return True

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    def _parse_response(self, raw_response: str) -> str:
        """
        Parse the raw LLM response into a plain question string.

        Attempts strict JSON parsing first (per the format requested in
        build_prompt()). Falls back to treating the raw response as the
        question text directly if JSON parsing fails.

        Args:
            raw_response: The raw text returned by the LLM.

        Returns:
            The extracted question text.
        """
        try:
            parsed = json.loads(raw_response)
            if isinstance(parsed, dict) and "question" in parsed:
                return str(parsed["question"]).strip()
        except (json.JSONDecodeError, TypeError):
            logger.warning("Failed to parse LLM response as JSON. Falling back to raw text.")

        return raw_response.strip()

    # ------------------------------------------------------------------
    # Core generation
    # ------------------------------------------------------------------

    def generate_question(self) -> GeneratedQuestion:
        """
        Generate exactly one new interview question for the current step
        of the interview plan.

        Workflow:
            1. Read the current topic/day/difficulty from InterviewPlanner.
            2. Read prior question history from InterviewMemory.
            3. Build the prompt and call GeminiClient.
            4. Parse and validate the response, retrying on failure.
            5. Update InterviewMemory with the new question.
            6. Return a structured GeneratedQuestion object.

        Returns:
            A GeneratedQuestion instance representing the newly generated,
            validated question.

        Raises:
            InterviewCompletedError: If the interview plan has no more
                questions remaining.
            QuestionValidationError: If a valid, non-repeated question
                could not be produced within max_attempts.
        """
        next_entry = self.planner.get_next_topic(self.memory.current_index)
        if next_entry is None:
            raise InterviewCompletedError(
                "No more questions remain in the interview plan."
            )

        candidate_profile = getattr(self.planner, "candidate_profile", {})
        completed_topics = candidate_profile.get("completed_topics", [])
        skipped_topics = candidate_profile.get("skipped_topics", [])
        previous_questions = [
            turn.question for turn in self.memory.turns if turn.question
        ]

        target_topic = next_entry.get("topic")
        difficulty = next_entry.get("difficulty")

        raw_response = ""
        question_text = ""
        last_error: Optional[str] = None

        for attempt in range(1, self.max_attempts + 1):
            prompt = self.build_prompt(
                candidate_profile=candidate_profile,
                target_topic=target_topic,
                completed_topics=completed_topics,
                skipped_topics=skipped_topics,
                difficulty=difficulty,
                previous_questions=previous_questions,
            )

            raw_response = self.gemini_client.generate(prompt, temperature=0.8)
            question_text = self._parse_response(raw_response)

            if self.validate_question(question_text, previous_questions):
                break

            logger.warning(
                "Generated question failed validation on attempt %d/%d: %r",
                attempt,
                self.max_attempts,
                question_text,
            )
            last_error = question_text
        else:
            raise QuestionValidationError(
                f"Failed to generate a valid, non-repeated question after "
                f"{self.max_attempts} attempts. Last output: {last_error!r}"
            )

        # Advance and update interview memory with the accepted question.
        self.memory.next_question()
        self.memory.add_question(question_text)

        return GeneratedQuestion(
            order=next_entry.get("order", self.memory.current_index + 1),
            day=next_entry.get("day"),
            day_title=next_entry.get("day_title"),
            topic=target_topic,
            difficulty=difficulty,
            question=question_text,
            raw_response=raw_response,
        )