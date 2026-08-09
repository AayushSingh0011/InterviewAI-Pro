"""
session_manager.py

Stores the state of active AI interview sessions.

Each session keeps:
- candidate information
- interview memory
- Gemini client
- interview planner
- question generator
- evaluator
- conversation messages
- interview status
"""

from typing import Any, Dict, Optional


class InterviewSession:
    """
    Represents one complete interview session.

    The same InterviewSession object must be returned for every
    request using the same session_id.
    """

    def __init__(
        self,
        session_id: str,
        candidate: Any = None,
    ):
        self.session_id = session_id

        # ---------------------------------------------------------
        # Candidate
        # ---------------------------------------------------------

        self.candidate = candidate

        # ---------------------------------------------------------
        # AI / Interview components
        # ---------------------------------------------------------

        self.gemini_client = None
        self.planner = None
        self.memory = None
        self.question_generator = None
        self.evaluator = None

        # ---------------------------------------------------------
        # Conversation
        # ---------------------------------------------------------

        self.messages = []

        # ---------------------------------------------------------
        # Interview status
        # ---------------------------------------------------------

        self.question_count = 0
        self.done = False


class SessionManager:
    """
    Keeps all active InterviewSession objects.

    IMPORTANT:
    The same SessionManager instance must be used by the API
    for all requests.
    """

    def __init__(self):
        # session_id -> InterviewSession
        self.sessions: Dict[str, InterviewSession] = {}

    # =============================================================
    # CREATE SESSION
    # =============================================================

    def create_session(
        self,
        session_id: str,
        candidate: Any = None,
    ) -> InterviewSession:
        """
        Create and store a new interview session.

        If a session with the same ID already exists, the existing
        session is returned instead of silently replacing it.
        """

        if session_id in self.sessions:
            return self.sessions[session_id]

        session = InterviewSession(
            session_id=session_id,
            candidate=candidate,
        )

        self.sessions[session_id] = session

        return session

    # =============================================================
    # GET SESSION
    # =============================================================

    def get_session(
        self,
        session_id: str,
    ) -> Optional[InterviewSession]:
        """
        Return the existing session.

        Returns None if the session does not exist.
        """

        return self.sessions.get(session_id)

    # =============================================================
    # GET OR CREATE
    # =============================================================

    def get_or_create_session(
        self,
        session_id: str,
        candidate: Any = None,
    ) -> InterviewSession:
        """
        Return an existing session or create a new one.
        """

        session = self.get_session(session_id)

        if session is not None:
            return session

        return self.create_session(
            session_id=session_id,
            candidate=candidate,
        )

    # =============================================================
    # DELETE SESSION
    # =============================================================

    def delete_session(
        self,
        session_id: str,
    ) -> None:
        """
        Delete one interview session.
        """

        self.sessions.pop(session_id, None)

    # =============================================================
    # CLEAR ALL
    # =============================================================

    def clear(self) -> None:
        """
        Clear all active interview sessions.
        """

        self.sessions.clear()

    # =============================================================
    # DEBUG / STATUS
    # =============================================================

    def has_session(
        self,
        session_id: str,
    ) -> bool:
        """
        Check whether a session exists.
        """

        return session_id in self.sessions

    def session_count(self) -> int:
        """
        Return number of active sessions.
        """

        return len(self.sessions)






# from typing import Any


# class InterviewSession:

#     def __init__(
#         self,
#         session_id: str,
#         candidate: dict[str, Any],
#     ):
#         self.session_id = session_id
#         self.candidate = candidate

#         self.messages: list[dict[str, str]] = []

#         self.question_count = 0
#         self.current_day: int | None = None
#         self.done = False

#         # AI interview components
#         self.gemini_client = None
#         self.planner = None
#         self.memory = None
#         self.question_generator = None
#         self.evaluator = None


# class SessionManager:

#     def __init__(self):
#         self.sessions: dict[str, InterviewSession] = {}

#     def create_session(
#         self,
#         session_id: str,
#         candidate: dict[str, Any],
#     ) -> InterviewSession:

#         session = InterviewSession(
#             session_id=session_id,
#             candidate=candidate,
#         )

#         self.sessions[session_id] = session

#         return session

#     def get_session(
#         self,
#         session_id: str,
#     ) -> InterviewSession | None:

#         return self.sessions.get(session_id)










# # from typing import Any


# # class InterviewSession:
# #     def __init__(
# #         self,
# #         session_id: str,
# #         candidate: dict[str, Any],
# #     ):
# #         self.session_id = session_id
# #         self.candidate = candidate
# #         self.messages: list[dict[str, str]] = []
# #         self.question_count = 0
# #         self.current_day: int | None = None
# #         self.done = False


# # class SessionManager:
# #     def __init__(self):
# #         self.sessions: dict[str, InterviewSession] = {}

# #     def create_session(
# #         self,
# #         session_id: str,
# #         candidate: dict[str, Any],
# #     ) -> InterviewSession:

# #         session = InterviewSession(
# #             session_id=session_id,
# #             candidate=candidate,
# #         )

# #         self.sessions[session_id] = session

# #         return session

# #     def get_session(
# #         self,
# #         session_id: str,
# #     ) -> InterviewSession | None:

# #         return self.sessions.get(session_id)