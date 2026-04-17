"""
deploy.py — Deploy CPAS Meta Ads ke Modal
==========================================
Urutan deterministik:
  1. Load & validasi config
  2. Sync secrets ke Modal
  3. Deploy modal_app.py
  4. Print endpoint URL

Usage:
  python execution/deploy.py
"""
import subprocess
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config_loader import load_config, require

APP_DIR = Path(__file__).parent


def run(cmd: list[str], env: dict | None = None) -> None:
    """Jalankan command dan exit jika gagal."""
    result = subprocess.run(cmd, env=env)
    if result.returncode != 0:
        print(f"[ERROR] Command gagal: {' '.join(cmd)}")
        raise SystemExit(1)


def main() -> None:
    # ── Step 1: Config ────────────────────────────────────────
    print("[1/3] Memuat config ...")
    cfg = load_config()
    require(cfg, "MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET", "META_ACCESS_TOKEN", "API_AUTH_TOKEN", "N8N_WEBHOOK_URL")

    # ALERT_WEBHOOK_URL opsional — kalau kosong, alert akan di-log saja tanpa dikirim
    alert_webhook = cfg.get("ALERT_WEBHOOK_URL", "")

    modal_env = {
        **os.environ,
        "MODAL_TOKEN_ID": cfg["MODAL_TOKEN_ID"],
        "MODAL_TOKEN_SECRET": cfg["MODAL_TOKEN_SECRET"],
    }

    # ── Step 2: Sync secrets ──────────────────────────────────
    print("[2/3] Mensinkronkan secrets ke Modal ...")
    run(
        ["modal", "secret", "create", "--force",
         "meta-ads-token", f"META_ACCESS_TOKEN={cfg['META_ACCESS_TOKEN']}"],
        env=modal_env,
    )
    run(
        ["modal", "secret", "create", "--force",
         "api-auth-token", f"API_AUTH_TOKEN={cfg['API_AUTH_TOKEN']}"],
        env=modal_env,
    )
    run(
        ["modal", "secret", "create", "--force",
         "n8n-webhook-url", f"N8N_WEBHOOK_URL={cfg['N8N_WEBHOOK_URL']}"],
        env=modal_env,
    )
    # alert-webhook-url selalu dibuat (nilai kosong diperbolehkan → alert di-log saja).
    # Modal Secret dengan value kosong tetap valid; modal_app._send_alert akan
    # fallback ke print saat os.environ.get("ALERT_WEBHOOK_URL") falsy.
    run(
        ["modal", "secret", "create", "--force",
         "alert-webhook-url", f"ALERT_WEBHOOK_URL={alert_webhook}"],
        env=modal_env,
    )

    # ── Step 3: Deploy ────────────────────────────────────────
    print("[3/3] Deploying modal_app.py ...")
    run(
        ["modal", "deploy", str(APP_DIR / "modal_app.py")],
        env=modal_env,
    )

    print()
    print("Deploy selesai!")


if __name__ == "__main__":
    main()
