"""
components/score_card.py
=========================
Reusable score / info cards used across Home and Report pages.
"""

import streamlit as st


def render_score_card(title: str, score: int, subtitle: str | None = None, color: str = "#8B5CF6") -> None:
    """
    Small labeled score card, e.g. used for Technical Skill / Communication /
    Problem Solving summary tiles.
    """
    subtitle_html = f'<div class="score-card-subtitle">{subtitle}</div>' if subtitle else ""

    st.markdown(
        f"""
        <div class="score-card" style="--accent:{color};">
            <div class="score-card-title">{title}</div>
            <div class="score-card-value">{score}<span class="score-card-max">/100</span></div>
            {subtitle_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_overall_score(score: int, label: str) -> None:
    """
    The big hero score card at the top of the Report page.
    """
    st.markdown(
        f"""
        <div class="overall-score-card">
            <div class="overall-score-eyebrow">OVERALL SCORE</div>
            <div class="overall-score-value">{score}<span class="overall-score-max">/100</span></div>
            <div class="overall-score-label">{label}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_strength_weakness_card(kind: str, title: str, description: str) -> None:
    """
    kind: "strength" or "weakness"
    """
    if kind == "strength":
        icon, eyebrow, accent_class = "✓", "STRENGTH", "card-strength"
    else:
        icon, eyebrow, accent_class = "⚡", "AREA TO IMPROVE", "card-weakness"

    st.markdown(
        f"""
        <div class="trait-card {accent_class}">
            <div class="trait-eyebrow">{icon} {eyebrow}</div>
            <div class="trait-title">{title}</div>
            <div class="trait-desc">{description}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_hiring_recommendation(recommendation: str) -> None:
    """
    Prominent recommendation banner. Green for positive outcomes,
    amber/red for cautionary ones.
    """
    positive = {"strong hire", "hire", "proceed to technical round"}
    caution = {"consider"}

    rec_lower = recommendation.strip().lower()

    if rec_lower in positive:
        css_class, icon = "rec-positive", "✓"
    elif rec_lower in caution:
        css_class, icon = "rec-caution", "◐"
    else:
        css_class, icon = "rec-negative", "!"

    st.markdown(
        f"""
        <div class="recommendation-card {css_class}">
            <div class="recommendation-eyebrow">HIRING RECOMMENDATION</div>
            <div class="recommendation-value">{icon} {recommendation}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )