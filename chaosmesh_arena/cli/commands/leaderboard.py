"""
ChaosMesh CLI — Leaderboard Command.

    chaosmesh leaderboard                   # Top 10, all-time
    chaosmesh leaderboard --level 2         # Level 2 only
    chaosmesh leaderboard --period week     # This week
    chaosmesh leaderboard --limit 25        # Top 25
    chaosmesh leaderboard --me              # Show my rank
"""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from chaosmesh_arena.cli.config import get_config

console = Console()

_PERIOD_CHOICES = click.Choice(["all_time", "week", "month"], case_sensitive=False)
_MEDAL = {1: "🥇", 2: "🥈", 3: "🥉"}


@click.command("leaderboard")
@click.option("--level", type=click.IntRange(1, 5), default=None, help="Filter by level 1-5")
@click.option("--period", type=_PERIOD_CHOICES, default="all_time", show_default=True)
@click.option("--limit", type=int, default=10, show_default=True, help="Number of entries")
@click.option("--me", is_flag=True, help="Show only your rank")
def leaderboard_cmd(level, period, limit, me):
    """
    Show the ChaosMesh Arena global leaderboard.

    Rankings are by best normalized score [0.0 – 1.0].
    """
    cfg = get_config()
    if not cfg.is_logged_in:
        console.print("[red]Not logged in. Run: chaosmesh login[/red]")
        raise SystemExit(1)

    client = cfg.make_client()

    try:
        if me:
            rank_data = client.get_my_rank(level=level)
            rank = rank_data.get("rank")
            score = rank_data.get("best_score", 0.0)
            total = rank_data.get("total_episodes", 0)
            console.print(Panel(
                f"Global Rank: [bold cyan]{'#' + str(rank) if rank else 'Unranked'}[/bold cyan]\n"
                f"Best Score:  [bold green]{score:.1%}[/bold green]\n"
                f"Episodes:    {total}",
                title="⚡ Your Rank",
                border_style="purple",
            ))
            return

        entries = client.get_leaderboard(level=level, period=period, limit=limit)

        title_parts = ["Global Leaderboard"]
        if level:
            title_parts.append(f"Level {level}")
        title_parts.append(period.replace("_", " ").title())
        title = " · ".join(title_parts)

        t = Table(
            title=f"⚡ {title}",
            box=box.ROUNDED,
            header_style="bold magenta",
            border_style="dim",
        )
        t.add_column("Rank", justify="center", width=6)
        t.add_column("Player", min_width=20)
        t.add_column("Best Score", justify="right")
        t.add_column("Avg Score", justify="right")
        t.add_column("Episodes", justify="right")
        t.add_column("Resolved", justify="right")

        for entry in entries:
            medal = _MEDAL.get(entry.rank, f"#{entry.rank}")
            score_color = "green" if entry.best_score >= 0.7 else ("yellow" if entry.best_score >= 0.4 else "red")
            t.add_row(
                str(medal),
                f"[bold]{entry.display_name}[/bold]",
                f"[{score_color}]{entry.best_score:.1%}[/{score_color}]",
                f"{entry.avg_score:.1%}",
                str(entry.total_episodes),
                str(entry.resolved_count),
            )

        if not entries:
            console.print("[dim]No entries yet. Be the first — run: chaosmesh run[/dim]")
        else:
            console.print(t)

    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise SystemExit(1)
