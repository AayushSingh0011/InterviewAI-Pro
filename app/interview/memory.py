"""
memory.py

Manages the in-memory conversation state for a single interview session.

This module contains no API, UI, persistence, or LLM logic — it is a pure
state-management layer used by app/interview/session_manager.py and
app/services/interview_service.py to track everything that happens during
an interview: the plan being followed, each question/answer/evaluation
exchanged, and derived metrics like the running average score.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class InterviewTurn:
    """
    Represents a single question/answer exchange within an interview.

    Attributes:
        index: Zero-based position of this turn within the interview.
        day: Curriculum day identifier this turn's topic belongs to.
        topic: The topic being assessed in this turn.
        difficulty: The difficulty level assigned to this turn's question.
        question: The actual question text presented to the candidate.
        answer: The candidate's answer text, if submitted.
        evaluation: The evaluation result dictionary for this turn's
            answer, if it has been evaluated.
    """

    index: int
    day: Optional[str] = None
    topic: Optional[str] = None
    difficulty: Optional[str] = None
    question: Optional[str] = None
    answer: Optional[str] = None
    evaluation: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert this turn into a plain, serializable dictionary.

        Returns:
            A dictionary representation of the turn.
        """
        return {
            "index": self.index,
            "day": self.day,
            "topic": self.topic,
            "difficulty": self.difficulty,
            "question": self.question,
            "answer": self.answer,
            "evaluation": self.evaluation,
        }


