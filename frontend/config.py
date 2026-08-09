"""
config.py
=========

Central place for:
  - Backend configuration (BACKEND_URL, USE_MOCK_API)
  - All API calls to the FastAPI backend (start / answer / finish / report)
  - Mock data + mock response generators used while the backend
    is not available yet.

WHY THIS FILE EXISTS
---------------------
The prompt requires a clean separation between UI code and API/backend
logic so a teammate can wire up the real FastAPI backend later without
touching any page or component code.

>>> WHEN YOUR BACKEND IS READY <
1. Set USE_MOCK_API = False below.
2. Update BACKEND_URL to point at your running FastAPI server.
3. That's it — every page already calls the functions in this file
   (start_interview, submit_answer, finish_interview), so nothing in
   pages/ or components/ needs to change.
"""

import time
import random
import requests
import streamlit as st

# ==================================================================
# BACKEND CONFIGURATION
# ==================================================================

BACKEND_URL = "http://localhost:8000"

# Flip this to False once the FastAPI backend is live.
USE_MOCK_API = True

REQUEST_TIMEOUT = 8  # seconds


# ==================================================================
# COLOR PALETTE (single source of truth for the whole app)
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
# MOCK DATA
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
    "Solid answer — consider mentioning trade-offs next time.",
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
# INTERNAL MOCK HELPERS
# ==================================================================

def _mock_start_interview(candidate_id: str) -> dict:
    """Simulate POST /start"""
    time.sleep(0.4)  # tiny delay so the UI feels like it's "thinking"
    return {
        "session_id": f"mock-session-{candidate_id}",
        "question": MOCK_QUESTIONS[0],
        "total_questions": len(MOCK_QUESTIONS),
    }


def _mock_submit_answer(session_id: str, answer: str, question_number: int) -> dict:
    """Simulate POST /answer"""
    time.sleep(0.5)

    score = random.randint(6, 10)
    feedback = random.choice(MOCK_FEEDBACK_POOL)

    next_index = question_number  # question_number is 1-based already answered
    if next_index < len(MOCK_QUESTIONS):
        next_question = MOCK_QUESTIONS[next_index]
    else:
        next_question = None  # signals interview is complete

    return {
        "evaluation": {"score": score, "feedback": feedback},
        "next_question": next_question,
    }


def _mock_finish_interview(session_id: str) -> dict:
    """Simulate POST /finish"""
    time.sleep(0.6)
    return MOCK_REPORT


# ==================================================================
# PUBLIC API — used by pages/components
# ==================================================================

def start_interview(candidate_id: str) -> dict | None:
    """
    Calls POST /start

    Request:  {"candidate_id": "candidate_001"}
    Response: {"session_id": "abc123", "question": "..."}
    """
    if USE_MOCK_API:
        return _mock_start_interview(candidate_id)

    try:
        resp = requests.post(
            f"{BACKEND_URL}/start",
            json={"candidate_id": candidate_id},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        st.error(f"⚠️ Could not reach the interview backend. ({e})")
        return None


def submit_answer(session_id: str, answer: str, question_number: int = 1) -> dict | None:
    """
    Calls POST /answer

    Request:  {"session_id": "abc123", "answer": "..."}
    Response: {"evaluation": {"score": 8, "feedback": "..."}, "next_question": "..."}
    """
    if USE_MOCK_API:
        return _mock_submit_answer(session_id, answer, question_number)

    try:
        resp = requests.post(
            f"{BACKEND_URL}/answer",
            json={"session_id": session_id, "answer": answer},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        st.error(f"⚠️ Could not submit your answer to the backend. ({e})")
        return None


def finish_interview(session_id: str) -> dict | None:
    """
    Calls POST /finish

    Request:  {"session_id": "abc123"}
    Response: {overall_score, technical_skill, communication, problem_solving,
                strength, weakness, hiring_recommendation, ...}
    """
    if USE_MOCK_API:
        return _mock_finish_interview(session_id)

    try:
        resp = requests.post(
            f"{BACKEND_URL}/finish",
            json={"session_id": session_id},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        st.error(f"⚠️ Could not finalize the interview report. ({e})")
        return None


def get_report(session_id: str) -> dict | None:
    """
    Calls GET /report (optional convenience endpoint some backends expose).
    """
    if USE_MOCK_API:
        return MOCK_REPORT

    try:
        resp = requests.get(
            f"{BACKEND_URL}/report",
            params={"session_id": session_id},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        st.error(f"⚠️ Could not fetch the report. ({e})")
        return None