import time
import random
import requests
import streamlit as st

# ==================================================================
# BACKEND CONFIGURATION
# ==================================================================

BACKEND_URL = "https://interviewai-pro-vwul.onrender.com"
USE_MOCK_API = False
REQUEST_TIMEOUT = 60


# ==================================================================
# COLOR PALETTE
# ==================================================================

COLORS = {
    "background": "#080B14",
    "card": "#111827",
    "primary": "#8B5CF6",
    "secondary": "#6366F1",
    "blue": "#60A5FA",
    "success": "#22C55E",
    "warning": "#F59E0B",
    "danger": "#EF4444",
    "text": "#F8FAFC",
    "muted": "#94A3B8",
}


# ==================================================================
# CANDIDATE DATA
# ==================================================================

MOCK_CANDIDATES = {
    "candidate_001": {
        "candidate_id": "candidate_001",
        "name": "Sujal",
        "cohort": "AI Engineering Cohort",
        "completed_days": 18,
        "total_days": 31,
        "missions_completed": 24,
        "topics_completed": 18,
        "readiness": 82,
    },
    "candidate_002": {
        "candidate_id": "candidate_002",
        "name": "Ananya",
        "cohort": "AI Engineering Cohort",
        "completed_days": 25,
        "total_days": 31,
        "missions_completed": 30,
        "topics_completed": 22,
        "readiness": 91,
    },
    "candidate_003": {
        "candidate_id": "candidate_003",
        "name": "Rohan",
        "cohort": "AI Engineering Cohort",
        "completed_days": 10,
        "total_days": 31,
        "missions_completed": 12,
        "topics_completed": 9,
        "readiness": 58,
    },
}


# ==================================================================
# MOCK DATA
# ==================================================================

MOCK_QUESTIONS = [
    "What is RAG and why would you use it?",
    "How does a vector database work?",
    "What is prompt engineering?",
    "Explain an AI agent.",
    "What problem does MCP solve?",
    "How would you deploy an AI system?",
    "How would you reduce hallucinations?",
    "How would you debug a slow RAG pipeline?",
]

MOCK_FEEDBACK_POOL = [
    "Good explanation, you covered the core concept clearly.",
    "Solid answer - consider mentioning trade-offs next time.",
    "Nice grasp of fundamentals, could go deeper on implementation.",
    "Clear and structured response with good technical vocabulary.",
    "Correct at a high level, add a concrete example to strengthen it.",
]

MOCK_REPORT = {
    "overall_score": 82,
    "technical_skill": 86,
    "communication": 78,
    "problem_solving": 81,
    "topic_coverage": 84,
    "confidence": 76,
    "strength": "Strong AI fundamentals",
    "weakness": "System design depth",
    "hiring_recommendation": "Proceed to Technical Round",
}


# ==================================================================
# MOCK HELPERS
# ==================================================================

def _mock_start_interview(candidate_id: str) -> dict:
    time.sleep(0.4)
    return {
        "session_id": f"mock-session-{candidate_id}",
        "question": MOCK_QUESTIONS[0],
        "total_questions": len(MOCK_QUESTIONS),
    }


def _mock_submit_answer(
    session_id: str,
    answer: str,
    question_number: int
) -> dict:
    time.sleep(0.5)

    score = random.randint(6, 10)
    feedback = random.choice(MOCK_FEEDBACK_POOL)

    next_index = question_number

    if next_index < len(MOCK_QUESTIONS):
        next_question = MOCK_QUESTIONS[next_index]
    else:
        next_question = None

    return {
        "evaluation": {
            "score": score,
            "feedback": feedback,
        },
        "next_question": next_question,
    }


def _mock_finish_interview(session_id: str) -> dict:
    time.sleep(0.6)
    return MOCK_REPORT


# ==================================================================
# PUBLIC API
# ==================================================================

def start_interview(candidate_id: str) -> dict | None:
    """Start interview using the real FastAPI backend."""

    if USE_MOCK_API:
        return _mock_start_interview(candidate_id)

    try:
        candidate = MOCK_CANDIDATES.get(candidate_id)

        if not candidate:
            st.error("Candidate profile not found.")
            return None

        session_id = f"streamlit-{candidate_id}-{int(time.time())}"

        response = requests.post(
            f"{BACKEND_URL}/api/interview",
            json={
                "sessionId": session_id,
                "candidate": candidate,
            },
            timeout=REQUEST_TIMEOUT,
        )

        response.raise_for_status()
        data = response.json()

        return {
            "session_id": session_id,
            "question": data.get("reply", ""),
            "total_questions": 8,
        }

    except requests.exceptions.RequestException as e:
        st.error(f"Could not reach the interview backend. ({e})")
        return None


def submit_answer(
    session_id: str,
    answer: str,
    question_number: int = 1
) -> dict | None:
    """Submit an answer using the real FastAPI backend."""

    if USE_MOCK_API:
        return _mock_submit_answer(
            session_id,
            answer,
            question_number,
        )

    try:
        response = requests.post(
            f"{BACKEND_URL}/api/interview",
            json={
                "sessionId": session_id,
                "message": answer,
            },
            timeout=REQUEST_TIMEOUT,
        )

        response.raise_for_status()
        data = response.json()

        return {
            "evaluation": {
                "score": data.get("feedback", {}).get("overall_score", 0),
                "feedback": data.get("feedback", ""),
            },
            "next_question": data.get("reply"),
            "done": data.get("done", False),
            "backend_feedback": data.get("feedback"),
        }

    except requests.exceptions.RequestException as e:
        st.error(f"Could not submit your answer to the backend. ({e})")
        return None


def finish_interview(session_id: str) -> dict | None:
    """Compatibility function for the existing frontend."""

    if USE_MOCK_API:
        return _mock_finish_interview(session_id)

    return {
        "overall_score": 0,
        "technical_skill": 0,
        "communication": 0,
        "problem_solving": 0,
        "topic_coverage": 0,
        "confidence": 0,
        "strength": "Interview completed",
        "weakness": "Detailed evaluation not yet available",
        "hiring_recommendation": "Review interview feedback",
    }


def get_report(session_id: str) -> dict | None:
    """Compatibility function; backend has no separate /report endpoint."""

    if USE_MOCK_API:
        return MOCK_REPORT

    return None



