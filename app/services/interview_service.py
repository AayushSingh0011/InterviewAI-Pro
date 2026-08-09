"""
interview_service.py

Orchestrates the complete lifecycle of an interview session.

This module is the top-level coordinator that wires together every
interview subsystem:
    - CandidateLoader / CurriculumLoader: supply input data.
    - InterviewPlanner: builds the interview plan.
    - InterviewMemory: tracks conversation state.
    - QuestionGenerator: generates each planned question.
    - InterviewEvaluator: evaluates each candidate answer.
    - DifficultyController: adapts difficulty based on performance.
    - FollowUpGenerator: generates follow-up questions when warranted.
    - FeedbackGenerator: produces the final recruiter report.

This module contains no API or UI logic — it is a pure orchestration
layer intended to be called from app/api/routes_interview.py.
"""

import logging
from typing import Any, Dict, Optional

from app.services.candidate_loader import CandidateLoader
from app.services.curriculum_loader import CurriculumLoader
from app.interview.interview_planner import InterviewPlanner
from app.interview.memory import InterviewMemory, InterviewTurn
from app.interview.question_generator import QuestionGenerator, InterviewCompletedError
from app.interview.evaluator import InterviewEvaluator
from app.interview.difficulty_controller import DifficultyController
from app.interview.followup import FollowUpGenerator
from app.interview.feedback_generator import FeedbackGenerator

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Maps InterviewPlanner's candidate level scale to DifficultyController's
# difficulty scale, since the two modules use different casing/vocabulary.
CANDIDATE_LEVEL_TO_DIFFICULTY = {
    "beginner": "Easy",
    "intermediate": "Medium",
    "advanced": "Hard",
}
DEFAULT_INITIAL_DIFFICULTY = "Easy"


class InterviewServiceError(Exception):
    """Raised when the interview service is used in an invalid state
    (e.g., submitting an answer before an interview has been started)."""
    pass


