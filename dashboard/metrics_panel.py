"""
ChaosMesh Arena — Gradio Metrics Panel + Judge Inject Form (Task 3.4)

Provides:
- Plotly time-series chart for service error rates / P99 latency
- Reward breakdown bar chart (per component)
- Judge inject form: pick scenario + level → POST /demo/inject
"""

from __future__ import annotations

from typing import Any

import plotly.graph_objects as go
from plotly.subplots import make_subplots

_DARK_BG  = "#0f172a"
_PAPER_BG = "#1e293b"
_LINE_COLORS = [
    "#38bdf8", "#818cf8", "#34d399", "#f472b6",
    "#fb923c", "#fbbf24", "#a78bfa",
]


def build_metrics_figure(
    metrics_history: list[dict[str, Any]],
    max_points: int = 60,
) -> go.Figure:
    """
    Build a dual-axis time series:
      - Left Y: error rate (%) for all services
      - Right Y: P99 latency (ms) for all services

    metrics_history: list of step snapshots. Each item is a dict:
        {"step": int, "services": {"svc-name": {"error_rate": x, "p99_latency": y}}}
    """
    if not metrics_history:
        return _empty_fig("No metrics yet — run an episode step")

    # Trim to max_points
    history = metrics_history[-max_points:]
    steps = [h.get("step", i) for i, h in enumerate(history)]

    # Gather all service names
    svc_names: set[str] = set()
    for h in history:
        svc_names.update(h.get("services", {}).keys())
    svc_names_sorted = sorted(svc_names)

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        subplot_titles=("Service Error Rate (%)", "P99 Latency (ms)"),
        vertical_spacing=0.12,
    )

    for i, svc in enumerate(svc_names_sorted):
        color = _LINE_COLORS[i % len(_LINE_COLORS)]
        err_rates = [h.get("services", {}).get(svc, {}).get("error_rate", 0) for h in history]
        p99s = [h.get("services", {}).get(svc, {}).get("p99_latency", 0) for h in history]

        fig.add_trace(go.Scatter(
            x=steps, y=err_rates, name=svc,
            line={"color": color, "width": 2},
            mode="lines",
            legendgroup=svc,
        ), row=1, col=1)

        fig.add_trace(go.Scatter(
            x=steps, y=p99s, name=svc,
            line={"color": color, "width": 2, "dash": "dot"},
            mode="lines",
            legendgroup=svc,
            showlegend=False,
        ), row=2, col=1)

    # Error threshold reference line
    fig.add_hline(y=5.0, line_dash="dash", line_color="#ef4444",
                  annotation_text="5% threshold", row=1, col=1)
    fig.add_hline(y=100.0, line_dash="dash", line_color="#f59e0b",
                  annotation_text="100ms SLO", row=2, col=1)

    fig.update_layout(
        paper_bgcolor=_PAPER_BG,
        plot_bgcolor=_DARK_BG,
        font={"color": "#e2e8f0", "family": "Inter, sans-serif", "size": 11},
        margin={"l": 40, "r": 20, "t": 50, "b": 20},
        legend={"bgcolor": "#1e293b", "bordercolor": "#334155", "font": {"size": 10}},
        height=380,
    )
    for axis in ("xaxis", "xaxis2", "yaxis", "yaxis2"):
        fig.update_layout(**{
            axis: {
                "gridcolor": "#1e293b",
                "linecolor": "#334155",
                "tickfont": {"color": "#94a3b8"},
                "title_font": {"color": "#94a3b8"},
            }
        })
    return fig


def build_reward_chart(reward_history: list[dict[str, float]]) -> go.Figure:
    """
    Bar chart showing cumulative reward breakdown (individual, coordination,
    efficiency, resolution) and total reward line.
    """
    if not reward_history:
        return _empty_fig("No reward data yet")

    history = reward_history[-40:]
    steps = list(range(len(history)))
    components = ["individual", "coordination", "efficiency", "resolution"]
    comp_colors = {"individual": "#38bdf8", "coordination": "#818cf8",
                   "efficiency": "#34d399", "resolution": "#f472b6"}

    fig = go.Figure()

    # Stacked bars for each reward component
    for comp in components:
        vals = [h.get(comp, 0.0) for h in history]
        fig.add_trace(go.Bar(
            x=steps, y=vals, name=comp.capitalize(),
            marker_color=comp_colors[comp], opacity=0.85,
        ))

    # Total reward line
    totals = [h.get("total", 0.0) for h in history]
    fig.add_trace(go.Scatter(
        x=steps, y=totals, name="Total",
        line={"color": "#fbbf24", "width": 2},
        mode="lines+markers",
        marker={"size": 4},
    ))

    fig.update_layout(
        barmode="stack",
        paper_bgcolor=_PAPER_BG,
        plot_bgcolor=_DARK_BG,
        font={"color": "#e2e8f0", "family": "Inter, sans-serif", "size": 11},
        margin={"l": 40, "r": 20, "t": 40, "b": 20},
        title={"text": "Reward Breakdown per Step", "font": {"size": 13, "color": "#94a3b8"}},
        legend={"bgcolor": "#1e293b", "bordercolor": "#334155"},
        height=300,
        xaxis={"gridcolor": "#1e293b", "linecolor": "#334155", "title": "Step"},
        yaxis={"gridcolor": "#1e293b", "linecolor": "#334155", "title": "Reward"},
    )
    return fig


def build_belief_table(agent_beliefs: dict[str, Any]) -> str:
    """Return HTML table of current agent beliefs."""
    if not agent_beliefs:
        return '<div style="color:#64748b;font-size:12px">No agent beliefs recorded yet.</div>'

    rows = []
    for agent, belief in agent_beliefs.items():
        if isinstance(belief, dict):
            confidence = belief.get("confidence", 0)
            hypothesis = belief.get("hypothesis", "")[:120]
        else:
            confidence = getattr(belief, "confidence", 0)
            hypothesis = getattr(belief, "hypothesis", "")[:120]

        conf_color = "#22c55e" if confidence > 0.7 else "#f59e0b" if confidence > 0.4 else "#ef4444"
        rows.append(
            f'<tr>'
            f'<td style="color:#94a3b8;padding:4px 8px;font-size:11px">{agent}</td>'
            f'<td style="color:{conf_color};padding:4px 8px;font-size:11px">{confidence:.0%}</td>'
            f'<td style="color:#e2e8f0;padding:4px 8px;font-size:11px">{hypothesis}</td>'
            f'</tr>'
        )

    header = (
        '<tr style="background:#334155">'
        '<th style="color:#94a3b8;padding:4px 8px;font-size:11px;text-align:left">Agent</th>'
        '<th style="color:#94a3b8;padding:4px 8px;font-size:11px;text-align:left">Confidence</th>'
        '<th style="color:#94a3b8;padding:4px 8px;font-size:11px;text-align:left">Hypothesis</th>'
        '</tr>'
    )
    return (
        '<table style="width:100%;border-collapse:collapse;background:#1e293b;border-radius:8px">'
        + header + "".join(rows) + "</table>"
    )


def _empty_fig(msg: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=msg, x=0.5, y=0.5, xref="paper", yref="paper",
        showarrow=False, font={"size": 13, "color": "#64748b"},
    )
    fig.update_layout(
        paper_bgcolor=_PAPER_BG, plot_bgcolor=_DARK_BG, height=300,
        xaxis={"showgrid": False, "zeroline": False},
        yaxis={"showgrid": False, "zeroline": False},
    )
    return fig
