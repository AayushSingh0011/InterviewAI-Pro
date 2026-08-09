import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.core.session_manager import SessionManager

from app.schemas.interview import (
    InterviewResponse,
    InterviewStartRequest,
    InterviewTurnRequest,
)

from app.llm.gemini import GeminiClient

from app.interview.interview_planner import InterviewPlanner

from app.interview.memory import (
    InterviewMemory,
    InterviewTurn,
)

from app.interview.question_generator import (
    QuestionGenerator,
    InterviewCompletedError,
)

from app.interview.evaluator import InterviewEvaluator


# ================================================================
# ROUTER
# ================================================================

router = APIRouter(
    prefix="/api",
    tags=["Interview"],
)


# ================================================================
# IMPORTANT
# ================================================================
#
# Create SessionManager ONLY ONCE.
#
# DO NOT move this inside the interview() function.
#
# This object stores the active interview sessions.
#
# ================================================================

session_manager = SessionManager()


# ================================================================
# CURRICULUM LOADER
# ================================================================

def load_curriculum():
    """
    Load curriculum.json and convert the current list format
    into the dictionary format expected by InterviewPlanner.
    """

    path = (
        Path(__file__).resolve().parents[2]
        / "data"
        / "curriculum.json"
    )

    if not path.exists():
        raise FileNotFoundError(
            f"Curriculum file not found: {path}"
        )

    with open(
        path,
        "r",
        encoding="utf-8",
    ) as f:
        data = json.load(f)

    # ------------------------------------------------------------
    # Current curriculum.json is a LIST
    # ------------------------------------------------------------

    if isinstance(data, list):

        days = {}

        for item in data:

            day = str(
                item.get("day", "")
            )

            days[day] = {
                "title": item.get(
                    "title",
                    "",
                ),

                "topics": [
                    item.get(
                        "topic",
                        "",
                    )
                ],

                "learning_objectives": [],

                "tools": [],
            }

        return {
            "days": days
        }

    # ------------------------------------------------------------
    # Already dictionary format
    # ------------------------------------------------------------

    return data


# ================================================================
# INTERVIEW API
# ================================================================

