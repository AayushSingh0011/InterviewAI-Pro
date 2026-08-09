"""
feedback_generator.py

Generates the final, recruiter-style feedback report at the end of an
interview session.

This module orchestrates two collaborators to produce a single structured
report:
    - InterviewMemory: supplies the full interview history (questions,
      answers, evaluations, average score) used to build the report prompt.
    - GeminiClient: performs the actual report generation, driven by the
      FINAL_FEEDBACK_PROMPT template from app/llm/prompts.py.

This module contains no API or UI logic.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.llm.prompts import FINAL_FEEDBACK_PROMPT

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

MAX_FEEDBACK_ATTEMPTS = 3

REQUIRED_NUMERIC_FIELDS = ["overall_score", "technical_skills", "communication", "problem_solving"]
REQUIRED_LIST_FIELDS = ["strengths", "weaknesses", "topics_to_improve", "learning_resources"]
REQUIRED_STRING_FIELDS = ["hire_recommendation", "summary"]

VALID_HIRE_RECOMMENDATIONS = {"Strong Hire", "Hire", "Lean Hire", "No Hire"}


class FeedbackGeneratorError(Exception):
    """Base exception for feedback generation failures."""
    pass


class FeedbackParsingError(FeedbackGeneratorError):
    """Raised when the LLM response cannot be parsed as valid JSON."""
    pass


class FeedbackValidationError(FeedbackGeneratorError):
    """Raised when a parsed feedback response fails schema validation
    after all retry attempts."""
    pass


@dataclass
class FeedbackReport:
    """
    Structured representation of the final recruiter-style feedback report.

    Attributes:
        overall_score: Overall interview performance score, on a 1-10 scale.
        technical_skills: Technical skills score, on a 1-10 scale.
        communication: Communication skills score, on a 1-10 scale.
        problem_solving: Problem-solving skills score, on a 1-10 scale.
        strengths: List of overall strengths demonstrated in the interview.
        weaknesses: List of overall weaknesses demonstrated in the interview.
        topics_to_improve: List of topics the candidate should study further.
        learning_resources: List of suggested learning resources.
        hire_recommendation: One of 'Strong Hire', 'Hire', 'Lean Hire', 'No Hire'.
        summary: Free-text overall summary of the interview.
    """

    overall_score: float
    technical_skills: float
    communication: float
    problem_solving: float
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    topics_to_improve: List[str] = field(default_factory=list)
    learning_resources: List[str] = field(default_factory=list)
    hire_recommendation: str = ""
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert this report into a plain, JSON-serializable dictionary.

        Returns:
            A dictionary containing all fields of the feedback report.
        """
        return {
            "overall_score": self.overall_score,
            "technical_skills": self.technical_skills,
            "communication": self.communication,
            "problem_solving": self.problem_solving,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "topics_to_improve": self.topics_to_improve,
            "learning_resources": self.learning_resources,
            "hire_recommendation": self.hire_recommendation,
            "summary": self.summary,
        }

    def to_json(self) -> str:
        """
        Serialize this report into a JSON string.

        Returns:
            A JSON-formatted string representation of this report.
        """
        return json.dumps(self.to_dict(), ensure_ascii=False)


