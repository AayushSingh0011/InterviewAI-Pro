from typing import Any


class InterviewSession:
    def __init__(
        self,
        session_id: str,
        candidate: dict[str, Any],
    ):
        self.session_id = session_id
        self.candidate = candidate
        self.messages: list[dict[str, str]] = []
        self.question_count = 0
        self.current_day: int | None = None
        self.done = False


class SessionManager:
    def __init__(self):
        self.sessions: dict[str, InterviewSession] = {}

    def create_session(
        self,
        session_id: str,
        candidate: dict[str, Any],
    ) -> InterviewSession:

        session = InterviewSession(
            session_id=session_id,
            candidate=candidate,
        )

        self.sessions[session_id] = session

        return session

    def get_session(
        self,
        session_id: str,
    ) -> InterviewSession | None:

        return self.sessions.get(session_id)