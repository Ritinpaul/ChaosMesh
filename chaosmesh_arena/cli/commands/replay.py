"""
ChaosMesh CLI — Replay Command.

    chaosmesh replay <episode-id>           # Print action timeline
    chaosmesh replay <episode-id> --json    # Raw JSON output
    chaosmesh replay <episode-id> --report  # Open HTML report in browser
"""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from chaosmesh_arena.cli.config import get_config

console = Console()

_AGENT_STYLE = {
    "incident_commander": ("purple", "IC"),
    "diagnostician": ("yellow", "DX"),
    "remediator": ("red", "RM"),
    "security_analyst": ("blue", "SA"),
    "communicator": ("green", "CM"),
}


@click.command("replay")
@click.argument("episode_id")
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
@click.option("--report", is_flag=True, help="Open HTML post-mortem in browser (Pro)")
def replay_cmd(episode_id: str, as_json: bool, report: bool):
    """
    Replay a completed episode step by step.

    EPISODE_ID: The ID of a completed episode (from: chaosmesh episodes)
    """
    cfg = get_config()
    if not cfg.is_logged_in:
        console.print("[red]Not logged in. Run: chaosmesh login[/red]")
        raise SystemExit(1)

    client = cfg.make_client()

    try:
        if report:
            # Open HTML report in browser
            url = f"{cfg.base_url}/episodes/{episode_id}/report"
            console.print(f"Opening report in browser: [cyan]{url}[/cyan]")
            import webbrowser
            webbrowser.open(url)
            return

        data = client.get_replay(episode_id)

        if as_json:
            import json
            console.print_json(json.dumps(data, indent=2))
            return

        # Rich table output
        actions = data.get("actions", [])
        score = data.get("score", 0.0)
        total_steps = data.get("total_steps", len(actions))
        level = data.get("level", "?")

        score_color = "green" if score >= 0.7 else ("yellow" if score >= 0.4 else "red")
        header = (
            f"ID: [dim]{episode_id[:16]}…[/dim]  "
            f"Level: {level}  "
            f"Steps: {total_steps}  "
            f"Score: [{score_color}]{score:.1%}[/{score_color}]"
        )
        console.print(Panel(header, title="⚡ Episode Replay", border_style="purple"))

        t = Table(box=box.SIMPLE_HEAD, header_style="bold dim", show_lines=False)
        t.add_column("#", width=4, justify="right")
        t.add_column("Agent", width=4, justify="center")
        t.add_column("Action", min_width=18)
        t.add_column("Target", min_width=16)
        t.add_column("Reward", width=10, justify="right")

        for step in actions:
            agent = str(step.get("agent", ""))
            style, short = _AGENT_STYLE.get(agent, ("white", "??"))
            action_type = str(step.get("action_type", "")).replace("_", " ").title()
            target = str(step.get("target", "—")) or "—"
            raw_reward = step.get("reward", 0.0)
            rew_str = (
                f"[green]+{raw_reward:.3f}[/green]" if raw_reward > 0
                else (f"[red]{raw_reward:.3f}[/red]" if raw_reward < 0 else "[dim]0.000[/dim]")
            )
            t.add_row(
                str(step.get("step", "?")),
                f"[{style}]{short}[/{style}]",
                action_type,
                f"[dim]{target}[/dim]",
                rew_str,
            )

        if actions:
            console.print(t)
        else:
            console.print("[dim]No action log available for this episode.[/dim]")

    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise SystemExit(1)
