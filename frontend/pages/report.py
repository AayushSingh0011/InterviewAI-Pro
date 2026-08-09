"""
pages/report.py
================
Premium post-interview feedback dashboard:
  - Overall score hero card
  - Performance breakdown (Technical / Communication / Problem Solving)
  - Strength / Weakness cards
  - Hiring recommendation banner
  - Radar chart (Plotly)
"""

import streamlit as st
import plotly.graph_objects as go

from frontend.components.score_card import(
    render_overall_score,
    render_strength_weakness_card,
    render_hiring_recommendation,
)
from components.progress import render_skill_progress
from config import COLORS


def render() -> None:
    report = st.session_state.get("report_data")

    if not report:
        _render_empty_state()
        return

    st.markdown('<div class="page-title">Interview Report</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="page-subtitle">AI-generated feedback from your technical interview.</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="status-badge">✓ Interview Complete</div>',
        unsafe_allow_html=True,
    )
    st.write("")

    # ---------------- Overall score ----------------
    overall = report.get("overall_score", 0)
    render_overall_score(overall, _performance_label(overall))

    # ---------------- Performance breakdown ----------------
    st.markdown('<div class="section-heading">Performance Breakdown</div>', unsafe_allow_html=True)
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)

    render_skill_progress("Technical Skill", report.get("technical_skill", 0), color=COLORS["primary"])
    render_skill_progress("Communication", report.get("communication", 0), color=COLORS["blue"])
    render_skill_progress("Problem Solving", report.get("problem_solving", 0), color=COLORS["secondary"])

    st.markdown("</div>", unsafe_allow_html=True)

    st.write("")

    # ---------------- Strength / Weakness ----------------
    col1, col2 = st.columns(2, gap="medium")
    with col1:
        render_strength_weakness_card(
            "strength",
            report.get("strength", "—"),
            "This came through clearly across your answers and shows a solid foundation to build on.",
        )
    with col2:
        render_strength_weakness_card(
            "weakness",
            report.get("weakness", "—"),
            "Focused practice here will meaningfully raise your overall interview performance.",
        )

    # ---------------- Hiring recommendation ----------------
    render_hiring_recommendation(report.get("hiring_recommendation", "Consider"))

    # ---------------- Radar chart ----------------
    st.markdown('<div class="section-heading">Skill Radar</div>', unsafe_allow_html=True)
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    _render_radar_chart(report)
    st.markdown("</div>", unsafe_allow_html=True)

    st.write("")
    if st.button("🔁 Start a New Interview"):
        for key in [
            "candidate_id", "session_id", "current_question", "question_number",
            "messages", "interview_started", "interview_finished", "report_data",
        ]:
            st.session_state[key] = (
                [] if key == "messages" else
                False if key in ("interview_started", "interview_finished") else
                1 if key == "question_number" else
                None
            )
        st.session_state.page = "Home"
        st.rerun()


def _performance_label(score: int) -> str:
    if score >= 90:
        return "Outstanding Performance"
    if score >= 75:
        return "Strong Performance"
    if score >= 60:
        return "Solid Performance"
    if score >= 40:
        return "Needs Improvement"
    return "Significant Gaps"


def _render_radar_chart(report: dict) -> None:
    categories = [
        "Technical Skill",
        "Communication",
        "Problem Solving",
        "Topic Coverage",
        "Confidence",
    ]
    values = [
        report.get("technical_skill", 0),
        report.get("communication", 0),
        report.get("problem_solving", 0),
        report.get("topic_coverage", report.get("technical_skill", 0)),
        report.get("confidence", report.get("communication", 0)),
    ]

    # close the loop for a smooth radar polygon
    categories_closed = categories + [categories[0]]
    values_closed = values + [values[0]]

    fig = go.Figure()

    fig.add_trace(
        go.Scatterpolar(
            r=values_closed,
            theta=categories_closed,
            fill="toself",
            fillcolor="rgba(139, 92, 246, 0.28)",
            line=dict(color="#8B5CF6", width=2),
            marker=dict(color="#60A5FA", size=6),
            name="Performance",
        )
    )

    fig.update_layout(
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                gridcolor="rgba(148, 163, 184, 0.18)",
                linecolor="rgba(148, 163, 184, 0.18)",
                tickfont=dict(color="#64748B", size=10),
            ),
            angularaxis=dict(
                gridcolor="rgba(148, 163, 184, 0.18)",
                linecolor="rgba(148, 163, 184, 0.18)",
                tickfont=dict(color="#F8FAFC", size=12),
            ),
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#F8FAFC"),
        showlegend=False,
        margin=dict(l=40, r=40, t=30, b=30),
        height=420,
    )

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _render_empty_state() -> None:
    st.markdown('<div class="page-title">Interview Report</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="glass-card" style="text-align:center; padding:3rem 2rem;">
            <div style="font-size:1.1rem; font-weight:700; margin-bottom:0.5rem;">
                No report available yet
            </div>
            <div style="color:#94A3B8; margin-bottom:1.2rem;">
                Complete an interview to see your performance report here.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("🏠 Go to Home", type="primary"):
        st.session_state.page = "Home"
        st.rerun()