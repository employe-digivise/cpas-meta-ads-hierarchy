"""
rotate_token.py — Update Meta Access Token
==========================================
Gunakan saat token expired (~60 hari).
Urutan deterministik:
  1. Load config lama
  2. Tulis token baru ke pyvenv.cfg
  3. Sync secret ke Modal
  4. Verifikasi dengan test_endpoint.py

Usage:
  python execution/rotate_token.py <NEW_META_TOKEN>
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config_loader import load_config, require

CFG_PATH = Path(__file__).parent.parent / ".venv" / "pyvenv.cfg"


def update_cfg_value(path: Path, key: str, new_value: str) -> None:
    """Update nilai key di pyvenv.cfg secara in-place."""
    lines = path.read_text().splitlines()
    updated = []
    found = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in stripped:
            updated.append(line)
            continue
        k, _, _ = stripped.partition("=")
        if k.strip() == key:
            # Pertahankan indentasi asli
            indent = line[: len(line) - len(line.lstrip())]
            updated.append(f"{indent}{key:<20} = {new_value}")
            found = True
        else:
            updated.append(line)
    if not found:
        updated.append(f"{key:<20} = {new_value}")
    path.write_text("\n".join(updated) + "\n")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python rotate_token.py <NEW_META_TOKEN>")
        raise SystemExit(1)

    new_token = sys.argv[1].strip()
    if len(new_token) < 50:
        print("[ERROR] Token terlalu pendek — pastikan token valid.")
        raise SystemExit(1)

    # ── Step 1: Load config ──────────────────────────────────
    print("[1/3] Memuat config lama ...")
    cfg = load_config()
    require(cfg, "MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET")

    modal_env = {
        "MODAL_TOKEN_ID": cfg["MODAL_TOKEN_ID"],
        "MODAL_TOKEN_SECRET": cfg["MODAL_TOKEN_SECRET"],
    }

    # ── Step 2: Update pyvenv.cfg ────────────────────────────
    print("[2/3] Mengupdate META_ACCESS_TOKEN di pyvenv.cfg ...")
    update_cfg_value(CFG_PATH, "META_ACCESS_TOKEN", new_token)
    print(f"       Token baru: {new_token[:20]}...{new_token[-10:]}")

    # ── Step 3: Sync secret ke Modal ─────────────────────────
    print("[3/3] Mensinkronkan secret ke Modal ...")
    import os
    full_env = {**os.environ, **modal_env}
    result = subprocess.run(
        ["modal", "secret", "create", "--force",
         "meta-ads-token", f"META_ACCESS_TOKEN={new_token}"],
        env=full_env,
    )
    if result.returncode != 0:
        print("[ERROR] Gagal update secret di Modal.")
        raise SystemExit(1)

    print()
    print("Token berhasil dirotasi!")
    print("Jalankan test: python execution/test_endpoint.py")


if __name__ == "__main__":
    main()
