"""
ChaosMesh CLI — Config File Manager.

Config file: ~/.config/chaosmesh/config.toml

[default]
api_key = "cm_live_..."
base_url = "http://localhost:8000"
jwt_token = ""
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

# Try tomllib (Python 3.11+) then tomli backport
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None  # type: ignore

_CONFIG_DIR = Path.home() / ".config" / "chaosmesh"
_CONFIG_FILE = _CONFIG_DIR / "config.toml"


class CLIConfig:
    """Reads and writes the ChaosMesh CLI config file."""

    def __init__(self) -> None:
        self._data: dict = {}
        self._load()

    def _load(self) -> None:
        if _CONFIG_FILE.exists() and tomllib:
            try:
                with open(_CONFIG_FILE, "rb") as f:
                    self._data = tomllib.load(f)
            except Exception:
                self._data = {}

    def _save(self) -> None:
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        # Write TOML manually (no external dep for writing)
        lines = []
        for profile, values in self._data.items():
            lines.append(f"[{profile}]")
            for k, v in values.items():
                if isinstance(v, str):
                    lines.append(f'{k} = "{v}"')
                else:
                    lines.append(f"{k} = {v}")
            lines.append("")
        _CONFIG_FILE.write_text("\n".join(lines), encoding="utf-8")
        # Secure: only readable by owner
        try:
            _CONFIG_FILE.chmod(0o600)
        except Exception:
            pass

    def get(self, key: str, profile: str = "default", fallback: str = "") -> str:
        return self._data.get(profile, {}).get(key, fallback)

    def set(self, key: str, value: str, profile: str = "default") -> None:
        if profile not in self._data:
            self._data[profile] = {}
        self._data[profile][key] = value
        self._save()

    @property
    def api_key(self) -> str:
        return self.get("api_key") or os.getenv("CHAOSMESH_API_KEY", "")

    @property
    def base_url(self) -> str:
        return self.get("base_url") or os.getenv("CHAOSMESH_URL", "http://localhost:8000")

    @property
    def jwt_token(self) -> str:
        return self.get("jwt_token") or os.getenv("CHAOSMESH_JWT", "")

    def save_login(self, api_key: str = "", jwt_token: str = "", base_url: str = "") -> None:
        if api_key:
            self.set("api_key", api_key)
        if jwt_token:
            self.set("jwt_token", jwt_token)
        if base_url:
            self.set("base_url", base_url)

    def logout(self) -> None:
        if "default" in self._data:
            self._data["default"].pop("api_key", None)
            self._data["default"].pop("jwt_token", None)
        self._save()

    @property
    def is_logged_in(self) -> bool:
        return bool(self.api_key or self.jwt_token)

    def make_client(self):
        """Return a configured ChaosMeshClient."""
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "sdk"))
        from chaosmesh_sdk import ChaosMeshClient
        return ChaosMeshClient(
            api_key=self.api_key,
            base_url=self.base_url,
            jwt_token=self.jwt_token,
        )


_cfg: CLIConfig | None = None


def get_config() -> CLIConfig:
    global _cfg
    if _cfg is None:
        _cfg = CLIConfig()
    return _cfg
