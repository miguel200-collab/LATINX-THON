"""Plotly figures for the Streamlit demo (the queue chart and the safety-calculation bars)."""

from __future__ import annotations

import math

import plotly.graph_objects as go

from .erlang import max_stable_intake_minutes, queue_metrics, wait_curve


def queue_chart(
    arrivals_per_hour: float,
    nurses: int,
    manual_minutes: float,
    automated_minutes: float,
) -> go.Figure:
    """Mean triage-queue wait vs. nurse intake time, with the two scenarios marked."""
    limit = max_stable_intake_minutes(arrivals_per_hour, nurses)
    top = max(limit * 0.985, 1.2)
    xs = [1.0 + (top - 1.0) * i / 160 for i in range(161)]
    ys = wait_curve(arrivals_per_hour, nurses, xs)
    ys = [y if math.isfinite(y) else None for y in ys]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", name="Mean queue wait", line=dict(width=3, color="#1d4ed8")))
    for label, minutes, color in (
        ("Manual intake", manual_minutes, "#b91c1c"),
        ("Automated intake", automated_minutes, "#15803d"),
    ):
        m = queue_metrics(arrivals_per_hour, minutes, nurses)
        if m.stable:
            fig.add_trace(go.Scatter(
                x=[minutes], y=[m.wait_minutes], mode="markers+text", name=label,
                text=[f"{m.wait_minutes:.1f} min" if m.wait_minutes >= 1 else f"{m.wait_seconds:.0f} s"],
                textposition="top center", marker=dict(size=12, color=color),
            ))
        else:
            fig.add_trace(go.Scatter(
                x=[min(minutes, top)], y=[0], mode="markers+text", name=f"{label} (queue never clears)",
                text=["unstable"], textposition="top center", marker=dict(size=12, color=color, symbol="x"),
            ))
    fig.add_vline(x=limit, line_dash="dash", line_color="#64748b",
                  annotation_text="utilization 100%", annotation_position="top left")
    fig.update_layout(
        title="Average wait in the triage queue vs. nurse intake time",
        xaxis_title="Intake time per patient (minutes)", yaxis_title="Average wait (minutes)",
        margin=dict(l=40, r=20, t=60, b=40), height=420, legend=dict(orientation="h", y=-0.2),
    )
    return fig


def probability_chart(probabilities: list[float], suggested_tier: int, most_likely_tier: int | None) -> go.Figure:
    """Bar chart of P(ESI 1..5); the suggested review tier is highlighted."""
    tiers = [f"ESI {i}" for i in range(1, 6)]
    colors = ["#b91c1c" if i + 1 == suggested_tier else "#94a3b8" for i in range(5)]
    fig = go.Figure(go.Bar(
        x=tiers, y=[p * 100 for p in probabilities], marker_color=colors,
        text=[f"{p * 100:.0f}%" for p in probabilities], textposition="outside",
    ))
    fig.update_layout(
        title="Probability by ESI tier", yaxis_title="Probability (%)", yaxis_range=[0, 105],
        margin=dict(l=40, r=20, t=60, b=40), height=320,
    )
    return fig


def loss_chart(expected_losses: list[float], suggested_tier: int) -> go.Figure:
    """Expected loss for each possible tier. Lower is safer; the lowest bar is the suggested tier."""
    tiers = [f"ESI {i}" for i in range(1, 6)]
    colors = ["#b91c1c" if i + 1 == suggested_tier else "#94a3b8" for i in range(5)]
    fig = go.Figure(go.Bar(
        x=tiers, y=expected_losses, marker_color=colors,
        text=[f"{x:.2f}" for x in expected_losses], textposition="outside",
    ))
    fig.update_layout(
        title="Expected loss by tier (lower is safer)",
        yaxis_title="Expected loss", margin=dict(l=40, r=20, t=60, b=40), height=320,
    )
    return fig
