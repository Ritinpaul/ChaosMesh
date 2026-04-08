"""
ChaosMesh Arena — Gradio Topology Panel (Task 3.2)

Renders the Kubernetes cluster topology as an interactive Plotly network graph.
Nodes = pods/services/nodes, edges = service dependencies.
Color-coded by health status. Refreshes every tick via polling.
"""

from __future__ import annotations

import json
from typing import Any

import plotly.graph_objects as go

# Health status color palette
_STATUS_COLOR = {
    "Running":      "#22c55e",  # green
    "Pending":      "#f59e0b",  # amber
    "Failed":       "#ef4444",  # red
    "CrashLoopBackOff": "#dc2626",
    "OOMKilled":    "#be123c",
    "Unknown":      "#94a3b8",  # slate
    "Terminating":  "#f97316",  # orange
    "Healthy":      "#22c55e",
    "Degraded":     "#f59e0b",
    "Down":         "#ef4444",
    "Ready":        "#22c55e",
    "NotReady":     "#ef4444",
    "MemoryPressure": "#f97316",
    "DiskPressure":   "#f97316",
}

_NODE_TYPE_SYMBOL = {
    "pod":     "circle",
    "service": "diamond",
    "node":    "square",
}

_DARK_BG = "#0f172a"
_PAPER_BG = "#1e293b"


def build_topology_figure(cluster_state: dict[str, Any]) -> go.Figure:
    """
    Build a Plotly scatter-network figure from a ClusterStateSnapshot dict.

    Returns a Plotly Figure ready to embed in a Gradio Plot component.
    """
    if not cluster_state:
        return _empty_figure("No cluster state — reset an episode first")

    pods: dict = cluster_state.get("pods", {})
    services: dict = cluster_state.get("services", {})
    nodes_: dict = cluster_state.get("nodes", {})
    network_partitions: list = cluster_state.get("network_partitions", [])

    # ── Assign positions in a layered layout ─────────────────────────────────
    positions: dict[str, tuple[float, float]] = {}
    all_items: list[tuple[str, str, dict]] = []

    # Layer 0: K8s nodes (bottom)
    n_nodes = len(nodes_)
    for i, (name, nd) in enumerate(nodes_.items()):
        x = (i + 0.5) / max(n_nodes, 1) * 10
        positions[name] = (x, 0.0)
        all_items.append((name, "node", nd))

    # Layer 1: Pods (middle)
    n_pods = len(pods)
    for i, (name, pod) in enumerate(pods.items()):
        x = (i + 0.5) / max(n_pods, 1) * 10
        positions[name] = (x, 3.5)
        all_items.append((name, "pod", pod))

    # Layer 2: Services (top)
    n_svcs = len(services)
    for i, (name, svc) in enumerate(services.items()):
        x = (i + 0.5) / max(n_svcs, 1) * 10
        positions[name] = (name, 7.0)
        # Fix: use numeric x
        positions[name] = ((i + 0.5) / max(n_svcs, 1) * 10, 7.0)
        all_items.append((name, "service", svc))

    # ── Build edge traces (service→pod dependencies) ──────────────────────────
    edge_x: list[float | None] = []
    edge_y: list[float | None] = []

    # Draw pod → node assignment edges
    for pod_name, pod in pods.items():
        node_name = pod.get("node_name")
        if node_name and node_name in positions and pod_name in positions:
            px, py = positions[pod_name]
            nx, ny = positions[node_name]
            edge_x += [px, nx, None]
            edge_y += [py, ny, None]

    # Draw partition edges (dashed red would need shapes; use red edges)
    partition_edges: list[tuple[str, str]] = []
    for p in network_partitions:
        if isinstance(p, (list, tuple)) and len(p) == 2:
            partition_edges.append((str(p[0]), str(p[1])))

    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        mode="lines",
        line={"width": 1, "color": "#475569"},
        hoverinfo="none",
        showlegend=False,
    )

    # ── Build node traces by type ──────────────────────────────────────────────
    traces: list[go.Scatter] = [edge_trace]

    for item_type in ("node", "pod", "service"):
        xs, ys, labels, colors, sizes, hover_texts = [], [], [], [], [], []

        for name, t, data in all_items:
            if t != item_type:
                continue
            if name not in positions:
                continue
            x, y = positions[name]
            xs.append(x)
            ys.append(y)

            # Determine health status
            if item_type == "pod":
                phase = data.get("phase", "Unknown")
                ready = data.get("ready", False)
                restart = data.get("restart_count", 0)
                status_key = phase if ready else ("CrashLoopBackOff" if restart > 2 else phase)
                color = _STATUS_COLOR.get(status_key, "#94a3b8")
                hover = (
                    f"<b>{name}</b><br>"
                    f"Phase: {phase}<br>"
                    f"Ready: {ready}<br>"
                    f"Restarts: {restart}<br>"
                    f"CPU: {data.get('resources', {}).get('cpu_millicores', 0)}m<br>"
                    f"Mem: {data.get('resources', {}).get('memory_mib', 0)}MiB"
                )
                size = 18

            elif item_type == "service":
                err_rate = data.get("error_rate_percent", 0)
                healthy_ep = data.get("healthy_endpoints", 0)
                total_ep = data.get("total_endpoints", 1)
                if err_rate > 20 or healthy_ep == 0:
                    color = _STATUS_COLOR["Down"]
                elif err_rate > 5 or healthy_ep < total_ep:
                    color = _STATUS_COLOR["Degraded"]
                else:
                    color = _STATUS_COLOR["Healthy"]
                hover = (
                    f"<b>{name}</b> [Service]<br>"
                    f"Error rate: {err_rate:.1f}%<br>"
                    f"P99: {data.get('p99_latency_ms', 0):.0f}ms<br>"
                    f"RPS: {data.get('request_rate_rps', 0):.0f}<br>"
                    f"Endpoints: {healthy_ep}/{total_ep}"
                )
                size = 22

            else:  # node
                cond = data.get("condition", "Unknown")
                color = _STATUS_COLOR.get(cond, "#94a3b8")
                hover = (
                    f"<b>{name}</b> [Node]<br>"
                    f"Condition: {cond}<br>"
                    f"CPU: {data.get('cpu_allocatable_millicores', 0)}m available<br>"
                    f"Mem: {data.get('memory_allocatable_mib', 0)}MiB available"
                )
                size = 26

            colors.append(color)
            sizes.append(size)
            hover_texts.append(hover)
            labels.append(name.replace("pod-", "").replace("svc-", "")[:16])

        trace = go.Scatter(
            x=xs, y=ys,
            mode="markers+text",
            marker={
                "size": sizes,
                "color": colors,
                "symbol": _NODE_TYPE_SYMBOL.get(item_type, "circle"),
                "line": {"width": 2, "color": "#334155"},
            },
            text=labels,
            textposition="top center",
            textfont={"size": 9, "color": "#cbd5e1"},
            hovertext=hover_texts,
            hoverinfo="text",
            name=item_type.capitalize() + "s",
        )
        traces.append(trace)

    fig = go.Figure(data=traces)
    fig.update_layout(
        paper_bgcolor=_PAPER_BG,
        plot_bgcolor=_DARK_BG,
        font={"color": "#e2e8f0", "family": "Inter, sans-serif"},
        margin={"l": 10, "r": 10, "t": 40, "b": 10},
        title={
            "text": "K8s Cluster Topology",
            "font": {"size": 14, "color": "#94a3b8"},
        },
        showlegend=True,
        legend={
            "bgcolor": "#1e293b",
            "bordercolor": "#334155",
            "font": {"color": "#94a3b8"},
        },
        xaxis={"showgrid": False, "zeroline": False, "showticklabels": False},
        yaxis={"showgrid": False, "zeroline": False, "showticklabels": False},
        height=400,
    )
    return fig


