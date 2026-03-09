"""
config_loader.py
Baca semua konfigurasi dari ../.venv/pyvenv.cfg
Digunakan oleh semua script execution agar deterministik.
"""

from pathlib import Path


def load_config() -> dict:
    cfg_path = Path(__file__).parent.parent / ".venv" / "pyvenv.cfg"
    if not cfg_path.exists():
        raise FileNotFoundError(f"Config tidak ditemukan: {cfg_path}")
    config = {}
    for line in cfg_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        config[key.strip()] = value.strip()
    return config


def require(config: dict, *keys: str) -> None:
    """Validasi key wajib ada dan tidak kosong. Exit jika ada yang kurang."""
    missing = [k for k in keys if not config.get(k)]
    if missing:
        print("[ERROR] Key berikut wajib diisi di pyvenv.cfg: " + ", ".join(missing))
        raise SystemExit(1)
