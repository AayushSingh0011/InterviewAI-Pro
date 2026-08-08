from fastapi import APIRouter, HTTPException

from app.core.session_manager import SessionManager
from app.schemas.interview import (
    InterviewResponse,
    InterviewStartRequest,
    InterviewTurnRequest,
)


router = APIRouter(
    prefix="/api",
    tags=["Interview"],
)


session_manager = SessionManager()


@router.post(
    "/interview",
    response_model=InterviewResponse,
)
def interview(
    request: InterviewStartRequest | InterviewTurnRequest,
):
    session = session_manager.get_session(request.sessionId)

    # -------------------------------------------------
    # START NEW INTERVIEW
    # -------------------------------------------------
    if session is None:

        if not isinstance(request, InterviewStartRequest):
            raise HTTPException(
                status_code=400,
                detail="First request must include candidate data.",
            )

        session = session_manager.create_session(
            session_id=request.sessionId,
            candidate=request.candidate,
        )

        session.messages.append(
            {
                "role": "assistant",
                "content": (
                    "Welcome to the technical interview. "
                    "Let's begin with your experience from the AI Cohort."
                ),
            }
        )

        session.question_count = 1

        return InterviewResponse(
            reply=(
                "Welcome to the technical interview. "
                "Let's begin with your experience from the AI Cohort."
            ),
            done=False,
        )

    # -------------------------------------------------
    # CONTINUE EXISTING INTERVIEW
    # -------------------------------------------------

    if not isinstance(request, InterviewTurnRequest):
        raise HTTPException(
            status_code=400,
            detail="This session already exists. Send a message.",
        )

    if session.done:
        return InterviewResponse(
            reply="This interview has already been completed.",
            done=True,
        )

    # Store candidate answer
    session.messages.append(
        {
            "role": "user",
            "content": request.message,
        }
    )

    # -------------------------------------------------
    # TEMPORARY QUESTION LOGIC
    # -------------------------------------------------
    #
    # This is intentionally simple for now.
    # Member 2 will replace this section with
    # the actual LLM interviewer.
    # -------------------------------------------------

    session.question_count += 1

    if session.question_count >= 8:

        session.done = True

        return InterviewResponse(
            reply="Thank you. The interview is now complete.",
            done=True,
            feedback={
                "summary": (
                    "The candidate completed the technical interview."
                ),
                "strengths": [
                    "Completed the interview interaction successfully."
                ],
                "gaps": [
                    "Detailed technical assessment will be generated "
                    "by the interview intelligence layer."
                ],
                "next": [
                    "Review the technical concepts covered during the cohort."
                ],
            },
        )

    reply = (
        f"Thank you for your answer. "
        f"Let's explore another technical topic. "
        f"This is question {session.question_count}."
    )

    session.messages.append(
        {
            "role": "assistant",
            "content": reply,
        }
    )

    return InterviewResponse(
        reply=reply,
        done=False,
    )