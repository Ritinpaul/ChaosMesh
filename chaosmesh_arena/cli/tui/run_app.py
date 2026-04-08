"""
ChaosMesh CLI — Run TUI (Textual).

Full-screen terminal dashboard for running an episode interactively.

Layout:
┌─ ChaosMesh Arena ── Level 2 ── ep:abc123456 ─────────── Step 3/50 ──┐
│                                                                       │
│  ┌─ Cluster State ────────────────┐  ┌─ Agent Feed ─────────────┐   │
│  │  pod: auth-svc    ● RUNNING    │  │ [IC] Declaring P2 level  │   │
│  │  pod: payment-svc ✗ CRASH      │  │ [DX] Analyzing logs...   │   │
│  │  pod: api-gw      ● RUNNING    │  │ [RM] Scaling up pods     │   │
│  └────────────────────────────────┘  └──────────────────────────┘   │
│                                                                       │
│  ┌─ Incidents ─────────────────────────────────────────────────┐    │
│  │ 🔴 [P2] OOMKilled — payment-svc                             │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  Score: 38%  Reward: +1.2  MTTR: 2.3m  [r] Replay  [q] Quit         │
└───────────────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Label,
    Log,
    RichLog,
    Static,
)

if TYPE_CHECKING:
    from chaosmesh_sdk import ChaosMeshClient
    from chaosmesh_sdk.models import StepResult

_AGENT_COLOR = {
    "incident_commander": "bright_magenta",
    "diagnostician": "yellow",
    "remediator": "bright_red",
    "security_analyst": "bright_cyan",
    "communicator": "bright_green",
}
_AGENT_SHORT = {
    "incident_commander": "IC",
    "diagnostician": "DX",
    "remediator": "RM",
    "security_analyst": "SA",
    "communicator": "CM",
}
_STATUS_ICON = {
    "RUNNING": "●",
    "CRASH_LOOP_BACK_OFF": "✗",
    "PENDING": "◌",
    "TERMINATING": "⊘",
    "UNKNOWN": "?",
}


class HeroStats(Static):
    """Top-level score/reward stats bar."""

    score: reactive[float] = reactive(0.0)
    step: reactive[int] = reactive(0)
    max_steps: reactive[int] = reactive(50)
    reward: reactive[float] = reactive(0.0)
    cumulative: reactive[float] = reactive(0.0)
    episode_id: reactive[str] = reactive("")

    def render(self) -> str:
        score_pct = int(self.score * 100)
        score_color = "green" if score_pct >= 70 else ("yellow" if score_pct >= 40 else "red")
        ep_short = self.episode_id[:12] + "…" if self.episode_id else "—"
        return (
            f" Episode: [dim]{ep_short}[/dim]  "
            f"Step: [bold]{self.step}[/bold]/{self.max_steps}  "
            f"Score: [{score_color}]{score_pct}%[/{score_color}]  "
            f"Cumulative Reward: [green]{self.cumulative:+.3f}[/green]"
        )


class ClusterPanel(Static):
    """Displays pod/service status table."""

    _obs: dict = {}

    def update_obs(self, obs: dict) -> None:
        self._obs = obs
        self.refresh()

    def render(self) -> str:
        cluster = self._obs.get("cluster", {})
        pods = cluster.get("pods", {})
        if not pods:
            return "[dim]Waiting for cluster data…[/dim]"

        lines = ["[bold dim underline]Pod                  Status       Latency    Err%[/bold dim underline]"]
        for name, data in list(pods.items())[:12]:
            status = data.get("status", "UNKNOWN")
            icon = _STATUS_ICON.get(status, "?")
            status_color = "green" if status == "RUNNING" else "red"
            latency = data.get("latency_ms", 0)
            err_rate = data.get("error_rate", 0) * 100
            short_name = name[:20].ljust(20)
            lines.append(
                f"[{status_color}]{icon}[/{status_color}] {short_name} "
                f"[{status_color}]{status[:12].ljust(12)}[/{status_color}] "
                f"{latency:>7.1f}ms  {err_rate:>5.1f}%"
            )
        return "\n".join(lines)


class IncidentsPanel(Static):
    """Shows active incidents."""

    _obs: dict = {}

    def update_obs(self, obs: dict) -> None:
        self._obs = obs
        self.refresh()

    def render(self) -> str:
        incidents = self._obs.get("incidents", [])
        if not incidents:
            return "[green]✓ No active incidents[/green]"
        lines = []
        for inc in incidents[:5]:
            level = inc.get("level", "?")
            title = inc.get("title", "Unknown incident")
            color = "red" if level in ("P1", "P2") else "yellow"
            lines.append(f"[{color}]🔴 [{level}] {title}[/{color}]")
        return "\n".join(lines)


class ChaosMeshRunApp(App):
    """
    Textual TUI for running a ChaosMesh episode interactively.
    The episode is driven by the LLM agents on the server.
    """

    CSS = """
    Screen {
        background: #0f1117;
    }
    Header {
        background: #1a1d27;
        color: #a78bfa;
        text-style: bold;
    }
    Footer {
        background: #1a1d27;
        color: #94a3b8;
    }
    HeroStats {
        background: #1a1d27;
        border: solid #2a2d3e;
        padding: 0 2;
        height: 3;
        color: #e2e8f0;
    }
    ClusterPanel {
        background: #1a1d27;
        border: solid #2a2d3e;
        border-title-color: #a78bfa;
        padding: 1 2;
        height: 1fr;
        color: #e2e8f0;
    }
    RichLog {
        background: #1a1d27;
        border: solid #2a2d3e;
        border-title-color: #a78bfa;
        padding: 0 1;
        height: 1fr;
    }
    IncidentsPanel {
        background: #12141f;
        border: solid #3b1f3b;
        border-title-color: #f87171;
        padding: 0 2;
        height: 7;
        color: #e2e8f0;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("r", "replay", "Replay", show=True),
        Binding("p", "pause", "Pause/Resume", show=True),
    ]

    def __init__(
        self,
        client: "ChaosMeshClient",
        level: int = 1,
        agent_callable=None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._client = client
        self._level = level
        self._agent_callable = agent_callable
        self._episode_id = ""
        self._paused = False
        self._step_task: asyncio.Task | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield HeroStats(id="stats")
        with Horizontal():
            with Vertical():
                yield ClusterPanel(
                    id="cluster",
                    classes="box",
                )
                yield IncidentsPanel(id="incidents")
            yield RichLog(
                id="agent_feed",
                highlight=True,
                markup=True,
                wrap=True,
            )
        yield Footer()

    def on_mount(self) -> None:
        self.title = f"⚡ ChaosMesh Arena — Level {self._level}"
        self.query_one("#cluster").border_title = " Cluster State "
        self.query_one("#agent_feed").border_title = " Agent Feed "
        self.query_one("#incidents").border_title = " Active Incidents "
        self._step_task = self.set_interval(2.0, self._tick)
        # Start episode
        self.run_worker(self._start_episode(), exclusive=True)

    async def _start_episode(self) -> None:
        feed = self.query_one("#agent_feed", RichLog)
        stats = self.query_one("#stats", HeroStats)

        feed.write("[bold purple]Connecting to ChaosMesh Arena…[/bold purple]")
        try:
            obs, info = await self._client.async_reset(level=self._level)
            self._episode_id = info.get("episode_id", "")
            stats.episode_id = self._episode_id
            self._current_obs = obs
            feed.write(f"[green]✓ Episode started:[/green] [dim]{self._episode_id}[/dim]")
            self._update_panels(obs)
        except Exception as exc:
            feed.write(f"[red]✗ Failed to start: {exc}[/red]")

    def _update_panels(self, obs: dict) -> None:
        self.query_one("#cluster", ClusterPanel).update_obs(obs)
        self.query_one("#incidents", IncidentsPanel).update_obs(obs)

    async def _tick(self) -> None:
        """Called every 2 seconds to advance the episode."""
        if self._paused or not self._episode_id:
            return

        feed = self.query_one("#agent_feed", RichLog)
        stats = self.query_one("#stats", HeroStats)

        try:
            # Build action (use provided callable or deterministic demo action)
            obs = getattr(self, "_current_obs", {})
            if self._agent_callable:
                action = self._agent_callable(obs)
            else:
                action = self._demo_action(obs)

            result = await self._client.async_step(self._episode_id, action)
            self._current_obs = result.observation

            # Update stats
            stats.step += 1
            reward_val = result.reward.total if hasattr(result.reward, "total") else float(result.reward)
            stats.cumulative = getattr(stats, "cumulative", 0.0) + reward_val
            stats.reward = reward_val

            # Log to agent feed
            agent = action.get("agent", "unknown")
            a_short = _AGENT_SHORT.get(agent, "?")
            a_color = _AGENT_COLOR.get(agent, "white")
            action_type = action.get("action_type", "?").replace("_", " ").title()
            target = action.get("target", "") or ""
            rew_color = "green" if reward_val >= 0 else "red"
            feed.write(
                f"[{a_color}][{a_short}][/{a_color}] {action_type}"
                + (f" [dim]{target}[/dim]" if target else "")
                + f"  [{rew_color}]{reward_val:+.3f}[/{rew_color}]"
            )

            self._update_panels(result.observation)

            if result.terminated or result.truncated:
                status = "✓ Resolved" if result.terminated else "⏱ Timed out"
                status_color = "green" if result.terminated else "yellow"
                feed.write(f"\n[bold {status_color}]{status}[/bold {status_color}]  Score: {stats.score:.1%}")
                if self._step_task:
                    self._step_task.stop()

        except Exception as exc:
            feed.write(f"[red dim]Error: {exc}[/red dim]")

    def _demo_action(self, obs: dict) -> dict:
        """Simple deterministic action for demo mode."""
        import random
        agents = ["incident_commander", "diagnostician", "remediator", "security_analyst"]
        types = ["diagnose", "collect_logs", "scale_up", "run_healthcheck", "analyze_metrics"]
        pods = list(obs.get("cluster", {}).get("pods", {}).keys())
        return {
            "agent": random.choice(agents),
            "action_type": random.choice(types),
            "target": random.choice(pods) if pods else "default-service",
            "parameters": {},
            "reasoning": "CLI demo agent",
        }

    def action_pause(self) -> None:
        self._paused = not self._paused
        feed = self.query_one("#agent_feed", RichLog)
        feed.write("[yellow]⏸ Paused[/yellow]" if self._paused else "[green]▶ Resumed[/green]")

    def action_replay(self) -> None:
        if self._episode_id:
            import subprocess
            subprocess.Popen(["chaosmesh", "replay", self._episode_id])
