"""ASGI app entrypoint expected by OpenEnv validators."""

from server.main import app, run


def main() -> None:
	"""CLI entrypoint for validators expecting server.app:main."""
	run()


if __name__ == "__main__":
	main()


__all__ = ["app", "main"]