class FeedbackGenerator:
    """
    Generates the final, structured recruiter feedback report for a
    completed (or in-progress) interview session, based on its full
    recorded history.
    """

    def __init__(
        self,
        gemini_client: Any,
        memory: Any,
        max_attempts: int = MAX_FEEDBACK_ATTEMPTS,
    ):
        """
        Initialize the FeedbackGenerator.

        Args:
            gemini_client: An instance of GeminiClient (app/llm/gemini.py)
                used to perform the underlying report generation.
            memory: An instance of InterviewMemory
                (app/interview/memory.py), used to read the full interview
                history and running average score.
            max_attempts: Maximum number of generation attempts before
                raising FeedbackValidationError.
        """
        self.gemini_client = gemini_client
        self.memory = memory
        self.max_attempts = max_attempts

    # ------------------------------------------------------------------
    # History summarization
    # ------------------------------------------------------------------

    def _summarize_history(self) -> str:
        """
        Build a structured, readable summary of the full interview
        history, suitable for insertion into FINAL_FEEDBACK_PROMPT.

        Reads each turn's day, topic, difficulty, question, answer, and
        evaluation from InterviewMemory, along with the running average
        score.

        Returns:
            A formatted multi-line string summarizing the entire interview.
        """
        history: List[Dict[str, Any]] = self.memory.get_history()
        average_score: Optional[float] = self.memory.get_average_score()

        lines: List[str] = [f"Overall Average Score So Far: {average_score if average_score is not None else 'N/A'}"]

        for turn in history:
            evaluation = turn.get("evaluation") or {}
            lines.append(
                "\n---\n"
                f"Turn {turn.get('index', 0) + 1} "
                f"(Day: {turn.get('day', 'N/A')}, Topic: {turn.get('topic', 'N/A')}, "
                f"Difficulty: {turn.get('difficulty', 'N/A')})\n"
                f"Question: {turn.get('question', 'N/A')}\n"
                f"Answer: {turn.get('answer', 'N/A')}\n"
                f"Evaluation Score: {evaluation.get('overall_score', 'N/A')}\n"
                f"Strengths: {', '.join(evaluation.get('strengths', []) or [])}\n"
                f"Weaknesses: {', '.join(evaluation.get('weaknesses', []) or [])}\n"
                f"Interviewer Notes: {evaluation.get('interviewer_notes', 'N/A')}"
            )

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    def build_prompt(self) -> str:
        """
        Build the full feedback report prompt sent to the LLM, based on
        FINAL_FEEDBACK_PROMPT.

        Returns:
            The fully formatted prompt string, including the complete
            summarized interview history.
        """
        interview_summary = self._summarize_history()
        return FINAL_FEEDBACK_PROMPT.format(interview_summary=interview_summary)

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    def _parse_response(self, raw_response: str) -> Dict[str, Any]:
        """
        Parse the raw LLM response into a Python dictionary.

        Args:
            raw_response: The raw text returned by the LLM, expected to
                be a strict JSON object.

        Returns:
            The parsed feedback report dictionary.

        Raises:
            FeedbackParsingError: If the response is not valid JSON or
                does not parse into a JSON object.
        """
        try:
            parsed = json.loads(raw_response)
        except json.JSONDecodeError as exc:
            raise FeedbackParsingError(
                f"Failed to parse feedback response as JSON: {exc}"
            ) from exc

        if not isinstance(parsed, dict):
            raise FeedbackParsingError(
                "Feedback response did not parse into a JSON object."
            )

        return parsed

    # ------------------------------------------------------------------
    # Response validation
    # ------------------------------------------------------------------

    def _validate_response(self, data: Dict[str, Any]) -> bool:
        """
        Validate that a parsed feedback response matches the expected
        schema.

        Args:
            data: The parsed feedback report dictionary to validate.

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

        if data.get("hire_recommendation") not in VALID_HIRE_RECOMMENDATIONS:
            return False

        return True

    # ------------------------------------------------------------------
    # Core generation
    # ------------------------------------------------------------------

    def generate_feedback(self) -> FeedbackReport:
        """
        Generate the final, structured recruiter feedback report for the
        interview session currently held in InterviewMemory.

        Workflow:
            1. Read the full interview history from InterviewMemory.
            2. Build the feedback report prompt.
            3. Call GeminiClient to generate a strict JSON report.
            4. Parse and validate the response, retrying on failure.
            5. Return a structured FeedbackReport object.

        Returns:
            A FeedbackReport instance representing the validated final
            interview feedback.

        Raises:
            FeedbackValidationError: If a valid report could not be
                produced within max_attempts.
        """
        prompt = self.build_prompt()

        parsed: Dict[str, Any] = {}
        last_error: Optional[str] = None

        for attempt in range(1, self.max_attempts + 1):
            raw_response = self.gemini_client.generate(prompt, temperature=0.5, max_output_tokens=1536)

            try:
                parsed = self._parse_response(raw_response)
            except FeedbackParsingError as exc:
                logger.warning(
                    "Feedback parsing failed on attempt %d/%d: %s",
                    attempt,
                    self.max_attempts,
                    exc,
                )
                last_error = str(exc)
                continue

            if self._validate_response(parsed):
                break

            logger.warning(
                "Feedback response failed schema validation on attempt %d/%d: %r",
                attempt,
                self.max_attempts,
                parsed,
            )
            last_error = f"Schema validation failed for response: {parsed!r}"
            parsed = {}
        else:
            raise FeedbackValidationError(
                f"Failed to produce a valid feedback report after "
                f"{self.max_attempts} attempts. Last error: {last_error}"
            )

        if not parsed:
            raise FeedbackValidationError(
                f"Failed to produce a valid feedback report after "
                f"{self.max_attempts} attempts. Last error: {last_error}"
            )

        return FeedbackReport(
            overall_score=float(parsed["overall_score"]),
            technical_skills=float(parsed["technical_skills"]),
            communication=float(parsed["communication"]),
            problem_solving=float(parsed["problem_solving"]),
            strengths=list(parsed["strengths"]),
            weaknesses=list(parsed["weaknesses"]),
            topics_to_improve=list(parsed["topics_to_improve"]),
            learning_resources=list(parsed["learning_resources"]),
            hire_recommendation=str(parsed["hire_recommendation"]),
            summary=str(parsed["summary"]),
        )