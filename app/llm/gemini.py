"""
groq.py

Groq API client for InterviewAI-Pro.

The class is intentionally named GeminiClient for compatibility
with the existing InterviewAI-Pro codebase.
"""

import os
import logging
from typing import Optional

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

DEFAULT_MODEL_NAME = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-120b"
)


class GeminiClientError(Exception):
    """Raised when the LLM client fails to initialize or generate a response."""
    pass


class GeminiClient:
    """
    Groq-backed LLM client.

    The class name is kept as GeminiClient so existing
    evaluator/interview code continues to work.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        api_key: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")

        if not self.api_key:
            raise GeminiClientError(
                "GROQ_API_KEY not found. Please set it in your .env file."
            )

        try:
            self.model_name = model_name
            self.client = Groq(api_key=self.api_key)

            logger.info(
                "LLM client initialized with Groq model: %s",
                self.model_name,
            )

        except Exception as exc:
            logger.exception("Failed to initialize Groq client.")
            raise GeminiClientError(
                f"Failed to initialize Groq client: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Core generation method
    # ------------------------------------------------------------------

    def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_output_tokens: int = 1024,
    ) -> str:

        if not prompt or not prompt.strip():
            raise ValueError("Prompt must be a non-empty string.")

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                temperature=temperature,
                max_tokens=max_output_tokens,
            )

            content = response.choices[0].message.content

            if not content:
                raise GeminiClientError(
                    "Groq API returned an empty response."
                )

            return content.strip()

        except Exception as exc:
            logger.exception("Groq generation failed.")
            raise GeminiClientError(
                f"Groq generation failed: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Interview-specific methods
    # ------------------------------------------------------------------

    def generate_question(
        self,
        role: str,
        topic: str,
        difficulty: str = "medium",
    ) -> str:

        prompt = (
            f"You are an expert technical interviewer.\n"
            f"Generate one {difficulty}-difficulty interview question "
            f"for the role of '{role}', focused on the topic '{topic}'.\n"
            f"Return only the question text, with no numbering "
            f"or extra commentary."
        )

        return self.generate(prompt, temperature=0.8)

    def generate_followup(
        self,
        original_question: str,
        candidate_answer: str,
    ) -> str:

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

        prompt = (
            f"You are an expert technical interview coach.\n"
            f"Below is a summary of a candidate's full interview session:\n\n"
            f"{interview_summary}\n\n"
            f"Generate a comprehensive feedback report in JSON format with keys: "
            f"'overall_score', 'strengths', 'weaknesses', 'recommendations'."
        )

        return self.generate(
            prompt,
            temperature=0.5,
            max_output_tokens=1536,
        )