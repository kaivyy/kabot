#!/usr/bin/env python3
import argparse
import hashlib
import json
from pathlib import Path

import requests


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def download_file(url: str, dest_dir: Path, filename: str | None = None, verify_hash: bool = False):
    dest_dir.mkdir(parents=True, exist_ok=True)
    local_name = (filename or url.split("/")[-1] or "downloaded_file").strip()
    dest_path = dest_dir / local_name

    with requests.get(url, stream=True, timeout=30) as r:
        r.raise_for_status()
        with dest_path.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)

    size = dest_path.stat().st_size
    sha256 = None
    if verify_hash:
        sha256 = compute_sha256(dest_path)
    return {
        "path": str(dest_path),
        "size": size,
        "sha256": sha256
    }

def main():
    parser = argparse.ArgumentParser(prog="download-manager", description="Download file dari URL ke workspace Kabot")
    sub = parser.add_subparsers(dest="command", required=True)

    p_download = sub.add_parser("download", help="Download sebuah file dari URL")
    p_download.add_argument("url", help="URL file yang akan di-download")
    p_download.add_argument("dest", nargs="?", default=None, help="Dest filename atau subpath relatif dari dest_dir")
    p_download.add_argument("--dest", dest="dest_dir", default=None, help="Direktori tujuan (default: .kabot/workspace/docs)")
    p_download.add_argument("--hash", dest="verify_hash", action="store_true", help="Verifikasi SHA-256 setelah download")

    p_status = sub.add_parser("status", help="Cek status download terakhir (sederhana)")
    p_status.add_argument("--last", action="store_true", help="Cek status download terakhir (placeholder)")

    args = parser.parse_args()

    # Default destination directory (sesuaikan dengan struktur Kabot kamu)
    base_dest = Path.home() / ".kabot" / "workspace" / "docs"
    dest_dir = Path(args.dest_dir) if args.dest_dir else base_dest

    if args.command == "download":
        result = download_file(args.url, dest_dir, filename=args.dest, verify_hash=bool(args.verify_hash))
        print(json.dumps(result))
    elif args.command == "status":
        # Simple placeholder; bisa dikembangkan untuk track log/metadata
        print(json.dumps({"status": "not_implemented_yet"}))

if __name__ == "__main__":
    main()
