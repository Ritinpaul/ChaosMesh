"""
ChaosMesh CLI — Root Click Group + Main Entry Point.

    chaosmesh --help
    chaosmesh login
    chaosmesh run --level 2
    chaosmesh leaderboard
    chaosmesh episodes
    chaosmesh replay <episode-id>
    chaosmesh server start/stop/status
"""

from __future__ import annotations

import click
from rich.console import Console

from chaosmesh_arena.cli.commands.login import login_cmd, logout_cmd, whoami_cmd
from chaosmesh_arena.cli.commands.run import run_cmd
from chaosmesh_arena.cli.commands.leaderboard import leaderboard_cmd
from chaosmesh_arena.cli.commands.replay import replay_cmd
from chaosmesh_arena.cli.commands.episodes import episodes_cmd

console = Console()

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"], max_content_width=100)

_ASCII_LOGO = r"""
  ⚡ [bold purple]ChaosMesh Arena[/bold purple]
  [dim]Multi-agent adversarial SRE training[/dim]
"""


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(version="0.2.0", prog_name="chaosmesh")
def cli():
    """
    \b
    ⚡ ChaosMesh Arena — CLI

    Multi-agent adversarial SRE training environment.
    Train AI agents to detect and resolve production incidents.

    \b
    Quick start:
      chaosmesh login              # Authenticate
      chaosmesh run                # Start a Level 1 episode (TUI)
      chaosmesh leaderboard        # See global rankings

    Docs: https://chaosmesh.io/docs/cli
    """
    pass


# ── Commands ───────────────────────────────────────────────────────────────────
cli.add_command(login_cmd, name="login")
cli.add_command(logout_cmd, name="logout")
cli.add_command(whoami_cmd, name="whoami")
cli.add_command(run_cmd, name="run")
cli.add_command(leaderboard_cmd, name="leaderboard")
cli.add_command(replay_cmd, name="replay")
cli.add_command(episodes_cmd, name="episodes")


# ── Server management subgroup ─────────────────────────────────────────────────

@cli.group("server")
def server_group():
    """Start, stop, and manage the ChaosMesh server."""
    pass


@server_group.command("start")
@click.option("--port", default=8000, show_default=True)
@click.option("--host", default="0.0.0.0", show_default=True)
@click.option("--reload", is_flag=True, help="Enable hot-reload (dev only)")
def server_start(port, host, reload):
    """Start the ChaosMesh Arena server."""
    console.print(f"[green]Starting ChaosMesh Arena on {host}:{port}[/green]")
    import uvicorn
    uvicorn.run("server.main:app", host=host, port=port, reload=reload)


@server_group.command("stop")
def server_stop():
    """Send SIGTERM to the running server (Unix only)."""
    import subprocess, sys
    if sys.platform == "win32":
        console.print("[yellow]Use Ctrl+C in the server terminal to stop.[/yellow]")
        return
    result = subprocess.run(["pkill", "-f", "server.main:app"], capture_output=True)
    if result.returncode == 0:
        console.print("[green]Server stopped.[/green]")
    else:
        console.print("[yellow]No server process found.[/yellow]")


@server_group.command("status")
@click.option("--url", default="http://localhost:8000")
def server_status(url):
    """Check if the server is running and healthy."""
    import httpx
    try:
        resp = httpx.get(f"{url}/health", timeout=3.0)
        data = resp.json()
        console.print(
            f"[green]✓ Server online[/green]  "
            f"v{data.get('version', '?')}  "
            f"uptime: {data.get('uptime_seconds', 0):.0f}s"
        )
    except Exception as exc:
        console.print(f"[red]✗ Server offline: {exc}[/red]")


# ── Keys subgroup ──────────────────────────────────────────────────────────────

@cli.group("keys")
def keys_group():
    """Manage your API keys."""
    pass


@keys_group.command("list")
def keys_list():
    """List your active API keys."""
    from chaosmesh_arena.cli.config import get_config
    from rich.table import Table
    from rich import box

    cfg = get_config()
    if not cfg.is_logged_in:
        console.print("[red]Not logged in.[/red]")
        raise SystemExit(1)

    client = cfg.make_client()
    try:
        keys = client.list_api_keys()
    except Exception as exc:
        console.print(f"[red]{exc}[/red]")
        raise SystemExit(1)

    if not keys:
        console.print("[dim]No API keys found.[/dim]")
        return

    t = Table(box=box.ROUNDED, header_style="bold magenta")
    t.add_column("Name")
    t.add_column("Prefix")
    t.add_column("Created")
    t.add_column("Last Used")
    for k in keys:
        t.add_row(k.name, k.key_prefix, k.created_at[:10], k.last_used[:10] if k.last_used else "—")
    console.print(t)


@keys_group.command("revoke")
@click.argument("key_id")
def keys_revoke(key_id):
    """Revoke an API key by its ID."""
    from chaosmesh_arena.cli.config import get_config
    cfg = get_config()
    client = cfg.make_client()
    try:
        client._request("DELETE", f"/auth/keys/{key_id}")
        console.print(f"[green]✓ Key {key_id[:12]}… revoked.[/green]")
    except Exception as exc:
        console.print(f"[red]{exc}[/red]")


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    cli()


if __name__ == "__main__":
    main()