@router.post(
    "/interview",
    response_model=InterviewResponse,
)
def interview(
    request: InterviewStartRequest | InterviewTurnRequest,
):
    """
    Main adaptive AI interview endpoint.

    First request:
        InterviewStartRequest

    Following requests:
        InterviewTurnRequest
    """

    # ============================================================
    # GET EXISTING SESSION
    # ============================================================

    session = session_manager.get_session(
        request.sessionId
    )

    # ============================================================
    # START NEW INTERVIEW
    # ============================================================

    if session is None:

        # --------------------------------------------------------
        # First request MUST contain candidate data
        # --------------------------------------------------------

        if not isinstance(
            request,
            InterviewStartRequest,
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "First request must include "
                    "candidate data."
                ),
            )

        # --------------------------------------------------------
        # CREATE SESSION
        # --------------------------------------------------------

        session = session_manager.create_session(
            session_id=request.sessionId,
            candidate=request.candidate,
        )

        try:

            # ====================================================
            # GEMINI
            # ====================================================

            gemini_client = GeminiClient()

            # ====================================================
            # CURRICULUM
            # ====================================================

            curriculum = load_curriculum()

            # ====================================================
            # INTERVIEW PLANNER
            # ====================================================

            planner = InterviewPlanner(
                candidate_profile=request.candidate,
                curriculum=curriculum,
                gemini_client=gemini_client,
            )

            # ----------------------------------------------------
            # Generate interview plan
            # ----------------------------------------------------

            plan = planner.create_plan()

            # ====================================================
            # INTERVIEW MEMORY
            # ====================================================

            memory = InterviewMemory()

            memory.initialize(
                plan
            )

            # ====================================================
            # QUESTION GENERATOR
            # ====================================================

            question_generator = QuestionGenerator(
                gemini_client=gemini_client,
                planner=planner,
                memory=memory,
            )

            # ====================================================
            # EVALUATOR
            # ====================================================

            evaluator = InterviewEvaluator(
                gemini_client=gemini_client,
                memory=memory,
            )

            # ====================================================
            # GENERATE FIRST QUESTION
            # ====================================================

            first_question = (
                question_generator.generate_question()
            )

            # ====================================================
            # STORE EVERYTHING INSIDE SESSION
            # ====================================================
            #
            # THIS IS CRITICAL.
            #
            # All subsequent requests use this SAME session
            # and therefore the SAME memory object.
            #
            # ====================================================

            session.gemini_client = (
                gemini_client
            )

            session.planner = planner

            session.memory = memory

            session.question_generator = (
                question_generator
            )

            session.evaluator = evaluator

            # ----------------------------------------------------
            # Question counter
            # ----------------------------------------------------

            session.question_count = 1

            # ----------------------------------------------------
            # AI reply
            # ----------------------------------------------------

            reply = first_question.question

            # ----------------------------------------------------
            # Store conversation
            # ----------------------------------------------------

            session.messages.append(
                {
                    "role": "assistant",
                    "content": reply,
                }
            )

            # ----------------------------------------------------
            # Return first question
            # ----------------------------------------------------

            return InterviewResponse(
                reply=reply,
                done=False,
            )

        except Exception as e:

            # ----------------------------------------------------
            # Remove broken session
            #
            # If interview initialization fails, don't leave a
            # half-created session in the SessionManager.
            # ----------------------------------------------------

            session_manager.delete_session(
                request.sessionId
            )

            raise HTTPException(
                status_code=500,
                detail=(
                    "Failed to start AI interview: "
                    f"{str(e)}"
                ),
            )

    # ============================================================
    # EXISTING SESSION
    # ============================================================

    # At this point the session already exists.

    if not isinstance(
        request,
        InterviewTurnRequest,
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "This session already exists. "
                "Send a message."
            ),
        )

    # ============================================================
    # CHECK IF INTERVIEW IS ALREADY COMPLETE
    # ============================================================

    if session.done:

        return InterviewResponse(
            reply=(
                "This interview has already "
                "been completed."
            ),
            done=True,
        )

    # ============================================================
    # CONTINUE INTERVIEW
    # ============================================================

    try:

        # ========================================================
        # GET SESSION COMPONENTS
        # ========================================================

        memory = session.memory

        evaluator = session.evaluator

        question_generator = (
            session.question_generator
        )

        gemini_client = (
            session.gemini_client
        )

        # ========================================================
        # SAFETY CHECK
        # ========================================================
        #
        # This prevents:
        #
        # NoneType has no attribute 'add_answer'
        #
        # from appearing as an unexplained error.
        #
        # ========================================================

        if memory is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Interview memory is missing "
                    "for this session. Please start "
                    "a new interview."
                ),
            )

        if evaluator is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Interview evaluator is missing "
                    "for this session. Please start "
                    "a new interview."
                ),
            )

        if question_generator is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Question generator is missing "
                    "for this session. Please start "
                    "a new interview."
                ),
            )

        if gemini_client is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Gemini client is missing "
                    "for this session. Please start "
                    "a new interview."
                ),
            )

        # ========================================================
        # STORE CANDIDATE ANSWER IN MEMORY
        # ========================================================

        memory.add_answer(
            request.message
        )

        # ========================================================
        # GET CURRENT TURN
        # ========================================================

        if not memory.turns:
            raise HTTPException(
                status_code=400,
                detail=(
                    "No interview question exists "
                    "for this session."
                ),
            )

        if memory.current_index < 0:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Invalid interview memory state."
                ),
            )

        if memory.current_index >= len(
            memory.turns
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Interview memory index is invalid."
                ),
            )

        current_turn = memory.turns[
            memory.current_index
        ]

        # ========================================================
        # EVALUATE CANDIDATE ANSWER
        # ========================================================

        evaluation = (
            evaluator.evaluate_answer(
                question=current_turn.question,
                answer=request.message,
                topic=current_turn.topic,
                difficulty=current_turn.difficulty,
            )
        )

        # ========================================================
        # STORE USER MESSAGE
        # ========================================================

        session.messages.append(
            {
                "role": "user",
                "content": request.message,
            }
        )

        # ========================================================
        # FOLLOW-UP FOR WEAK ANSWER
        # ========================================================

        if (
            evaluation.next_action
            == "FOLLOW_UP"
        ):

            followup = (
                gemini_client.generate_followup(
                    original_question=(
                        current_turn.question
                    ),
                    candidate_answer=(
                        request.message
                    ),
                )
            )

            # ----------------------------------------------------
            # Create next turn
            # ----------------------------------------------------

            new_index = (
                memory.current_index + 1
            )

            memory.turns.append(
                InterviewTurn(
                    index=new_index,
                    day=current_turn.day,
                    topic=current_turn.topic,
                    difficulty=current_turn.difficulty,
                    question=followup,
                )
            )

            # ----------------------------------------------------
            # Move memory pointer
            # ----------------------------------------------------

            memory.current_index = new_index

            # ----------------------------------------------------
            # Update question count
            # ----------------------------------------------------

            session.question_count += 1

            # ----------------------------------------------------
            # Store AI follow-up
            # ----------------------------------------------------

            session.messages.append(
                {
                    "role": "assistant",
                    "content": followup,
                }
            )

            # ----------------------------------------------------
            # Return follow-up
            # ----------------------------------------------------

            return InterviewResponse(
                reply=followup,
                done=False,
            )

        # ========================================================
        # GENERATE NEXT AI QUESTION
        # ========================================================

        try:

            next_question = (
                question_generator.generate_question()
            )

        except InterviewCompletedError:

            # ----------------------------------------------------
            # Interview finished
            # ----------------------------------------------------

            session.done = True

            return InterviewResponse(
                reply=(
                    "Thank you. The AI interview "
                    "is now complete."
                ),
                done=True,
                feedback={
                    "summary": (
                        "The candidate completed "
                        "the adaptive technical "
                        "interview."
                    ),

                    "strengths": (
                        evaluation.strengths
                    ),

                    "gaps": (
                        evaluation.weaknesses
                    ),

                    "next": [
                        (
                            "Review the concepts "
                            "discussed during "
                            "the interview."
                        )
                    ],
                },
            )

        # ========================================================
        # STORE NEXT QUESTION
        # ========================================================

        session.question_count += 1

        reply = next_question.question

        session.messages.append(
            {
                "role": "assistant",
                "content": reply,
            }
        )

        # ========================================================
        # RETURN NEXT QUESTION
        # ========================================================

        return InterviewResponse(
            reply=reply,
            done=False,
        )

    # ============================================================
    # ERROR HANDLING
    # ============================================================

    except HTTPException:
        # Don't convert our own HTTP errors into 500.
        raise

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=(
                "Interview processing failed: "
                f"{str(e)}"
            ),
        )