@dataclass
class InterviewMemory:
    """
    Tracks the full state of a single interview conversation.

    Holds the interview plan, the current position within it, every
    question/answer/evaluation exchanged so far, and derived metrics
    such as the running average score. Instances are independent of
    any web framework, database, or LLM client.
    """

    plan: Dict[str, Any] = field(default_factory=dict)
    current_index: int = -1
    turns: List[InterviewTurn] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def initialize(self, plan: Dict[str, Any]) -> None:
        """
        Initialize (or reset) the memory with a new interview plan.

        Args:
            plan: The Interview Plan dictionary produced by
                InterviewPlanner.create_plan(), expected to contain a
                'questions' list of {order, day, day_title, topic,
                difficulty} entries.
        """
        self.plan = plan or {}
        self.current_index = -1
        self.turns = []




    def should_generate_followup(self, threshold: float = 6.0) -> bool:
      """
      Decide whether a follow-up question should be asked based on the
    latest evaluation score. Returns:
        True -> Ask a follow-up on the same topic.
        False -> Move to the next topic.
    """
      if not self.evaluations:
         return False

      latest = self.evaluations[-1]

      score = latest.get("overall_score", 0)

      return score < threshold




    # ------------------------------------------------------------------
    # Recording exchanges
    # ------------------------------------------------------------------

    def next_question(self) -> Optional[Dict[str, Any]]:
        """
        Advance to the next planned question and start a new turn for it.

        Reads the next entry from the plan's question list (based on
        `current_index`), creates a new InterviewTurn pre-populated with
        its day/topic/difficulty, and appends it to the turn history.

        Returns:
            The plan entry dictionary for the new current question
            (day, day_title, topic, difficulty, order), or None if the
            plan is exhausted or has not been initialized.
        """
        questions = self.plan.get("questions", [])
        next_index = self.current_index + 1

        if next_index >= len(questions):
            return None

        plan_entry = questions[next_index]
        self.current_index = next_index

        turn = InterviewTurn(
            index=next_index,
            day=plan_entry.get("day"),
            topic=plan_entry.get("topic"),
            difficulty=plan_entry.get("difficulty"),
        )
        self.turns.append(turn)

        return plan_entry

    def add_question(self, question: str) -> None:
        """
        Record the generated question text for the current turn.

        Args:
            question: The question text produced for the candidate.

        Raises:
            ValueError: If no turn is currently active (next_question()
                has not been called yet).
        """
        turn = self._current_turn()
        turn.question = question

    def add_answer(self, answer: str) -> None:
        """
        Record the candidate's answer for the current turn.

        Args:
            answer: The candidate's answer text.

        Raises:
            ValueError: If no turn is currently active.
        """
        turn = self._current_turn()
        turn.answer = answer

    def add_evaluation(self, evaluation: Dict[str, Any]) -> None:
        """
        Record the evaluation result for the current turn's answer.

        Args:
            evaluation: The evaluation result dictionary (e.g., containing
                'overall_score', 'correctness', 'depth', 'communication',
                'confidence', 'strengths', 'weaknesses', 'interviewer_notes').

        Raises:
            ValueError: If no turn is currently active.
        """
        turn = self._current_turn()
        turn.evaluation = evaluation

    def _current_turn(self) -> InterviewTurn:
        """
        Get the currently active turn.

        Returns:
            The InterviewTurn at `current_index`.

        Raises:
            ValueError: If there is no active turn (memory is empty or
                uninitialized).
        """
        if not self.turns or self.current_index < 0 or self.current_index >= len(self.turns):
            raise ValueError(
                "No active interview turn. Call next_question() before "
                "recording a question, answer, or evaluation."
            )
        return self.turns[self.current_index]

    # ------------------------------------------------------------------
    # Read accessors
    # ------------------------------------------------------------------

    def get_last_question(self) -> Optional[str]:
        """
        Get the question text of the most recent turn.

        Returns:
            The question text, or None if no turn exists or no question
            has been recorded yet.
        """
        if not self.turns:
            return None
        return self.turns[-1].question

    def get_last_answer(self) -> Optional[str]:
        """
        Get the candidate's answer text from the most recent turn.

        Returns:
            The answer text, or None if no turn exists or no answer has
            been recorded yet.
        """
        if not self.turns:
            return None
        return self.turns[-1].answer

    def get_current_topic(self) -> Optional[str]:
        """
        Get the topic associated with the current turn.

        Returns:
            The topic string, or None if no turn is currently active.
        """
        if not self.turns:
            return None
        return self.turns[-1].topic

    def get_average_score(self) -> Optional[float]:
        """
        Calculate the running average of 'overall_score' across all
        evaluated turns so far.

        Returns:
            The average score as a float, or None if no turns have been
            evaluated yet.
        """
        scores = [
            turn.evaluation.get("overall_score")
            for turn in self.turns
            if turn.evaluation and isinstance(turn.evaluation.get("overall_score"), (int, float))
        ]

        if not scores:
            return None

        return sum(scores) / len(scores)

    def get_context(self) -> Dict[str, Any]:
        """
        Build a compact context snapshot suitable for passing into LLM
        prompts (e.g., for follow-up question generation or evaluation).

        Returns:
            A dictionary containing the current topic, difficulty, last
            question, last answer, and the number of completed turns.
        """
        current_turn = self.turns[-1] if self.turns else None

        return {
            "current_index": self.current_index,
            "topic": current_turn.topic if current_turn else None,
            "difficulty": current_turn.difficulty if current_turn else None,
            "last_question": current_turn.question if current_turn else None,
            "last_answer": current_turn.answer if current_turn else None,
            "completed_turns": len([t for t in self.turns if t.answer is not None]),
            "total_questions": len(self.plan.get("questions", [])),
            "average_score": self.get_average_score(),
        }

    def get_history(self) -> List[Dict[str, Any]]:
        """
        Get the full interview history as a list of serializable turns.

        Returns:
            A list of dictionaries, one per turn, in chronological order.
        """
        return [turn.to_dict() for turn in self.turns]

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def is_completed(self) -> bool:
        """
        Determine whether the interview has covered all planned questions.

        Returns:
            True if the current index has reached the end of the plan's
            question list, False otherwise (including when the plan has
            not been initialized).
        """
        total_questions = len(self.plan.get("questions", []))
        if total_questions == 0:
            return False
        return self.current_index >= total_questions - 1 and (
            self.turns and self.turns[-1].answer is not None
        )

    # ------------------------------------------------------------------
    # Reset / Serialization
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """
        Reset the memory to a completely empty, uninitialized state.
        """
        self.plan = {}
        self.current_index = -1
        self.turns = []

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize the entire memory state into a plain dictionary.

        Returns:
            A dictionary containing the plan, current index, full turn
            history, and the running average score.
        """
        return {
            "plan": self.plan,
            "current_index": self.current_index,
            "turns": self.get_history(),
            "average_score": self.get_average_score(),
            "is_completed": self.is_completed(),
        }