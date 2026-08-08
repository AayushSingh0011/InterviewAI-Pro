from typing import Any

from pydantic import BaseModel, Field


class InterviewStartRequest(BaseModel):
    sessionId: str = Field(min_length=1)
    candidate: dict[str, Any]


class InterviewTurnRequest(BaseModel):
    sessionId: str = Field(min_length=1)
    message: str = Field(min_length=1)


class Feedback(BaseModel):
    summary: str
    strengths: list[str]
    gaps: list[str]
    next: list[str]


class InterviewResponse(BaseModel):
    reply: str
    done: bool
    feedback: Feedback | None = None