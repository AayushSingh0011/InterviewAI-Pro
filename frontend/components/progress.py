"""
components/progress.py
=======================
Reusable progress indicators:
  - interview question progress ("Question 3 / 8" + bar)
  - generic skill progress bar (used in the report page)
  - completion percentage helper
"""

import streamlit as st


def completion_percentage(current: int, total: int) -> int:
    """Returns an integer 0-100 percentage, safely handling total=0."""
    if total <= 0:
        return 0
    return max(0, min(100, round((current / total) * 100)))


def render_interview_progress(current_question: int, total_questions: int) -> None:
    """
    Renders the "Question X / Y" label + a gradient progress bar.
    Used at the top of the Interview page.
    """
    pct = completion_percentage(current_question - 1, total_questions)

    st.markdown(
        f"""
        <div class="progress-wrap">
            <div class="progress-header">
                <span class="progress-label">Question {current_question} / {total_questions}</span>
                <span class="progress-pct">{pct}%</span>
            </div>
            <div class="progress-track">
                <div class="progress-fill" style="width:{pct}%;"></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_skill_progress(label: str, score: int, max_score: int = 100, color: str = "#8B5CF6") -> None:
    """
    Renders a labeled skill bar, e.g.

        Technical Skill
        █████████████████░░ 86%

    Used on the Report page for Technical Skill / Communication / Problem Solving.
    """
    pct = completion_percentage(score, max_score)

    st.markdown(
        f"""
        <div class="skill-bar-wrap">
            <div class="skill-bar-header">
                <span class="skill-bar-label">{label}</span>
                <span class="skill-bar-score">{score}/{max_score}</span>
            </div>
            <div class="skill-bar-track">
                <div class="skill-bar-fill" style="width:{pct}%; background:{color};"></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )