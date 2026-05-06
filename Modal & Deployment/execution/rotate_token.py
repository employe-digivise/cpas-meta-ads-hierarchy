"""
rotate_token.py — Update Meta Access Token
==========================================
Gunakan saat token expired (~60 hari).

Local mode (laptop):
  Tulis token baru ke .env lokal.

VPS mode (jalankan di VPS sebagai root):
  Tulis token baru ke /root/digivise/cpas-meta-ads/.env, lalu restart service.

Usage:
  python execution/rotate_token.py <NEW_META_TOKEN>
"""
import os
import subprocess
import sys
from pathlib import Path


def _find_env_path() -> Path:
    """Pilih .env path: VPS dulu (kalau jalan di VPS), kalau tidak repo root."""
    vps_path = Path("/root/digivise/cpas-meta-ads/.env")
    if vps_path.exists():
        return vps_path
    repo_root = Path(__file__).resolve().parent.parent.parent
    return repo_root / ".env"


def update_env_value(path: Path, key: str, new_value: str) -> None:
    """Update nilai key di .env in-place. Tambah kalau belum ada."""
    if not path.exists():
        path.write_text(f"{key}={new_value}\n")
        return

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
            updated.append(f"{key}={new_value}")
            found = True
        else:
            updated.append(line)
    if not found:
        updated.append(f"{key}={new_value}")
    path.write_text("\n".join(updated) + "\n")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python rotate_token.py <NEW_META_TOKEN>")
        raise SystemExit(1)

    new_token = sys.argv[1].strip()
    if len(new_token) < 50:
        print("[ERROR] Token terlalu pendek — pastikan token valid.")
        raise SystemExit(1)

    env_path = _find_env_path()
    print(f"[1/2] Menulis token baru ke: {env_path}")
    update_env_value(env_path, "META_ACCESS_TOKEN", new_token)
    print(f"       Token baru: {new_token[:20]}...{new_token[-10:]}")

    # Restart service kalau di VPS dan systemd ada
    if env_path == Path("/root/digivise/cpas-meta-ads/.env"):
        print("[2/2] Restarting cpas-meta-ads service ...")
        result = subprocess.run(
            ["systemctl", "restart", "cpas-meta-ads"],
            env={**os.environ},
        )
        if result.returncode != 0:
            print("[WARN] Gagal restart service. Restart manual: systemctl restart cpas-meta-ads")
    else:
        print("[2/2] Local mode — tidak ada service untuk di-restart.")
        print("       Kalau VPS perlu di-update juga: SSH ke VPS lalu jalankan script ini di sana,")
        print("       atau edit /root/digivise/cpas-meta-ads/.env manual + systemctl restart cpas-meta-ads")

    print()
    print("Token berhasil dirotasi!")
    print("Verifikasi: python execution/test_endpoint.py")


if __name__ == "__main__":
    main()
