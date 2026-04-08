"""
ChaosMesh CLI — Episodes Command.

    chaosmesh episodes                      # List recent episodes
    chaosmesh episodes --level 2            # Filter by level
    chaosmesh episodes --limit 50           # More entries
"""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table
from rich import box

from chaosmesh_arena.cli.config import get_config

console = Console()


@click.command("episodes")
@click.option("--level", type=click.IntRange(1, 5), default=None)
@click.option("--limit", type=int, default=20, show_default=True)
def episodes_cmd(level, limit):
    """List your recent episode history."""
    cfg = get_config()
    if not cfg.is_logged_in:
        console.print("[red]Not logged in. Run: chaosmesh login[/red]")
        raise SystemExit(1)

    client = cfg.make_client()

    try:
        episodes = client.list_episodes(limit=limit, level=level)
    except Exception as exc:
        console.print(f"[red]{exc}[/red]")
        raise SystemExit(1)

    if not episodes:
        console.print("[dim]No episodes yet. Run:[/dim] [bold]chaosmesh run[/bold]")
        return

    t = Table(box=box.ROUNDED, header_style="bold magenta", border_style="dim")
    t.add_column("Episode ID", style="dim", max_width=20)
    t.add_column("Lvl", justify="center", width=5)
    t.add_column("Score", justify="right", width=8)
    t.add_column("Steps", justify="right", width=7)
    t.add_column("MTTR", justify="right", width=8)
    t.add_column("Outcome", justify="center", width=10)
    t.add_column("Date", width=20, style="dim")

    for ep in episodes:
        score_color = "green" if ep.score >= 0.7 else ("yellow" if ep.score >= 0.4 else "red")
        outcome = "[green]Resolved[/green]" if ep.resolved else "[yellow]Timed Out[/yellow]"
        date = ep.created_at[:16].replace("T", " ") if ep.created_at else "—"
        ep_id_short = ep.episode_id[:18] + "…"
        t.add_row(
            ep_id_short,
            str(ep.level),
            f"[{score_color}]{ep.score:.1%}[/{score_color}]",
            str(ep.steps),
            f"{ep.mttr_minutes:.1f}m",
            outcome,
            date,
        )

    console.print(t)
    console.print(f"\n[dim]Replay any episode:[/dim] [bold]chaosmesh replay <episode-id>[/bold]")