class InterviewService:
    """
    Coordinates the full interview lifecycle for a single candidate
    session: starting the interview, handling answer submissions
    (evaluation, adaptive difficulty, follow-ups, next question), and
    finishing the interview with a final feedback report.
    """

    def __init__(
        self,
        gemini_client: Any,
        candidates_path: Optional[str] = None,
        curriculum_path: Optional[str] = None,
    ):
        """
        Initialize the InterviewService.

        Args:
            gemini_client: An instance of GeminiClient (app/llm/gemini.py),
                shared across all LLM-driven subsystems (planner, question
                generator, evaluator, follow-up generator, feedback
                generator).
            candidates_path: Optional override path for candidates.json,
                passed through to CandidateLoader.
            curriculum_path: Optional override path for curriculum.json,
                passed through to CurriculumLoader.
        """
        self.gemini_client = gemini_client

        self.candidate_loader = (
            CandidateLoader(candidates_path) if candidates_path else CandidateLoader()
        )
        self.curriculum_loader = (
            CurriculumLoader(curriculum_path) if curriculum_path else CurriculumLoader()
        )

        self.candidate_id: Optional[str] = None
        self.memory: Optional[InterviewMemory] = None
        self.planner: Optional[InterviewPlanner] = None
        self.difficulty_controller: Optional[DifficultyController] = None
        self.question_generator: Optional[QuestionGenerator] = None
        self.evaluator: Optional[InterviewEvaluator] = None
        self.followup_generator: Optional[FollowUpGenerator] = None
        self.feedback_generator: Optional[FeedbackGenerator] = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_started(self) -> None:
        """
        Verify that an interview session is currently active.

        Raises:
            InterviewServiceError: If start_interview() has not been
                called yet (or the previous session was never initialized).
        """
        if self.memory is None or self.planner is None:
            raise InterviewServiceError(
                "No active interview session. Call start_interview() first."
            )

    def _map_candidate_level(self, candidate_level: str) -> str:
        """
        Map an InterviewPlanner candidate level ('beginner', 'intermediate',
        'advanced') to a DifficultyController difficulty level
        ('Easy', 'Medium', 'Hard').

        Args:
            candidate_level: The candidate level string from the plan.

        Returns:
            The corresponding difficulty level, defaulting to 'Easy' if
            the candidate level is unrecognized.
        """
        return CANDIDATE_LEVEL_TO_DIFFICULTY.get(
            (candidate_level or "").lower(), DEFAULT_INITIAL_DIFFICULTY
        )

    def _record_followup_turn(self, followup_text: str, based_on: InterviewTurn) -> None:
        """
        Append a follow-up question as a new turn in InterviewMemory.

        Follow-up questions are not part of the pre-built plan, so this
        bypasses InterviewMemory.next_question() (which pulls from the
        plan) and instead appends a turn directly, inheriting the day,
        topic, and difficulty of the turn it follows up on.

        Args:
            followup_text: The generated follow-up question text.
            based_on: The InterviewTurn the follow-up question relates to.
        """
        new_index = self.memory.current_index + 1
        turn = InterviewTurn(
            index=new_index,
            day=based_on.day,
            topic=based_on.topic,
            difficulty=based_on.difficulty,
            question=followup_text,
        )
        self.memory.turns.append(turn)
        self.memory.current_index = new_index

    def _advance_to_next_question(self) -> Optional[Dict[str, Any]]:
        """
        Generate the next planned question, if any remain.

        Returns:
            The structured next question as a dictionary, or None if the
            interview plan has been exhausted.
        """
        try:
            generated = self.question_generator.generate_question()
            return generated.to_dict()
        except InterviewCompletedError:
            return None

    # ------------------------------------------------------------------
    # Lifecycle: start
    # ------------------------------------------------------------------

    def start_interview(self, candidate_id: str) -> Dict[str, Any]:
        """
        Start a new interview session for the given candidate.

        Loads the candidate profile and curriculum, builds the interview
        plan, initializes memory and all downstream subsystems, and
        generates the first question.

        Args:
            candidate_id: Unique identifier of the candidate to interview.

        Returns:
            A dictionary containing the candidate ID, a summary of the
            interview plan, the starting difficulty, and the first
            generated question.
        """
        candidate_profile = self.candidate_loader.get_candidate(candidate_id)
        curriculum = self.curriculum_loader.get_curriculum()

        self.candidate_id = candidate_id

        self.planner = InterviewPlanner(
            candidate_profile=candidate_profile,
            curriculum=curriculum,
            gemini_client=self.gemini_client,
        )
        plan = self.planner.create_plan()

        self.memory = InterviewMemory()
        self.memory.initialize(plan)

        initial_difficulty = self._map_candidate_level(plan.get("candidate_level"))
        self.difficulty_controller = DifficultyController(
            memory=self.memory,
            initial_difficulty=initial_difficulty,
        )

        self.question_generator = QuestionGenerator(
            gemini_client=self.gemini_client,
            planner=self.planner,
            memory=self.memory,
        )
        self.evaluator = InterviewEvaluator(
            gemini_client=self.gemini_client,
            memory=self.memory,
        )
        self.followup_generator = FollowUpGenerator(
            gemini_client=self.gemini_client,
            memory=self.memory,
            difficulty_controller=self.difficulty_controller,
        )
        self.feedback_generator = FeedbackGenerator(
            gemini_client=self.gemini_client,
            memory=self.memory,
        )

        first_question = self.question_generator.generate_question()

        logger.info("Interview started for candidate '%s'.", candidate_id)

        return {
            "candidate_id": candidate_id,
            "plan_summary": {
                "candidate_level": plan.get("candidate_level"),
                "total_questions": plan.get("total_questions"),
                "days_covered": plan.get("days_covered"),
            },
            "current_difficulty": self.difficulty_controller.current_difficulty,
            "question": first_question.to_dict(),
        }

    # ------------------------------------------------------------------
    # Lifecycle: submit answer
    # ------------------------------------------------------------------

    def submit_answer(self, answer: str) -> Dict[str, Any]:
        """
        Submit the candidate's answer to the current question, evaluate
        it, adapt difficulty, and determine the next step (a follow-up
        question or the next planned question).

        Args:
            answer: The candidate's answer text to the current question.

        Returns:
            A dictionary containing the evaluation result, the updated
            average score, the updated difficulty level, whether the
            interview is now complete, and the next question (a follow-up
            or a planned question), or None if the interview is complete.

        Raises:
            InterviewServiceError: If no interview session is active.
        """
        self._ensure_started()

        self.memory.add_answer(answer)
        current_turn = self.memory.turns[self.memory.current_index]

        evaluation = self.evaluator.evaluate_answer(
            question=current_turn.question,
            answer=answer,
            topic=current_turn.topic,
            difficulty=current_turn.difficulty,
        )

        updated_difficulty = self.difficulty_controller.calculate_difficulty()
        followup_text = self.followup_generator.generate_followup(evaluation)

        if followup_text:
            self._record_followup_turn(followup_text, current_turn)
            next_question: Optional[Dict[str, Any]] = {
                "type": "followup",
                "day": current_turn.day,
                "topic": current_turn.topic,
                "difficulty": current_turn.difficulty,
                "question": followup_text,
            }
        else:
            next_question = self._advance_to_next_question()

        return {
            "evaluation": evaluation.to_dict(),
            "average_score": self.memory.get_average_score(),
            "current_difficulty": updated_difficulty,
            "next_question": next_question,
            "completed": next_question is None,
        }

    # ------------------------------------------------------------------
    # Lifecycle: finish
    # ------------------------------------------------------------------

    def finish_interview(self) -> Dict[str, Any]:
        """
        Finish the interview session and generate the final recruiter
        feedback report.

        Returns:
            A dictionary containing the candidate ID, final average
            score, total number of turns answered, and the structured
            final feedback report.

        Raises:
            InterviewServiceError: If no interview session is active.
        """
        self._ensure_started()

        report = self.feedback_generator.generate_feedback()
        answered_turns = [turn for turn in self.memory.turns if turn.answer is not None]

        logger.info("Interview finished for candidate '%s'.", self.candidate_id)

        return {
            "candidate_id": self.candidate_id,
            "average_score": self.memory.get_average_score(),
            "total_questions_answered": len(answered_turns),
            "report": report.to_dict(),
        }