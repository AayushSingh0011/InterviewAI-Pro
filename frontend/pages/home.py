"""
pages/home.py
==============
Landing / dashboard page.

- Candidate selection dropdown
- Candidate summary (cohort progress, missions, topics, readiness)
- "Start Interview" CTA -> POST /start (or mock) -> navigate to Interview
"""

import streamlit as st

from config import MOCK_CANDIDATES, start_interview


def render() -> None:
    st.markdown('<div class="page-title">ABTalks AI Interview Agent</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="page-subtitle">Your personalized technical interview based on your AI engineering journey.</div>',
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.4, 1], gap="large")

    with left:
        st.markdown('<div class="section-heading">Select Candidate</div>', unsafe_allow_html=True)

        candidate_ids = list(MOCK_CANDIDATES.keys())
        candidate_labels = {
            cid: f"{MOCK_CANDIDATES[cid]['name']} · {cid}" for cid in candidate_ids
        }

        selected_id = st.selectbox(
            "Select Candidate",
            options=candidate_ids,
            format_func=lambda cid: candidate_labels[cid],
            label_visibility="collapsed",
        )

        candidate = MOCK_CANDIDATES[selected_id]

        st.markdown(
            f"""
            <div class="candidate-card">
                <div class="candidate-name">{candidate['name']}</div>
                <div class="candidate-cohort">{candidate['cohort']}</div>
                <div class="stat-grid">
                    <div class="stat-item">
                        <div class="stat-label">Progress</div>
                        <div class="stat-value">{candidate['completed_days']} / {candidate['total_days']} days</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">Missions</div>
                        <div class="stat-value">{candidate['missions_completed']}</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">Topics</div>
                        <div class="stat-value">{candidate['topics_completed']}</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">Readiness</div>
                        <div class="stat-value">{candidate['readiness']}%</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown('<div class="cta-button">', unsafe_allow_html=True)
        start_clicked = st.button("🚀 Start Interview", type="primary", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

        if start_clicked:
            with st.spinner("Connecting to your AI interviewer..."):
                response = start_interview(selected_id)

            if response:
                st.session_state.candidate_id = selected_id
                st.session_state.session_id = response.get("session_id")
                st.session_state.current_question = response.get("question")
                st.session_state.total_questions = response.get("total_questions", 8)
                st.session_state.question_number = 1
                st.session_state.messages = [
                    {"role": "ai", "content": response.get("question"), "meta": None}
                ]
                st.session_state.interview_started = True
                st.session_state.interview_finished = False
                st.session_state.report_data = None
                st.session_state.page = "Interview"
                st.rerun()

    with right:
        st.markdown('<div class="section-heading">How it works</div>', unsafe_allow_html=True)
        st.markdown(
            """
            <div class="glass-card">
                <p style="color:#94A3B8; font-size:0.92rem; line-height:1.7; margin:0;">
                    1. Pick your candidate profile.<br/>
                    2. The AI interviewer asks questions tailored to your cohort progress.<br/>
                    3. Answer naturally — the AI evaluates each response in real time.<br/>
                    4. After the final question, get a full performance report with a
                    hiring recommendation and radar chart.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )