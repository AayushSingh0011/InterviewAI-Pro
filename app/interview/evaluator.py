"""
evaluator.py

Evaluates candidate answers during an interview session.

This module orchestrates three collaborators to produce exactly ONE
validated evaluation per call:
    - GeminiClient: performs the actual evaluation generation, driven by
      the EVALUATION_PROMPT template from app/llm/prompts.py.
    - InterviewMemory: is updated with the evaluation result for the
      current turn.

This module contains no API, UI, or persistence logic.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.llm.prompts import EVALUATION_PROMPT

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

MAX_EVALUATION_ATTEMPTS = 3

REQUIRED_NUMERIC_FIELDS = ["overall_score", "correctness", "depth", "communication", "confidence"]
REQUIRED_LIST_FIELDS = ["strengths", "weaknesses"]
REQUIRED_STRING_FIELDS = ["interviewer_notes"]


class EvaluatorError(Exception):
    """Base exception for evaluation failures."""
    pass


class EvaluationParsingError(EvaluatorError):
    """Raised when the LLM response cannot be parsed as valid JSON."""
    pass


class EvaluationValidationError(EvaluatorError):
    """Raised when a parsed evaluation response fails schema validation
    after all retry attempts."""
    pass


@dataclass
class EvaluationResult:
    """
    Structured representation of a single answer evaluation.

    Attributes:
        overall_score: Overall score for the answer, on a 1-10 scale.
        correctness: Correctness score, on a 1-10 scale.
        depth: Depth-of-understanding score, on a 1-10 scale.
        communication: Communication clarity score, on a 1-10 scale.
        confidence: Perceived confidence score, on a 1-10 scale.
        strengths: List of identified strengths in the answer.
        weaknesses: List of identified weaknesses in the answer.
        interviewer_notes: Free-text interviewer notes/commentary.
    """

    overall_score: float
    correctness: float
    depth: float
    communication: float
    confidence: float
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    interviewer_notes: str = ""
    next_action: str = "NEXT_TOPIC"

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert this result into a plain, JSON-serializable dictionary.

        Returns:
            A dictionary containing all fields of the evaluation result.
        """
        return {
            "overall_score": self.overall_score,
            "correctness": self.correctness,
            "depth": self.depth,
            "communication": self.communication,
            "confidence": self.confidence,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "interviewer_notes": self.interviewer_notes,
            "next_action": self.next_action,
        }

    def to_json(self) -> str:
        """
        Serialize this result into a JSON string.

        Returns:
            A JSON-formatted string representation of this evaluation.
        """
        return json.dumps(self.to_dict(), ensure_ascii=False)