# from fastapi import APIRouter, HTTPException

# from app.core.session_manager import SessionManager
# from app.schemas.interview import (
#     InterviewResponse,
#     InterviewStartRequest,
#     InterviewTurnRequest,
# )


# router = APIRouter(
#     prefix="/api",
#     tags=["Interview"],
# )


# session_manager = SessionManager()


# @router.post(
#     "/interview",
#     response_model=InterviewResponse,
# )
# def interview(
#     request: InterviewStartRequest | InterviewTurnRequest,
# ):
#     session = session_manager.get_session(request.sessionId)

#     # -------------------------------------------------
#     # START NEW INTERVIEW
#     # -------------------------------------------------
#     if session is None:

#         if not isinstance(request, InterviewStartRequest):
#             raise HTTPException(
#                 status_code=400,
#                 detail="First request must include candidate data.",
#             )

#         session = session_manager.create_session(
#             session_id=request.sessionId,
#             candidate=request.candidate,
#         )

#         session.messages.append(
#             {
#                 "role": "assistant",
#                 "content": (
#                     "Welcome to the technical interview. "
#                     "Let's begin with your experience from the AI Cohort."
#                 ),
#             }
#         )

#         session.question_count = 1

#         return InterviewResponse(
#             reply=(
#                 "Welcome to the technical interview. "
#                 "Let's begin with your experience from the AI Cohort."
#             ),
#             done=False,
#         )

#     # -------------------------------------------------
#     # CONTINUE EXISTING INTERVIEW
#     # -------------------------------------------------

#     if not isinstance(request, InterviewTurnRequest):
#         raise HTTPException(
#             status_code=400,
#             detail="This session already exists. Send a message.",
#         )

#     if session.done:
#         return InterviewResponse(
#             reply="This interview has already been completed.",
#             done=True,
#         )

#     # Store candidate answer
#     session.messages.append(
#         {
#             "role": "user",
#             "content": request.message,
#         }
#     )

#     # -------------------------------------------------
#     # TEMPORARY QUESTION LOGIC
#     # -------------------------------------------------
#     #
#     # This is intentionally simple for now.
#     # Member 2 will replace this section with
#     # the actual LLM interviewer.
#     # -------------------------------------------------

#     session.question_count += 1

#     if session.question_count >= 8:

#         session.done = True

#         return InterviewResponse(
#             reply="Thank you. The interview is now complete.",
#             done=True,
#             feedback={
#                 "summary": (
#                     "The candidate completed the technical interview."
#                 ),
#                 "strengths": [
#                     "Completed the interview interaction successfully."
#                 ],
#                 "gaps": [
#                     "Detailed technical assessment will be generated "
#                     "by the interview intelligence layer."
#                 ],
#                 "next": [
#                     "Review the technical concepts covered during the cohort."
#                 ],
#             },
#         )

#     reply = (
#         f"Thank you for your answer. "
#         f"Let's explore another technical topic. "
#         f"This is question {session.question_count}."
#     )

#     session.messages.append(
#         {
#             "role": "assistant",
#             "content": reply,
#         }
#     )

#     return InterviewResponse(
#         reply=reply,
#         done=False,
#     )