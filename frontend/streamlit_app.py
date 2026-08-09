"""
streamlit_app.py
=================
Main entry point for the ABTalks AI Interview Agent frontend.

Run with:
    streamlit run streamlit_app.py

This file owns:
  - Page config (title, icon, layout)
  - Global dark/glassmorphism CSS theme
  - Session state initialization
  - Sidebar navigation + routing to pages/home.py, pages/interview.py,
    pages/report.py

NOTE ON MULTIPAGE STRUCTURE
----------------------------
The project keeps a `pages/` folder (as required) but each file there
exposes a `render()` function instead of relying on Streamlit's native
automatic multipage sidebar. We hide Streamlit's default page nav with
CSS and drive navigation ourselves via `st.session_state.page`, so the
sidebar shows exactly: Home / Interview / Report.
"""

import streamlit as st

from frontend.pages import home, interview, report


# ==================================================================
# PAGE CONFIG
# ==================================================================

st.set_page_config(
    page_title="ABTalks AI Interview",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ==================================================================
# SESSION STATE INITIALIZATION
# ==================================================================

DEFAULT_STATE = {
    "page": "Home",
    "candidate_id": None,
    "session_id": None,
    "current_question": None,
    "question_number": 1,
    "total_questions": 8,
    "messages": [],          # list of {"role": "ai"|"candidate", "content": str, "meta": dict|None}
    "interview_started": False,
    "interview_finished": False,
    "report_data": None,
}

for key, default_value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = default_value


def reset_interview_state() -> None:
    """Wipes interview-specific state, keeps navigation intact. Used for 'Start Over'."""
    for key in [
        "candidate_id", "session_id", "current_question", "question_number",
        "messages", "interview_started", "interview_finished", "report_data",
    ]:
        st.session_state[key] = DEFAULT_STATE[key]


# ==================================================================
# GLOBAL CSS — dark, glassmorphism, purple/blue gradient SaaS theme
# ==================================================================

GLOBAL_CSS = """
<style>

    /* ---------- Hide Streamlit chrome & native multipage nav ---------- */
    [data-testid="stSidebarNav"] { display: none; }
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header[data-testid="stHeader"] { background: transparent; }

    /* ---------- Base ---------- */
    html, body, [data-testid="stAppViewContainer"] {
        background: radial-gradient(circle at 15% 0%, #131a2c 0%, #080B14 45%, #05060b 100%);
        color: #F8FAFC;
        font-family: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
    }

    [data-testid="stAppViewContainer"] > .main {
        max-width: 1200px;
        margin: 0 auto;
    }

    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
        max-width: 1100px;
    }

    /* ---------- Sidebar ---------- */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0B0F1C 0%, #0A0D18 100%);
        border-right: 1px solid rgba(139, 92, 246, 0.15);
    }

    .sidebar-brand {
        font-size: 1.3rem;
        font-weight: 800;
        letter-spacing: -0.02em;
        padding: 0.5rem 0 1.5rem 0;
        background: linear-gradient(90deg, #8B5CF6, #60A5FA);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }

    div[data-testid="stSidebar"] .stButton button {
        width: 100%;
        text-align: left;
        background: transparent;
        border: 1px solid transparent;
        color: #94A3B8;
        font-weight: 600;
        border-radius: 10px;
        padding: 0.6rem 0.9rem;
        margin-bottom: 0.35rem;
        transition: all 0.15s ease;
    }

    div[data-testid="stSidebar"] .stButton button:hover {
        background: rgba(139, 92, 246, 0.12);
        border-color: rgba(139, 92, 246, 0.35);
        color: #F8FAFC;
    }

    div[data-testid="stSidebar"] .stButton button:focus:not(:active) {
        color: #F8FAFC;
    }

    .sidebar-active button {
        background: linear-gradient(90deg, rgba(139,92,246,0.25), rgba(96,165,250,0.10)) !important;
        border-color: rgba(139, 92, 246, 0.55) !important;
        color: #F8FAFC !important;
    }

    .sidebar-footer {
        position: fixed;
        bottom: 1.2rem;
        font-size: 0.72rem;
        color: #475569;
        padding: 0 0.9rem;
    }

    /* ---------- Headings ---------- */
    .page-title {
        font-size: 2.1rem;
        font-weight: 800;
        letter-spacing: -0.02em;
        margin-bottom: 0.15rem;
        background: linear-gradient(90deg, #F8FAFC, #C4B5FD);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }

    .page-subtitle {
        color: #94A3B8;
        font-size: 1.02rem;
        margin-bottom: 1.8rem;
    }

    /* ---------- Generic glass card ---------- */
    .glass-card {
        background: rgba(17, 24, 39, 0.65);
        border: 1px solid rgba(148, 163, 184, 0.12);
        border-radius: 18px;
        padding: 1.5rem 1.7rem;
        backdrop-filter: blur(10px);
        box-shadow: 0 8px 32px rgba(0,0,0,0.35);
    }

    /* ---------- Status badges ---------- */
    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        background: rgba(34, 197, 94, 0.10);
        border: 1px solid rgba(34, 197, 94, 0.35);
        color: #4ADE80;
        font-size: 0.82rem;
        font-weight: 600;
        padding: 0.32rem 0.75rem;
        border-radius: 999px;
    }

    .status-dot {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: #22C55E;
        box-shadow: 0 0 8px 2px rgba(34, 197, 94, 0.6);
        display: inline-block;
        animation: pulse 1.8s infinite;
    }

    @keyframes pulse {
        0%   { opacity: 1; }
        50%  { opacity: 0.35; }
        100% { opacity: 1; }
    }

    /* ---------- Primary CTA button ---------- */
    .stButton > button[kind="primary"], .cta-button button {
        background: linear-gradient(90deg, #8B5CF6, #6366F1) !important;
        border: none !important;
        color: white !important;
        font-weight: 700 !important;
        border-radius: 12px !important;
        padding: 0.75rem 1.4rem !important;
        box-shadow: 0 8px 24px rgba(139, 92, 246, 0.35) !important;
        transition: transform 0.15s ease, box-shadow 0.15s ease !important;
    }

    .stButton > button[kind="primary"]:hover {
        transform: translateY(-1px);
        box-shadow: 0 10px 28px rgba(139, 92, 246, 0.5) !important;
    }

    /* ---------- Candidate summary card ---------- */
    .candidate-card {
        background: linear-gradient(145deg, rgba(139,92,246,0.10), rgba(17,24,39,0.7));
        border: 1px solid rgba(139, 92, 246, 0.25);
        border-radius: 18px;
        padding: 1.6rem 1.8rem;
        margin: 1.2rem 0 1.6rem 0;
    }

    .candidate-name { font-size: 1.35rem; font-weight: 800; }
    .candidate-cohort { color: #A78BFA; font-size: 0.88rem; font-weight: 600; margin-bottom: 1rem; }

    .stat-grid { display: flex; gap: 1.8rem; flex-wrap: wrap; margin-top: 0.4rem; }
    .stat-item { min-width: 110px; }
    .stat-label { color: #94A3B8; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; }
    .stat-value { font-size: 1.3rem; font-weight: 800; color: #F8FAFC; }

    /* ---------- Chat interface ---------- */
    .chat-thread {
        display: flex;
        flex-direction: column;
        gap: 0.9rem;
        max-height: 520px;
        overflow-y: auto;
        padding: 0.4rem 0.2rem 0.8rem 0.2rem;
    }

    .msg-row { display: flex; align-items: flex-end; gap: 0.6rem; }
    .msg-row-ai { justify-content: flex-start; }
    .msg-row-candidate { justify-content: flex-end; }

    .avatar {
        width: 34px; height: 34px;
        border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        font-size: 1rem;
        flex-shrink: 0;
    }
    .avatar-ai { background: rgba(96, 165, 250, 0.18); border: 1px solid rgba(96,165,250,0.4); }
    .avatar-candidate { background: rgba(139, 92, 246, 0.22); border: 1px solid rgba(139,92,246,0.45); }

    .bubble {
        max-width: 62%;
        border-radius: 16px;
        padding: 0.75rem 1rem;
        font-size: 0.95rem;
        line-height: 1.5;
    }

    .bubble-ai {
        background: linear-gradient(145deg, #14192b, #10182b);
        border: 1px solid rgba(96, 165, 250, 0.25);
        border-bottom-left-radius: 4px;
    }

    .bubble-candidate {
        background: linear-gradient(145deg, #241a3d, #1c1533);
        border: 1px solid rgba(139, 92, 246, 0.35);
        border-bottom-right-radius: 4px;
    }

    .bubble-label {
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        color: #94A3B8;
        margin-bottom: 0.25rem;
    }

    .bubble-text { color: #F1F5F9; white-space: pre-wrap; }

    .eval-pill {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        margin-top: 0.6rem;
        background: rgba(34, 197, 94, 0.12);
        border: 1px solid rgba(34, 197, 94, 0.35);
        color: #4ADE80;
        font-size: 0.75rem;
        font-weight: 700;
        padding: 0.25rem 0.6rem;
        border-radius: 999px;
    }

    .eval-dot { width: 6px; height: 6px; border-radius: 50%; background: #22C55E; display: inline-block; }

    /* ---------- Progress bar (interview) ---------- */
    .progress-wrap { margin: 0.6rem 0 1.4rem 0; }
    .progress-header { display: flex; justify-content: space-between; margin-bottom: 0.4rem; }
    .progress-label { font-weight: 700; color: #F8FAFC; font-size: 0.92rem; }
    .progress-pct { color: #A78BFA; font-weight: 700; font-size: 0.92rem; }
    .progress-track {
        width: 100%; height: 10px;
        background: rgba(148, 163, 184, 0.12);
        border-radius: 999px;
        overflow: hidden;
    }
    .progress-fill {
        height: 100%;
        background: linear-gradient(90deg, #8B5CF6, #60A5FA);
        border-radius: 999px;
        transition: width 0.4s ease;
    }

    /* ---------- Skill bars (report) ---------- */
    .skill-bar-wrap { margin-bottom: 1.1rem; }
    .skill-bar-header { display: flex; justify-content: space-between; margin-bottom: 0.35rem; }
    .skill-bar-label { font-weight: 700; font-size: 0.92rem; }
    .skill-bar-score { color: #94A3B8; font-weight: 600; font-size: 0.85rem; }
    .skill-bar-track {
        width: 100%; height: 9px;
        background: rgba(148, 163, 184, 0.12);
        border-radius: 999px;
        overflow: hidden;
    }
    .skill-bar-fill { height: 100%; border-radius: 999px; transition: width 0.5s ease; }

    /* ---------- Score cards ---------- */
    .score-card {
        background: rgba(17, 24, 39, 0.7);
        border: 1px solid rgba(148, 163, 184, 0.12);
        border-top: 3px solid var(--accent, #8B5CF6);
        border-radius: 14px;
        padding: 1.1rem 1.3rem;
        text-align: left;
    }
    .score-card-title { color: #94A3B8; font-size: 0.82rem; font-weight: 600; margin-bottom: 0.3rem; }
    .score-card-value { font-size: 1.9rem; font-weight: 800; color: #F8FAFC; }
    .score-card-max { font-size: 1rem; color: #64748B; font-weight: 600; }
    .score-card-subtitle { color: #64748B; font-size: 0.78rem; margin-top: 0.2rem; }

    /* ---------- Overall score hero card ---------- */
    .overall-score-card {
        background: radial-gradient(circle at 30% 20%, rgba(139,92,246,0.25), transparent 60%),
                    linear-gradient(160deg, #151b31, #0d1122);
        border: 1px solid rgba(139, 92, 246, 0.35);
        border-radius: 22px;
        padding: 2.4rem 2rem;
        text-align: center;
        box-shadow: 0 0 60px rgba(139, 92, 246, 0.15);
        margin-bottom: 1.6rem;
    }
    .overall-score-eyebrow {
        letter-spacing: 0.12em;
        font-size: 0.78rem;
        color: #A78BFA;
        font-weight: 700;
        margin-bottom: 0.6rem;
    }
    .overall-score-value {
        font-size: 4.2rem;
        font-weight: 900;
        background: linear-gradient(90deg, #C4B5FD, #93C5FD);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        line-height: 1;
    }
    .overall-score-max { font-size: 1.6rem; color: #64748B; -webkit-text-fill-color: #64748B; }
    .overall-score-label { margin-top: 0.6rem; font-size: 1.05rem; font-weight: 700; color: #F8FAFC; }

    /* ---------- Strength / Weakness cards ---------- */
    .trait-card {
        border-radius: 16px;
        padding: 1.3rem 1.5rem;
        border: 1px solid rgba(148, 163, 184, 0.12);
        background: rgba(17, 24, 39, 0.65);
        height: 100%;
    }
    .card-strength { border-left: 3px solid #22C55E; }
    .card-weakness { border-left: 3px solid #F59E0B; }
    .trait-eyebrow { font-size: 0.75rem; font-weight: 800; letter-spacing: 0.06em; margin-bottom: 0.5rem; }
    .card-strength .trait-eyebrow { color: #4ADE80; }
    .card-weakness .trait-eyebrow { color: #FBBF24; }
    .trait-title { font-size: 1.15rem; font-weight: 800; margin-bottom: 0.4rem; }
    .trait-desc { color: #94A3B8; font-size: 0.9rem; line-height: 1.5; }

    /* ---------- Hiring recommendation ---------- */
    .recommendation-card {
        border-radius: 18px;
        padding: 1.5rem 1.8rem;
        text-align: center;
        margin: 1.4rem 0;
        border: 1px solid;
    }
    .rec-positive { background: rgba(34, 197, 94, 0.10); border-color: rgba(34, 197, 94, 0.4); }
    .rec-caution { background: rgba(245, 158, 11, 0.10); border-color: rgba(245, 158, 11, 0.4); }
    .rec-negative { background: rgba(239, 68, 68, 0.10); border-color: rgba(239, 68, 68, 0.4); }
    .recommendation-eyebrow { letter-spacing: 0.1em; font-size: 0.75rem; font-weight: 700; color: #94A3B8; margin-bottom: 0.5rem; }
    .recommendation-value { font-size: 1.4rem; font-weight: 800; }
    .rec-positive .recommendation-value { color: #4ADE80; }
    .rec-caution .recommendation-value { color: #FBBF24; }
    .rec-negative .recommendation-value { color: #F87171; }

    /* ---------- Misc ---------- */
    .section-heading {
        font-size: 1.05rem;
        font-weight: 800;
        color: #F8FAFC;
        margin: 1.6rem 0 0.8rem 0;
    }

    hr.soft-divider {
        border: none;
        border-top: 1px solid rgba(148, 163, 184, 0.12);
        margin: 1.6rem 0;
    }

</style>
"""

st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


# ==================================================================
# SIDEBAR NAVIGATION
# ==================================================================

def navigate_to(page_name: str) -> None:
    st.session_state.page = page_name


with st.sidebar:
    st.markdown('<div class="sidebar-brand">🧠 ABTalks AI</div>', unsafe_allow_html=True)

    nav_items = [
        ("Home", "🏠 Home"),
        ("Interview", "🎤 Interview"),
        ("Report", "📊 Report"),
    ]

    for page_key, page_label in nav_items:
        is_active = st.session_state.page == page_key
        wrapper_class = "sidebar-active" if is_active else ""
        st.markdown(f'<div class="{wrapper_class}">', unsafe_allow_html=True)

        # Interview & Report are only reachable once the flow has progressed,
        # but we still allow navigation — pages handle their own empty states.
        if st.button(page_label, key=f"nav_{page_key}", use_container_width=True):
            navigate_to(page_key)
            st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        '<div class="sidebar-footer">ABTalks · 31-Day AI Engineering Cohort<br/>Hackathon Build</div>',
        unsafe_allow_html=True,
    )


# ==================================================================
# ROUTING
# ==================================================================

if st.session_state.page == "Home":
    home.render()
elif st.session_state.page == "Interview":
    interview.render()
elif st.session_state.page == "Report":
    report.render()
else:
    home.render()