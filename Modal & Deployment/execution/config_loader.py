"""
config_loader.py
Baca konfigurasi dari file .env (di repo root atau /root/digivise/cpas-meta-ads/.env di VPS).
Digunakan oleh script CLI (check_token, rotate_token, test_endpoint).
"""

import os
from pathlib import Path


def _candidate_env_paths() -> list[Path]:
    """Lokasi .env yang dicek berurutan. Yang pertama exist akan dipakai."""
    here = Path(__file__).resolve().parent
    return [
        here.parent.parent / ".env",                      # repo_root/.env
        here.parent / ".env",                             # Modal & Deployment/.env
        Path("/root/digivise/cpas-meta-ads/.env"),        # VPS path
    ]


def load_config() -> dict:
    """Load env vars dari .env (kalau ada) lalu merge dengan os.environ.
    os.environ menang — supaya systemd EnvironmentFile bisa override file .env.
    """
    config: dict = {}

    for path in _candidate_env_paths():
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            config[key.strip()] = value.strip().strip('"').strip("'")
        break

    # os.environ mengoverride file .env (untuk systemd / docker)
    for k, v in os.environ.items():
        if v:
            config[k] = v

    return config


def require(config: dict, *keys: str) -> None:
    """Validasi key wajib ada dan tidak kosong. Exit jika ada yang kurang."""
    missing = [k for k in keys if not config.get(k)]
    if missing:
        print("[ERROR] Key berikut wajib diisi di .env: " + ", ".join(missing))
        raise SystemExit(1)