class InterviewEvaluator:
    """
    Evaluates a candidate's answer to a single interview question,
    producing a structured, validated EvaluationResult and recording it
    in the interview's memory.
    """

    def __init__(
        self,
        gemini_client: Any,
        memory: Any,
        max_attempts: int = MAX_EVALUATION_ATTEMPTS,
    ):
        """
        Initialize the InterviewEvaluator.

        Args:
            gemini_client: An instance of GeminiClient (app/llm/gemini.py)
                used to perform the underlying evaluation generation.
            memory: An instance of InterviewMemory
                (app/interview/memory.py), used to store the evaluation
                result against the current turn.
            max_attempts: Maximum number of evaluation attempts before
                raising EvaluationValidationError.
        """
        self.gemini_client = gemini_client
        self.memory = memory
        self.max_attempts = max_attempts




    def needs_followup(
      self,
      evaluation: EvaluationResult,
      threshold: float = 6.0,
    ) -> bool:
      """
      Determine whether a follow-up question should be asked.

      Returns:
      True -> Stay on the same topic and ask a follow-up.
      False -> Move to the next topic.
      """

      return evaluation.overall_score < threshold









    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    def build_prompt(
        self,
        question: str,
        answer: str,
        topic: Optional[str] = None,
        difficulty: Optional[str] = None,
    ) -> str:
        """
        Build the full evaluation prompt sent to the LLM, based on
        EVALUATION_PROMPT.

        Args:
            question: The interview question that was asked.
            answer: The candidate's answer text to evaluate.
            topic: The topic being assessed, included as additional
                grounding context for the model.
            difficulty: The difficulty level of the question, included as
                additional grounding context for the model.

        Returns:
            The fully formatted prompt string.
        """
        base_prompt = EVALUATION_PROMPT.format(question=question, candidate_answer=answer)

        context_note = (
            f"\n\nAdditional context: Topic = {topic or 'N/A'}, "
            f"Difficulty = {difficulty or 'N/A'}. "
            f"Calibrate your scoring expectations to this difficulty level."
        )

        return base_prompt + context_note

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    def parse_response(self, raw_response: str) -> Dict[str, Any]:
        """
        Parse the raw LLM response into a Python dictionary.

        Args:
            raw_response: The raw text returned by the LLM, expected to
                be a strict JSON object.

        Returns:
            The parsed evaluation dictionary.

        Raises:
            EvaluationParsingError: If the response is not valid JSON or
                does not parse into a JSON object.
        """
        try:
            parsed = json.loads(raw_response)
        except json.JSONDecodeError as exc:
            raise EvaluationParsingError(
                f"Failed to parse evaluation response as JSON: {exc}"
            ) from exc

        if not isinstance(parsed, dict):
            raise EvaluationParsingError(
                "Evaluation response did not parse into a JSON object."
            )

        return parsed

    # ------------------------------------------------------------------
    # Response validation
    # ------------------------------------------------------------------

    def validate_response(self, data: Dict[str, Any]) -> bool:
        """
        Validate that a parsed evaluation response matches the expected
        schema.

        Args:
            data: The parsed evaluation dictionary to validate.

        Returns:
            True if all required fields are present and correctly typed,
            False otherwise.
        """
        for field_name in REQUIRED_NUMERIC_FIELDS:
            value = data.get(field_name)
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                return False
            if not (0 <= value <= 10):
                return False

        for field_name in REQUIRED_LIST_FIELDS:
            value = data.get(field_name)
            if not isinstance(value, list):
                return False

        for field_name in REQUIRED_STRING_FIELDS:
            value = data.get(field_name)
            if not isinstance(value, str) or not value.strip():
                return False

        return True

    # ------------------------------------------------------------------
    # Core evaluation
    # ------------------------------------------------------------------

    def evaluate_answer(
        self,
        question: str,
        answer: str,
        topic: Optional[str] = None,
        difficulty: Optional[str] = None,
    ) -> EvaluationResult:
        """
        Evaluate a candidate's answer to a single interview question.

        Workflow:
            1. Build the evaluation prompt from the question, answer,
               topic, and difficulty.
            2. Call GeminiClient to generate a strict JSON evaluation.
            3. Parse and validate the response, retrying on failure.
            4. Store the resulting evaluation in InterviewMemory.
            5. Return a structured EvaluationResult object.

        Args:
            question: The interview question that was asked.
            answer: The candidate's answer text to evaluate.
            topic: The topic being assessed.
            difficulty: The difficulty level of the question.

        Returns:
            An EvaluationResult instance representing the validated
            evaluation of the candidate's answer.

        Raises:
            EvaluationValidationError: If a valid evaluation could not be
                produced within max_attempts.
        """
        raw_response = ""
        parsed: Dict[str, Any] = {}
        last_error: Optional[str] = None

        for attempt in range(1, self.max_attempts + 1):
            prompt = self.build_prompt(question, answer, topic, difficulty)
            raw_response = self.gemini_client.generate(prompt, temperature=0.3)

            try:
                parsed = self.parse_response(raw_response)
            except EvaluationParsingError as exc:
                logger.warning(
                    "Evaluation parsing failed on attempt %d/%d: %s",
                    attempt,
                    self.max_attempts,
                    exc,
                )
                last_error = str(exc)
                continue

            if self.validate_response(parsed):
                break

            logger.warning(
                "Evaluation response failed schema validation on attempt %d/%d: %r",
                attempt,
                self.max_attempts,
                parsed,
            )
            last_error = f"Schema validation failed for response: {parsed!r}"
            parsed = {}
        else:
            raise EvaluationValidationError(
                f"Failed to produce a valid evaluation after "
                f"{self.max_attempts} attempts. Last error: {last_error}"
            )

        if not parsed:
            raise EvaluationValidationError(
                f"Failed to produce a valid evaluation after "
                f"{self.max_attempts} attempts. Last error: {last_error}"
            )

        result = EvaluationResult(
            overall_score=float(parsed["overall_score"]),
            correctness=float(parsed["correctness"]),
            depth=float(parsed["depth"]),
            communication=float(parsed["communication"]),
            confidence=float(parsed["confidence"]),
            strengths=list(parsed["strengths"]),
            weaknesses=list(parsed["weaknesses"]),
            interviewer_notes=str(parsed["interviewer_notes"]),
        )

        if self.needs_followup(result):
          result.next_action = "FOLLOW_UP"
        else:
          result.next_action = "NEXT_TOPIC"

        self.memory.add_evaluation(result.to_dict())

        return result