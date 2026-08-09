"""
interview_planner.py

Plans the complete interview session BEFORE the first question is asked.

Given a candidate profile and the curriculum, this module produces a
structured Interview Plan: an ordered sequence of (day, topic, difficulty)
entries that the interview/session_manager.py will step through to drive
question generation.

This module contains no API, UI, or persistence logic. It is a pure
planning layer. GeminiClient is used only as a fallback — to estimate a
candidate's starting level when structured signals (completed topics,
attempt scores) are insufficient to do so deterministically.
"""

import logging
import math
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Difficulty levels used throughout the planner, in ascending order.
DIFFICULTY_LEVELS = ["easy", "medium", "hard"]

# Candidate skill levels, in ascending order.
CANDIDATE_LEVELS = ["beginner", "intermediate", "advanced"]

MIN_QUESTIONS = 8
MIN_DAYS_COVERED = 4


class InterviewPlannerError(Exception):
    """Raised when a valid interview plan cannot be constructed."""
    pass


class InterviewPlanner:
    """
    Builds a complete, ordered Interview Plan for a candidate based on
    their profile/progress and the available curriculum.

    The plan is computed once, up front, so that the rest of the
    interview flow (session_manager, question_generator) can simply
    step through a predetermined sequence of topics and difficulties.
    """

    def __init__(
        self,
        candidate_profile: Dict[str, Any],
        curriculum: Dict[str, Any],
        gemini_client: Optional[Any] = None,
        min_questions: int = MIN_QUESTIONS,
        min_days_covered: int = MIN_DAYS_COVERED,
    ):
        """
        Initialize the InterviewPlanner.

        Args:
            candidate_profile: Candidate data, typically from
                CandidateLoader.get_candidate(), expected to optionally
                contain 'completed_topics', 'skipped_topics', 'attempts',
                and 'progress'.
            curriculum: Full curriculum data, typically from
                CurriculumLoader.get_curriculum(), expected to contain
                a 'days' mapping of day -> {title, topics, ...}.
            gemini_client: Optional GeminiClient instance. Only used as a
                fallback in estimate_candidate_level() when structured
                candidate data is insufficient to infer a level.
            min_questions: Minimum number of questions the plan must contain.
            min_days_covered: Minimum number of distinct curriculum days
                the plan must draw topics from.

        Raises:
            InterviewPlannerError: If curriculum has no usable days.
        """
        self.candidate_profile = candidate_profile or {}
        self.curriculum = curriculum or {}
        self.gemini_client = gemini_client
        self.min_questions = min_questions
        self.min_days_covered = min_days_covered

        self._days: Dict[str, Any] = self.curriculum.get("days", {})
        if not self._days:
            raise InterviewPlannerError(
                "Curriculum contains no 'days' data. Cannot build an interview plan."
            )

        self._plan: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Candidate level estimation
    # ------------------------------------------------------------------

    def estimate_candidate_level(self) -> str:
        """
        Estimate the candidate's starting skill level.

        Prefers deterministic signals in this order:
            1. Average score of prior attempts (if available).
            2. Ratio of completed vs. skipped topics.
            3. Falls back to GeminiClient to interpret free-text profile
               fields (e.g., 'bio', 'experience_summary') only if no
               structured signal is available.
            4. Defaults to 'beginner' if nothing usable is found.

        Returns:
            One of 'beginner', 'intermediate', 'advanced'.
        """
        attempts = self.candidate_profile.get("attempts", [])
        if attempts:
            scores = [a.get("score") for a in attempts if isinstance(a.get("score"), (int, float))]
            if scores:
                avg_score = sum(scores) / len(scores)
                if avg_score >= 8:
                    return "advanced"
                if avg_score >= 5:
                    return "intermediate"
                return "beginner"

        completed = self.candidate_profile.get("completed_topics", [])
        skipped = self.candidate_profile.get("skipped_topics", [])
        total_seen = len(completed) + len(skipped)

        if total_seen > 0:
            completion_ratio = len(completed) / total_seen
            if completion_ratio >= 0.75 and len(completed) >= 5:
                return "advanced"
            if completion_ratio >= 0.4:
                return "intermediate"
            return "beginner"

        # Fallback: no structured signal available — consult GeminiClient
        # only if we actually have a client and free-text profile data.
        free_text = self.candidate_profile.get("bio") or self.candidate_profile.get("experience_summary")
        if self.gemini_client and free_text:
            try:
                level = self._infer_level_via_llm(free_text)
                if level in CANDIDATE_LEVELS:
                    return level
            except Exception:
                logger.exception(
                    "GeminiClient failed while estimating candidate level. Falling back to 'beginner'."
                )

        return "beginner"

    def _infer_level_via_llm(self, free_text: str) -> str:
        """
        Use GeminiClient to infer a candidate's skill level from free-text
        profile data when no structured signal is available.

        Args:
            free_text: Free-text bio or experience summary for the candidate.

        Returns:
            A raw string response from the model, expected to contain one
            of 'beginner', 'intermediate', or 'advanced'.
        """
        prompt = (
            "Based on the following candidate background, classify their "
            "technical skill level as exactly one word: 'beginner', "
            "'intermediate', or 'advanced'.\n\n"
            f"Candidate background:\n{free_text}\n\n"
            "Respond with only the single classification word."
        )
        response = self.gemini_client.generate(prompt, temperature=0.0, max_output_tokens=16)
        return response.strip().lower()

    # ------------------------------------------------------------------
    # Topic selection
    # ------------------------------------------------------------------

    def select_topics(self) -> List[Dict[str, Any]]:
        """
        Select an ordered list of (day, topic) entries to interview on.

        Selection rules:
            - Topics already in 'completed_topics' are deprioritized
              (only used as filler if nothing else is available).
            - Topics in 'skipped_topics' are prioritized for coverage,
              since they represent gaps.
            - Topics already asked in prior 'attempts' are avoided to
              prevent repetition.
            - At least `min_days_covered` distinct curriculum days must
              be represented.
            - At least `min_questions` topic entries must be produced,
              cycling back through remaining topics if the curriculum
              is small.

        Returns:
            A list of dictionaries: {'day': str, 'title': str, 'topic': str}
            in the order they should be interviewed.
        """
        completed = set(self.candidate_profile.get("completed_topics", []))
        skipped = set(self.candidate_profile.get("skipped_topics", []))
        asked_questions = {
            a.get("topic") for a in self.candidate_profile.get("attempts", []) if a.get("topic")
        }

        skip_priority: List[Dict[str, Any]] = []
        fresh_topics: List[Dict[str, Any]] = []
        completed_fallback: List[Dict[str, Any]] = []

        # Sort days numerically where possible for a sensible default order.
        sorted_day_ids = sorted(self._days.keys(), key=self._safe_day_sort_key)

        for day_id in sorted_day_ids:
            day_data = self._days[day_id]
            title = day_data.get("title", "")
            for topic in day_data.get("topics", []):
                if topic in asked_questions:
                    continue

                entry = {"day": day_id, "title": title, "topic": topic}

                if topic in skipped:
                    skip_priority.append(entry)
                elif topic in completed:
                    completed_fallback.append(entry)
                else:
                    fresh_topics.append(entry)

        # Priority order: skipped-topic gaps first, then fresh/unseen
        # topics, then completed topics as a last resort filler.
        ordered = skip_priority + fresh_topics + completed_fallback

        selected = self._ensure_day_coverage(ordered, sorted_day_ids)
        selected = self._ensure_minimum_questions(selected, ordered)

        return selected

    def _safe_day_sort_key(self, day_id: str):
        """
        Provide a sort key for day identifiers, sorting numerically when
        possible and falling back to string order otherwise.

        Args:
            day_id: The raw day identifier string.

        Returns:
            A value usable as a sort key.
        """
        try:
            return (0, int(day_id))
        except (ValueError, TypeError):
            return (1, str(day_id))

    def _ensure_day_coverage(
        self,
        ordered_topics: List[Dict[str, Any]],
        sorted_day_ids: List[str],
    ) -> List[Dict[str, Any]]:
        """
        Ensure the selected topics span at least `min_days_covered`
        distinct curriculum days, reordering/injecting entries as needed.

        Args:
            ordered_topics: Candidate topic entries in priority order.
            sorted_day_ids: All available day IDs, in sorted order.

        Returns:
            A reordered list of topic entries guaranteeing day coverage
            as early as possible, where the curriculum allows it.
        """
        covered_days: List[str] = []
        result: List[Dict[str, Any]] = []
        remaining = list(ordered_topics)

        # First pass: greedily take one topic per uncovered day, in day order,
        # to guarantee spread across the curriculum as early as possible.
        for day_id in sorted_day_ids:
            if len(covered_days) >= self.min_days_covered:
                break
            match_index = next(
                (i for i, e in enumerate(remaining) if e["day"] == day_id), None
            )
            if match_index is not None:
                entry = remaining.pop(match_index)
                result.append(entry)
                covered_days.append(day_id)

        # Second pass: append the rest of the priority-ordered topics.
        result.extend(remaining)

        return result

    def _ensure_minimum_questions(
        self,
        selected: List[Dict[str, Any]],
        full_pool: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Ensure the selected list contains at least `min_questions` entries,
        cycling back through the topic pool if the curriculum is too small
        to provide enough unique topics.

        Args:
            selected: The currently selected topic entries.
            full_pool: The full pool of candidate topic entries to draw
                additional (repeated, if necessary) entries from.

        Returns:
            A list of topic entries with length >= min_questions,
            provided the pool is non-empty.
        """
        if not full_pool:
            raise InterviewPlannerError(
                "No topics available in the curriculum to build an interview plan."
            )

        result = list(selected)
        cycle_index = 0

        while len(result) < self.min_questions:
            result.append(full_pool[cycle_index % len(full_pool)])
            cycle_index += 1

        return result

    # ------------------------------------------------------------------
    # Difficulty calculation
    # ------------------------------------------------------------------

    def calculate_difficulty(self, question_index: int, total_questions: int) -> str:
        """
        Calculate the difficulty level for a given question position,
        producing a gradual increase in difficulty over the course of
        the interview, anchored to the candidate's estimated level.

        Args:
            question_index: Zero-based index of the question in the plan.
            total_questions: Total number of questions in the plan.

        Returns:
            One of 'easy', 'medium', 'hard'.
        """
        if total_questions <= 1:
            return DIFFICULTY_LEVELS[CANDIDATE_LEVELS.index(self.estimate_candidate_level())]

        starting_level_index = CANDIDATE_LEVELS.index(self.estimate_candidate_level())

        # Progress ratio through the interview, from 0.0 to 1.0.
        progress_ratio = question_index / (total_questions - 1)

        # Map progress ratio onto the difficulty scale, starting at the
        # candidate's estimated level and rising toward 'hard' by the end.
        max_difficulty_index = len(DIFFICULTY_LEVELS) - 1
        raw_index = starting_level_index + progress_ratio * (max_difficulty_index - starting_level_index)

        difficulty_index = min(max_difficulty_index, max(0, math.floor(raw_index)))
        return DIFFICULTY_LEVELS[difficulty_index]

    # ------------------------------------------------------------------
    # Plan creation
    # ------------------------------------------------------------------

    def create_plan(self) -> Dict[str, Any]:
        """
        Build the complete Interview Plan.

        Returns:
            A dictionary of the form:
            {
                "candidate_level": str,
                "total_questions": int,
                "days_covered": List[str],
                "questions": [
                    {
                        "order": int,
                        "day": str,
                        "day_title": str,
                        "topic": str,
                        "difficulty": str
                    },
                    ...
                ]
            }

        Raises:
            InterviewPlannerError: If no valid plan can be constructed.
        """
        candidate_level = self.estimate_candidate_level()
        topics = self.select_topics()

        if len(topics) < self.min_questions:
            raise InterviewPlannerError(
                f"Unable to build a plan with the minimum required "
                f"{self.min_questions} questions."
            )

        days_covered = sorted({t["day"] for t in topics}, key=self._safe_day_sort_key)
        if len(days_covered) < self.min_days_covered:
            logger.warning(
                "Interview plan covers only %d day(s); minimum requested was %d. "
                "Curriculum may be too small.",
                len(days_covered),
                self.min_days_covered,
            )

        total_questions = len(topics)
        questions: List[Dict[str, Any]] = []

        for index, entry in enumerate(topics):
            questions.append(
                {
                    "order": index + 1,
                    "day": entry["day"],
                    "day_title": entry["title"],
                    "topic": entry["topic"],
                    "difficulty": self.calculate_difficulty(index, total_questions),
                }
            )

        self._plan = questions

        return {
            "candidate_level": candidate_level,
            "total_questions": total_questions,
            "days_covered": days_covered,
            "questions": questions,
        }

    # ------------------------------------------------------------------
    # Plan traversal
    # ------------------------------------------------------------------

    def get_next_topic(self, current_index: int) -> Optional[Dict[str, Any]]:
        """
        Get the next topic entry in the plan following the given index.

        Args:
            current_index: The zero-based index of the last completed
                question (use -1 to get the first question).

        Returns:
            The next question dictionary from the plan, or None if the
            plan is exhausted.

        Raises:
            InterviewPlannerError: If create_plan() has not been called yet.
        """
        if not self._plan:
            raise InterviewPlannerError(
                "No interview plan has been created yet. Call create_plan() first."
            )

        next_index = current_index + 1
        if next_index < 0 or next_index >= len(self._plan):
            return None

        return self._plan[next_index]