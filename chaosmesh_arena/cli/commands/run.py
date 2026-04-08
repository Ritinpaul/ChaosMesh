"""
ChaosMesh CLI — Run Command.

    chaosmesh run                           # Level 1, TUI
    chaosmesh run --level 3                 # Level 3
    chaosmesh run --no-tui                  # Plain text output
    chaosmesh run --steps 20               # Max 20 steps
    chaosmesh run --agent path/to/agent.py # Custom agent script
"""

from __future__ import annotations

import click
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from chaosmesh_arena.cli.config import get_config

console = Console()


@click.command("run")
@click.option("--level", type=click.IntRange(1, 5), default=1, show_default=True, help="Curriculum level")
@click.option("--steps", type=int, default=50, show_default=True, help="Max episode steps")
@click.option("--no-tui", "no_tui", is_flag=True, help="Plain text output (no Textual TUI)")
@click.option("--agent", "agent_module", type=click.Path(exists=False), default=None,
              help="Path to a Python file with def agent(obs) -> action: ...")
@click.option("--scenario", default=None, help="Pre-built demo scenario key")
def run_cmd(level: int, steps: int, no_tui: bool, agent_module: str | None, scenario: str | None):
    """
    Run a new ChaosMesh episode.

    The server's LLM agents will act by default.
    Provide --agent to inject your own decision function.
    """
    cfg = get_config()
    if not cfg.is_logged_in:
        console.print("[red]Not logged in. Run: chaosmesh login[/red]")
        raise SystemExit(1)

    # Load custom agent if provided
    agent_callable = None
    if agent_module:
        import importlib.util, sys
        spec = importlib.util.spec_from_file_location("_user_agent", agent_module)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if not hasattr(mod, "agent"):
            console.print("[red]Error: agent file must define 'def agent(obs) -> action'[/red]")
            raise SystemExit(1)
        agent_callable = mod.agent
        console.print(f"[green]✓ Custom agent loaded from:[/green] {agent_module}")

    client = cfg.make_client()

    if not no_tui:
        _run_tui(client, level, agent_callable)
    else:
        _run_plain(client, level, steps, agent_callable)


def _run_tui(client, level: int, agent_callable) -> None:
    """Launch the Textual TUI."""
    try:
        from chaosmesh_arena.cli.tui.run_app import ChaosMeshRunApp
        app = ChaosMeshRunApp(client=client, level=level, agent_callable=agent_callable)
        app.run()
    except ImportError:
        console.print(
            "[yellow]Textual not installed. Falling back to plain mode.[/yellow]\n"
            "Install with: [bold]pip install textual[/bold]"
        )
        _run_plain(client, level, 50, agent_callable)
    except Exception as exc:
        console.print(f"[red]TUI error: {exc}[/red]\nFalling back to plain mode...")
        _run_plain(client, level, 50, agent_callable)


def _run_plain(client, level: int, max_steps: int, agent_callable) -> None:
    """Plain-text episode runner (no Textual)."""
    import random

    console.print(Panel(
        f"Level: [bold]{level}[/bold]  Max Steps: {max_steps}",
        title="⚡ ChaosMesh Run",
        border_style="purple",
    ))

    # Reset
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True) as p:
        t = p.add_task("Starting episode…")
        obs, info = client.reset(level=level)
        episode_id = info.get("episode_id", "")
        p.update(t, description=f"Episode started: {episode_id[:16]}…")

    console.print(f"[green]✓[/green] Episode: [dim]{episode_id}[/dim]")

    cumulative = 0.0
    step = 0

    t = Table(show_header=True, header_style="bold dim", show_lines=False)
    t.add_column("#", width=4, justify="right")
    t.add_column("Agent", width=4)
    t.add_column("Action", min_width=18)
    t.add_column("Target", min_width=14)
    t.add_column("Reward", width=10, justify="right")

    agents = ["incident_commander", "diagnostician", "remediator", "security_analyst"]
    action_types = ["diagnose", "collect_logs", "scale_up", "run_healthcheck", "analyze_metrics"]

    for step in range(1, max_steps + 1):
        pods = list(obs.get("cluster", {}).get("pods", {}).keys())
        if agent_callable:
            action = agent_callable(obs)
        else:
            action = {
                "agent": random.choice(agents),
                "action_type": random.choice(action_types),
                "target": random.choice(pods) if pods else "default-service",
                "parameters": {},
                "reasoning": "CLI plain-mode agent",
            }

        result = client.step(episode_id, action)
        obs = result.observation
        reward = result.reward.total if hasattr(result.reward, "total") else float(result.reward)
        cumulative += reward

        rew_str = f"[green]+{reward:.3f}[/green]" if reward >= 0 else f"[red]{reward:.3f}[/red]"
        console.print(
            f"  Step {step:>3}  [{random.choice(['magenta','yellow','red','cyan'])}]"
            f"{action['agent'][:2].upper()}[/]  "
            f"{action['action_type'].replace('_', ' '):18}  "
            f"{(action.get('target','')[:14] or '—'):14}  {rew_str}"
        )

        if result.done:
            break

    status = "✓ Resolved" if result.terminated else "⏱ Timed out"
    status_color = "green" if result.terminated else "yellow"
    from chaosmesh_sdk.database_constants import LEVEL_MAX_REWARD
    score = max(0.0, min(1.0, cumulative / LEVEL_MAX_REWARD.get(level, 25.0)))
    console.print(Panel(
        f"[{status_color}]{status}[/{status_color}]  "
        f"Steps: {step}  "
        f"Cumulative Reward: [bold]{cumulative:+.3f}[/bold]  "
        f"Score: [bold]{'green' if score >= 0.7 else 'yellow'}]{score:.1%}[/bold]",
        title="Episode Complete",
        border_style=status_color,
    ))
    console.print(f"\nReplay: [cyan]chaosmesh replay {episode_id}[/cyan]")
