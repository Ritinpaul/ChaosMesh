"""
ChaosMesh Arena — Main Gradio Dashboard App (Tasks 3.2–3.5)

Full dashboard with:
  Tab 1 — Topology: Plotly K8s cluster graph + incident badges
  Tab 2 — Agent Chat: streamed agent messages + belief table
  Tab 3 — Metrics: error rate / latency charts + reward breakdown
  Tab 4 — Control: judge inject form + curriculum level selector

Connects to the FastAPI server via HTTP polling + WebSocket stream.
Run standalone:  python -m dashboard.app
Or embedded in FastAPI via mount_gradio_app().
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections import deque
from typing import Any

import gradio as gr
import httpx
import plotly.graph_objects as go

from dashboard.metrics_panel import (
    build_belief_table,
    build_metrics_figure,
    build_reward_chart,
)
from dashboard.topology_panel import build_incident_badges, build_topology_figure

# ── Config ────────────────────────────────────────────────────────────────────
API_BASE   = os.environ.get("CHAOSMESH_API_BASE", "http://localhost:8000")
API_KEY    = os.environ.get("CHAOSMESH_API_KEY", "cm_demo_change_me")
POLL_INTERVAL_S = 2.0       # Seconds between state polls
MAX_CHAT_MESSAGES = 200     # Rolling chat buffer size

_HEADERS = {"X-API-Key": API_KEY}

# ── In-memory state (shared across callbacks) ─────────────────────────────────
_state: dict[str, Any] = {
    "episode_id":       None,
    "step":             0,
    "level":            1,
    "cluster":          {},
    "active_incidents": [],
    "agent_beliefs":    {},
    "reward_history":   [],
    "metrics_history":  [],
    "cumulative_reward": 0.0,
    "difficulty_state": {},
}
_chat_buffer: deque[tuple[str, str]] = deque(maxlen=MAX_CHAT_MESSAGES)
_lock = threading.Lock()


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _api_get(path: str) -> dict:
    try:
        r = httpx.get(f"{API_BASE}{path}", headers=_HEADERS, timeout=5.0)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def _api_post(path: str, body: dict) -> dict:
    try:
        print(f"[Dashboard] POST {API_BASE}{path}")  # Debug logging
        print(f"[Dashboard] Body: {body}")
        r = httpx.post(f"{API_BASE}{path}", json=body, headers=_HEADERS, timeout=10.0)
        print(f"[Dashboard] Response: {r.status_code}")
        r.raise_for_status()
        return r.json()
    except Exception as e:
        error_msg = str(e)
        print(f"[Dashboard] ERROR: {error_msg}")  # Debug logging
        return {"error": error_msg}


def _refresh_state() -> None:
    """Poll /env/state and update in-memory state."""
    print("[Dashboard] Refreshing state from API...")  # Debug
    data = _api_get("/env/state")
    if "error" in data or not data:
        print(f"[Dashboard] State refresh error: {data.get('error', 'empty response')}")
        return

    print(f"[Dashboard] State received: episode={data.get('episode_id', '?')[:16]}...")  # Debug
    
    with _lock:
        _state["episode_id"] = data.get("episode_id")
        _state["step"]       = data.get("step", 0)
        _state["cluster"]    = data.get("cluster_state", {})
        _state["active_incidents"] = data.get("active_incidents", [])
        _state["agent_beliefs"]    = data.get("all_beliefs", {})

        level_raw = data.get("current_level", 1)
        if isinstance(level_raw, dict):
            level_raw = level_raw.get("value", 1)
        try:
            _state["level"] = int(level_raw)
        except (TypeError, ValueError):
            _state["level"] = 1
        _state["cumulative_reward"] = data.get("cumulative_reward", 0.0)
        _state["difficulty_state"]  = data.get("difficulty_state", {})

        # Track reward history
        rh = data.get("reward_history", [])
        if rh:
            _state["reward_history"] = rh

        # Build metrics snapshot
        cluster = _state["cluster"]
        svcs = cluster.get("services", {})
        if svcs:
            snap = {
                "step": _state["step"],
                "services": {
                    name: {
                        "error_rate": svc.get("error_rate_percent", 0),
                        "p99_latency": svc.get("p99_latency_ms", 0),
                    }
                    for name, svc in svcs.items()
                },
            }
            hist = _state.get("metrics_history", [])
            hist.append(snap)
            _state["metrics_history"] = hist[-120:]

        # Chat messages (defensive parsing: tolerate non-dict items)
        msgs = data.get("all_messages", [])
        if isinstance(msgs, list):
            for msg in msgs[-20:]:
                if isinstance(msg, dict):
                    sender_obj = msg.get("sender")
                    if isinstance(sender_obj, dict):
                        sender = str(sender_obj.get("value", "?"))
                    else:
                        sender = str(sender_obj or "?")

                    content_obj = msg.get("content")
                    if isinstance(content_obj, dict):
                        content = str(content_obj.get("finding", ""))[:300]
                    else:
                        content = str(content_obj or "")[:300]
                else:
                    sender = "system"
                    content = str(msg)[:300]

                chat_entry = (sender, content)
                if chat_entry not in list(_chat_buffer):
                    _chat_buffer.append(chat_entry)
    
    print(f"[Dashboard] State updated: {len(_state.get('active_incidents', []))} incidents")


# ── Gradio update callbacks ────────────────────────────────────────────────────

def update_topology():
    _refresh_state()
    with _lock:
        cluster  = _state["cluster"]
        incidents = _state["active_incidents"]
    fig    = build_topology_figure(cluster)
    badges = build_incident_badges(incidents)
    return fig, badges


def update_chat():
    with _lock:
        msgs = list(_chat_buffer)
    # Format as list-of-pairs for gr.Chatbot
    formatted = [(f"**{sender}**", content) for sender, content in msgs]
    return formatted


def update_metrics():
    with _lock:
        mh = list(_state.get("metrics_history", []))
        rh = list(_state.get("reward_history", []))
        beliefs = dict(_state.get("agent_beliefs", {}))
    return build_metrics_figure(mh), build_reward_chart(rh), build_belief_table(beliefs)


def update_status_bar():
    print("[Dashboard] Updating status bar...")  # Debug
    with _lock:
        ep    = _state.get("episode_id") or "—"
        step  = _state.get("step", 0)
        lvl   = _state.get("level", 1)
        rew   = _state.get("cumulative_reward", 0.0)
        n_inc = len(_state.get("active_incidents", []))
        diff  = _state.get("difficulty_state", {})
    consec = diff.get("consecutive_successes", 0)
    total  = diff.get("total_episodes", 0)
    
    status_text = (
        f"Episode: `{ep[:12]}…`  |  "
        f"Step: **{step}**  |  "
        f"Level: **L{lvl}**  |  "
        f"Reward: **{rew:.2f}**  |  "
        f"Incidents: **{n_inc}**  |  "
        f"Successes: **{consec}** / needed  |  "
        f"Total episodes: **{total}**"
    )
    print(f"[Dashboard] Status: {status_text[:80]}...")  # Debug
    return status_text


def do_reset(level_int: int):
    print(f"[Dashboard] Reset button clicked! Level: {level_int}")  # Debug
    resp = _api_post("/env/reset", {"level": level_int})
    print(f"[Dashboard] Reset response: {resp.get('episode_id', resp.get('error'))}")  # Debug
    
    if "error" in resp:
        error_msg = f"Reset failed: {resp['error']}"
        print(f"[Dashboard] ERROR: {error_msg}")
        return gr.update(value=f"❌ {error_msg}")
    
    ep_id = resp.get("episode_id", "?")
    _chat_buffer.clear()
    with _lock:
        _state["metrics_history"] = []
        _state["reward_history"]  = []
    
    success_msg = f"✅ Episode started: `{ep_id[:16]}...` at Level {level_int}"
    print(f"[Dashboard] SUCCESS: {success_msg}")
    return success_msg


def do_inject(scenario_key: str, description: str, level_int: int):
    body = {
        "scenario_key": scenario_key,
        "description":  description or scenario_key,
        "level":        level_int,
    }
    resp = _api_post("/demo/inject", body)
    if "error" in resp:
        return f"❌ Inject failed: {resp['error']}"
    return (
        f"✅ Injected: **{resp.get('title', '?')}** (L{resp.get('level', '?')})\n"
        f"Incident ID: `{resp.get('incident_id', '?')}`\n"
        f"Affected: {', '.join(resp.get('affected_pods', []))}"
    )


def fetch_scenarios() -> list[str]:
    resp = _api_get("/demo/scenarios")
    scenarios = resp.get("scenarios", {})
    return list(scenarios.keys()) if scenarios else ["pod_crash", "cascading_db", "ambiguous_attack"]


# ── Dashboard Layout ──────────────────────────────────────────────────────────

THEME = gr.themes.Base(
    primary_hue="indigo",
    secondary_hue="slate",
    neutral_hue="slate",
    font=gr.themes.GoogleFont("Inter"),
).set(
    body_background_fill="#0f172a",
    block_background_fill="#1e293b",
    block_border_color="#334155",
    block_title_text_color="#94a3b8",
    block_label_text_color="#64748b",
    button_primary_background_fill="#4f46e5",
    button_primary_background_fill_hover="#4338ca",
    button_primary_text_color="#ffffff",
    input_background_fill="#0f172a",
    input_border_color="#334155",
    body_text_color="#e2e8f0",
    checkbox_background_color="#1e293b",
)

CSS = """
.gradio-container { background: #0f172a !important; }
.status-bar { background: #1e293b; border: 1px solid #334155; border-radius: 8px;
              padding: 8px 16px; font-size: 13px; color: #94a3b8; margin-bottom: 8px; }
.incident-badges { padding: 8px; }
footer { display: none !important; }
.gr-chatbot { background: #0f172a; }
.gr-chatbot .message { background: #1e293b; border-radius: 8px; }
"""

LEVEL_LABELS = {1: "L1 — Pod Crash", 2: "L2 — Cascade", 3: "L3 — Ambiguous",
                4: "L4 — Dynamic", 5: "L5 — Compound"}

SCENARIO_DESCRIPTIONS = {
    "pod_crash":        "OOM kill and CrashLoopBackOff on pod-api",
    "cascading_db":     "Network partition causing DB → API cascade failure",
    "ambiguous_attack": "Auth anomalies — attack vs. misconfig",
    "dynamic_failure":  "Fixing pod-api breaks pod-cache (Level 4 seed)",
    "compound_chaos":   "DB replication lag + gateway saturation simultaneously",
}


def build_app() -> gr.Blocks:
    with gr.Blocks(title="ChaosMesh Arena") as app:

        # ── Header ────────────────────────────────────────────────────────────
        gr.HTML("""
        <div style="background:#1e293b;border-bottom:1px solid #334155;padding:16px 24px;
                    display:flex;align-items:center;gap:12px">
            <span style="font-size:22px">⚡</span>
            <div>
                <h1 style="margin:0;font-size:18px;color:#e2e8f0;font-weight:700">
                    ChaosMesh Arena
                </h1>
                <p style="margin:0;font-size:12px;color:#64748b">
                    Multi-Agent Adversarial SRE Training · OpenEnv RFC 001/002/003
                </p>
            </div>
        </div>
        """)

        # ── Status bar ────────────────────────────────────────────────────────
        status_md = gr.Markdown(
            "Waiting for episode…",
            elem_classes=["status-bar"],
        )

        with gr.Tabs():

            # ━━ Tab 1: Topology ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            with gr.Tab("🗺️ Topology", id="tab-topology"):
                incident_html = gr.HTML(
                    '<div style="color:#64748b;font-size:13px">No active incidents</div>',
                    elem_classes=["incident-badges"],
                )
                topology_plot = gr.Plot(label="K8s Cluster Topology")
                refresh_topo = gr.Button("🔄 Refresh", size="sm", variant="secondary")
                refresh_topo.click(update_topology, outputs=[topology_plot, incident_html])

            # ━━ Tab 2: Agent Chat ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            with gr.Tab("💬 Agent Chat", id="tab-chat"):
                chatbot = gr.Chatbot(
                    label="Agent Message Stream",
                    height=420,
                )
                with gr.Row():
                    refresh_chat = gr.Button("🔄 Refresh", size="sm", variant="secondary")
                    clear_chat   = gr.Button("🗑️ Clear", size="sm")
                refresh_chat.click(update_chat, outputs=[chatbot])
                clear_chat.click(lambda: [], outputs=[chatbot])

            # ━━ Tab 3: Metrics ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            with gr.Tab("📊 Metrics", id="tab-metrics"):
                metrics_plot = gr.Plot(label="Service Health")
                reward_plot  = gr.Plot(label="Reward Breakdown")
                belief_html  = gr.HTML("<div>No beliefs yet</div>")
                refresh_metrics = gr.Button("🔄 Refresh", size="sm", variant="secondary")
                refresh_metrics.click(
                    update_metrics,
                    outputs=[metrics_plot, reward_plot, belief_html],
                )

            # ━━ Tab 4: Control Panel ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            with gr.Tab("🎮 Control", id="tab-control"):

                # ── Level Selector (Task 3.5) ─────────────────────────────
                gr.Markdown("### Curriculum Level")
                with gr.Row():
                    level_radio = gr.Radio(
                        choices=list(LEVEL_LABELS.values()),
                        value="L1 — Pod Crash",
                        label="Select Difficulty Level",
                        interactive=True,
                    )
                with gr.Row():
                    reset_btn  = gr.Button("▶ Start New Episode", variant="primary", size="lg")
                reset_status = gr.Markdown("")
                level_desc = gr.Markdown(
                    "**L1**: Single-component failure. Straightforward diagnosis and remediation."
                )

                def update_level_desc(choice: str) -> str:
                    descs = {
                        "L1 — Pod Crash":   "**L1**: Single-component failure. Straightforward diagnosis and remediation.",
                        "L2 — Cascade":     "**L2**: Correlated failures — network partition causes cascading DB timeout.",
                        "L3 — Ambiguous":   "**L3**: Ambiguous — could be security attack OR misconfiguration.",
                        "L4 — Dynamic":     "**L4**: Dynamic — fixing one thing breaks another. Second-order effects.",
                        "L5 — Compound":    "**L5**: Compound chaos — 2 simultaneous unrelated incidents. Agents split attention.",
                    }
                    return descs.get(choice, "")

                level_radio.change(update_level_desc, inputs=[level_radio], outputs=[level_desc])

                def _reset_from_choice(choice: str) -> str:
                    lvl = int(choice.split("—")[0].strip().replace("L", ""))
                    return do_reset(lvl)

                reset_btn.click(_reset_from_choice, inputs=[level_radio], outputs=[reset_status])

                gr.Markdown("---")

                # ── Judge Inject Form (Task 3.4) ──────────────────────────
                gr.Markdown("### 🧨 Inject Incident (Judge Mode)")
                gr.Markdown(
                    "*Manually inject a specific incident scenario into the running episode.*"
                )
                with gr.Row():
                    scenario_dd = gr.Dropdown(
                        choices=list(SCENARIO_DESCRIPTIONS.keys()),
                        value="pod_crash",
                        label="Scenario",
                        interactive=True,
                    )
                    inject_level_dd = gr.Dropdown(
                        choices=[1, 2, 3, 4, 5],
                        value=1,
                        label="Level Override",
                        interactive=True,
                    )
                scenario_desc_md = gr.Markdown(
                    f"*{SCENARIO_DESCRIPTIONS['pod_crash']}*"
                )

                def update_scenario_desc(key: str) -> str:
                    return f"*{SCENARIO_DESCRIPTIONS.get(key, '')}*"

                scenario_dd.change(update_scenario_desc, [scenario_dd], [scenario_desc_md])

                custom_desc = gr.Textbox(
                    label="Custom description (optional — overrides scenario preset)",
                    placeholder="e.g. 'slow disk I/O causing write failures on postgres pod'",
                    lines=2,
                )
                inject_btn    = gr.Button("💥 Inject", variant="stop", size="lg")
                inject_status = gr.Markdown("")

                inject_btn.click(
                    do_inject,
                    inputs=[scenario_dd, custom_desc, inject_level_dd],
                    outputs=[inject_status],
                )

                gr.Markdown("---")

                # ── Connection info ───────────────────────────────────────
                gr.Markdown("### 🔗 API Connection")
                gr.Markdown(
                    f"API Base: `{API_BASE}`\n\n"
                    f"WebSocket: `ws://localhost:8000/ws/stream?api_key=...`\n\n"
                    f"Docs: [`/docs`]({API_BASE}/docs)"
                )

        # ── Auto-refresh timer ─────────────────────────────────────────────────
        # Gradio every() — polls every POLL_INTERVAL_S seconds
        gr.on(
            triggers=[app.load],
            fn=update_topology,
            outputs=[topology_plot, incident_html],
        )
        gr.on(
            triggers=[app.load],
            fn=update_metrics,
            outputs=[metrics_plot, reward_plot, belief_html],
        )
        gr.on(
            triggers=[app.load],
            fn=update_status_bar,
            outputs=[status_md],
        )

        # Timer-based auto-refresh (requires Gradio ≥4.x)
        timer = gr.Timer(value=POLL_INTERVAL_S)
        timer.tick(update_topology, outputs=[topology_plot, incident_html])
        timer.tick(update_metrics, outputs=[metrics_plot, reward_plot, belief_html])
        timer.tick(update_status_bar, outputs=[status_md])
        timer.tick(update_chat, outputs=[chatbot])

    return app


def mount_gradio_app(fastapi_app, path: str = "/dashboard") -> None:
    """Mount the Gradio dashboard onto an existing FastAPI app."""
    from gradio.routes import mount_gradio_app as _mount
    dashboard = build_app()
    # Don't queue when mounted (causes WebSocket issues in embedded mode)
    # dashboard.queue()  # Disabled for FastAPI mounting
    _mount(fastapi_app, dashboard, path=path)


if __name__ == "__main__":
    app = build_app()
    app.queue()  # Enable queue for standalone mode
    app.launch(
        server_name="127.0.0.1",
        server_port=int(os.environ.get("GRADIO_PORT", 7861)),
        share=bool(os.environ.get("GRADIO_SHARE", False)),
        favicon_path=None,
    )