def build_incident_badges(active_incidents: list[Any]) -> str:
    """Return HTML for incident severity badges."""
    if not active_incidents:
        return '<div style="color:#22c55e;font-size:13px">✅ No active incidents</div>'

    level_colors = {1: "#f59e0b", 2: "#f97316", 3: "#ef4444", 4: "#dc2626", 5: "#be123c"}
    badges = []
    for inc in active_incidents:
        if isinstance(inc, dict):
            inc_data = inc
        elif hasattr(inc, "model_dump"):
            inc_data = inc.model_dump()
        else:
            # Fallback for malformed payload items (e.g., raw ints/strings)
            inc_data = {"level": 1, "title": str(inc), "status": "active"}

        lvl = inc_data.get("level", {})
        if isinstance(lvl, dict):
            lvl = lvl.get("value", 1)
        try:
            lvl_int = int(lvl)
        except (TypeError, ValueError):
            lvl_int = 1

        color = level_colors.get(lvl_int, "#ef4444")
        title = str(inc_data.get("title", "Unknown"))[:50]
        status = str(inc_data.get("status", "active"))
        badges.append(
            f'<span style="background:{color};color:#fff;padding:3px 8px;border-radius:12px;'
            f'font-size:12px;margin:2px;display:inline-block">'
            f'L{lvl_int} {title} [{status}]</span>'
        )
    return "\n".join(badges)


def _empty_figure(msg: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=msg, x=0.5, y=0.5, xref="paper", yref="paper",
        showarrow=False, font={"size": 14, "color": "#64748b"},
    )
    fig.update_layout(
        paper_bgcolor=_PAPER_BG, plot_bgcolor=_DARK_BG, height=400,
        xaxis={"showgrid": False, "zeroline": False},
        yaxis={"showgrid": False, "zeroline": False},
    )
    return fig
