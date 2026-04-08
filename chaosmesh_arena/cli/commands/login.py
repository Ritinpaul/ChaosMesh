"""
ChaosMesh CLI — Login Command.

    chaosmesh login                         # Interactive prompt
    chaosmesh login --api-key cm_live_...   # Non-interactive
    chaosmesh login --url http://myhost:8000
    chaosmesh whoami
    chaosmesh logout
"""

from __future__ import annotations

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from chaosmesh_arena.cli.config import get_config

console = Console()


@click.command("login")
@click.option("--api-key", envvar="CHAOSMESH_API_KEY", help="Your API key (cm_live_...)")
@click.option("--url", default="", help="Server URL (default: http://localhost:8000)")
@click.pass_context
def login_cmd(ctx, api_key: str, url: str):
    """
    Authenticate with ChaosMesh Arena.

    Stores credentials in ~/.config/chaosmesh/config.toml
    """
    cfg = get_config()

    if not api_key:
        console.print(Panel(
            "[bold]Welcome to ChaosMesh Arena![/bold]\n\n"
            "Get an API key: [cyan]POST /auth/register[/cyan]\n"
            "Or visit: [link=https://chaosmesh.io]chaosmesh.io[/link]",
            title="⚡ ChaosMesh Login",
            border_style="purple",
        ))
        api_key = click.prompt("API Key", hide_input=True)

    if not api_key.startswith(("cm_live_", "cm_test_", "cm_")):
        console.print("[yellow]Warning: Key doesn't start with 'cm_live_' — verify it's correct[/yellow]")

    base_url = url or cfg.base_url

    # Verify key works
    console.print(f"Connecting to [cyan]{base_url}[/cyan]...")
    try:
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "sdk"))
        from chaosmesh_sdk import ChaosMeshClient, AuthError, ConnectionError as CMConnErr
        client = ChaosMeshClient(api_key=api_key, base_url=base_url)
        profile = client.get_profile()
        cfg.save_login(api_key=api_key, base_url=base_url)
        console.print(f"[green]✓ Logged in as[/green] [bold]{profile.email}[/bold] (plan: {profile.plan})")
    except Exception as exc:
        console.print(f"[red]✗ Login failed: {exc}[/red]")
        console.print("[dim]Check your API key and server URL, then try again.[/dim]")
        raise SystemExit(1)


@click.command("logout")
def logout_cmd():
    """Clear stored credentials."""
    get_config().logout()
    console.print("[green]Logged out. Credentials cleared.[/green]")


@click.command("whoami")
def whoami_cmd():
    """Show current authenticated user profile."""
    cfg = get_config()
    if not cfg.is_logged_in:
        console.print("[red]Not logged in. Run:[/red] [bold]chaosmesh login[/bold]")
        raise SystemExit(1)

    try:
        client = cfg.make_client()
        profile = client.get_profile()

        t = Table(show_header=False, box=None, padding=(0, 2))
        t.add_row("[dim]Email[/dim]", f"[bold]{profile.email}[/bold]")
        t.add_row("[dim]Display Name[/dim]", profile.display_name)
        t.add_row("[dim]Plan[/dim]", f"[{'green' if profile.plan == 'pro' else 'yellow'}]{profile.plan.upper()}[/]")
        t.add_row("[dim]Episodes (month)[/dim]", str(profile.episodes_this_month))
        t.add_row("[dim]Server[/dim]", cfg.base_url)

        console.print(Panel(t, title="⚡ ChaosMesh Profile", border_style="purple"))
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise SystemExit(1)
