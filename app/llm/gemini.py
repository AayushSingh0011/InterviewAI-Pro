"""
gemini.py

Production-ready Gemini API client for InterviewAI-Pro.

Responsible for all interactions with the Google Gemini API, including:
    - Generic text generation
    - Interview question generation
    - Contextual follow-up question generation
    - Candidate answer evaluation
    - Feedback report generation

The API key is loaded from environment variables via python-dotenv.
"""

import os
import logging
from typing import Optional

import google.generativeai as genai
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Environment & Logging Setup
# ---------------------------------------------------------------------------

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

DEFAULT_MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")


class GeminiClientError(Exception):
    """Raised when the Gemini client fails to initialize or generate a response."""
    pass


class GeminiClient:
    """
    Wrapper client around the Google Gemini API.

    Handles authentication, model initialization, and provides
    high-level methods tailored to the InterviewAI-Pro interview workflow.
    """

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME, api_key: Optional[str] = None):
        """
        Initialize the Gemini client.

        Args:
            model_name: Name of the Gemini model to use.
            api_key: Optional explicit API key. Falls back to GEMINI_API_KEY env var.

        Raises:
            GeminiClientError: If no API key is found or configuration fails.
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")

        if not self.api_key:
            raise GeminiClientError(
                "GEMINI_API_KEY not found. Please set it in your .env file."
            )

        try:
            genai.configure(api_key=self.api_key)
            self.model_name = model_name
            self.model = genai.GenerativeModel(self.model_name)
            logger.info("GeminiClient initialized with model: %s", self.model_name)
        except Exception as exc:
            logger.exception("Failed to initialize Gemini client.")
            raise GeminiClientError(f"Failed to initialize Gemini client: {exc}") from exc

    # ------------------------------------------------------------------
    # Core generation method
    # ------------------------------------------------------------------

    def generate(self, prompt: str, temperature: float = 0.7, max_output_tokens: int = 1024) -> str:
        """
        Generic text generation method used internally by all other methods.

        Args:
            prompt: The prompt string to send to the Gemini model.
            temperature: Sampling temperature controlling creativity.
            max_output_tokens: Maximum number of tokens in the response.

        Returns:
            The generated text response as a string.

        Raises:
            GeminiClientError: If the API call fails or returns no content.
        """
        if not prompt or not prompt.strip():
            raise ValueError("Prompt must be a non-empty string.")

        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                ),
            )

            if not response or not getattr(response, "text", None):
                raise GeminiClientError("Gemini API returned an empty response.")

            return response.text.strip()

        except Exception as exc:
            logger.exception("Gemini generation failed.")
            raise GeminiClientError(f"Gemini generation failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Interview-specific methods
    # ------------------------------------------------------------------

    def generate_question(
        self,
        role: str,
        topic: str,
        difficulty: str = "medium",
    ) -> str:
        """
        Generate a single interview question.

        Args:
            role: Target job role (e.g., "Backend Developer").
            topic: Specific topic or skill area (e.g., "System Design").
            difficulty: Difficulty level ("easy", "medium", "hard").

        Returns:
            A generated interview question as a string.
        """
        prompt = (
            f"You are an expert technical interviewer.\n"
            f"Generate one {difficulty}-difficulty interview question "
            f"for the role of '{role}', focused on the topic '{topic}'.\n"
            f"Return only the question text, with no numbering or extra commentary."
        )
        return self.generate(prompt, temperature=0.8)

    def generate_followup(
        self,
        original_question: str,
        candidate_answer: str,
    ) -> str:
        """
        Generate a contextual follow-up question based on the candidate's answer.

        Args:
            original_question: The question that was originally asked.
            candidate_answer: The candidate's response to that question.

        Returns:
            A generated follow-up question as a string.
        """
        prompt = (
            f"You are an expert technical interviewer conducting a live interview.\n"
            f"Original question: {original_question}\n"
            f"Candidate's answer: {candidate_answer}\n\n"
            f"Based on this answer, generate one relevant follow-up question "
            f"to probe deeper into the candidate's understanding.\n"
            f"Return only the follow-up question text, with no extra commentary."
        )
        return self.generate(prompt, temperature=0.7)

    def evaluate_answer(
        self,
        question: str,
        candidate_answer: str,
    ) -> str:
        """
        Evaluate a candidate's answer to an interview question.

        Args:
            question: The interview question that was asked.
            candidate_answer: The candidate's response to evaluate.

        Returns:
            A structured evaluation (e.g., score and justification) as a string.
            Expected to be parsed downstream by the interview/evaluator module.
        """
        prompt = (
            f"You are an expert technical interviewer evaluating a candidate's response.\n"
            f"Question: {question}\n"
            f"Candidate's answer: {candidate_answer}\n\n"
            f"Evaluate the answer on a scale of 1-10 for correctness, clarity, "
            f"and depth. Return the result in JSON format with keys: "
            f"'score', 'correctness', 'clarity', 'depth', 'justification'."
        )
        return self.generate(prompt, temperature=0.3)

    def generate_feedback(
        self,
        interview_summary: str,
    ) -> str:
        """
        Generate an overall feedback report based on a full interview session.

        Args:
            interview_summary: A compiled summary of all questions, answers,
                and per-answer evaluations from the session.

        Returns:
            A structured feedback report as a string (e.g., strengths,
            weaknesses, and improvement suggestions). Expected to be parsed
            downstream by the services/report_service module.
        """
        prompt = (
            f"You are an expert technical interview coach.\n"
            f"Below is a summary of a candidate's full interview session:\n\n"
            f"{interview_summary}\n\n"
            f"Generate a comprehensive feedback report in JSON format with keys: "
            f"'overall_score', 'strengths', 'weaknesses', 'recommendations'."
        )
        return self.generate(prompt, temperature=0.5, max_output_tokens=1536)