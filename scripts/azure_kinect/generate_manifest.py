#!/usr/bin/env python3
"""Generate and verify SHA-256 file integrity manifests.

Usage:
    # Generate a manifest for all files in a directory
    python generate_manifest.py generate \
        --input-dir data/azure_kinect/processed/K01 \
        --output data/azure_kinect/processed/K01/file_manifest.json

    # Verify files against an existing manifest
    python generate_manifest.py verify \
        --manifest data/azure_kinect/processed/K01/file_manifest.json
"""

from __future__ import annotations
import argparse
import hashlib
import json
import sys
from pathlib import Path
from datetime import datetime, timezone


def compute_sha256(path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            sha.update(chunk)
    return sha.hexdigest()


def generate_manifest(input_dir: Path, output_path: Path) -> dict:
    """Generate a manifest for all files in input_dir (non-recursive)."""
    if not input_dir.exists():
        print(f"ERROR: input directory not found: {input_dir}", file=sys.stderr)
        sys.exit(1)

    files = sorted([p for p in input_dir.iterdir() if p.is_file() and p.name != "file_manifest.json"])

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "directory": str(input_dir),
        "file_count": len(files),
        "files": {},
    }

    for fp in files:
        print(f"  Hashing {fp.name} ...")
        manifest["files"][str(fp)] = compute_sha256(fp)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"\nManifest generated: {output_path}")
    print(f"  {len(files)} files hashed")
    return manifest


def verify_manifest(manifest_path: Path) -> bool:
    """Verify all files in a manifest. Returns True if all pass."""
    if not manifest_path.exists():
        print(f"ERROR: manifest not found: {manifest_path}", file=sys.stderr)
        return False

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    files = manifest.get("files", {})
    if not files:
        print("Manifest contains no files.")
        return True

    print(f"Verifying {len(files)} files from {manifest_path} ...")
    print(f"  Generated at: {manifest.get('generated_at', 'unknown')}")

    ok = 0
    missing = 0
    mismatch = 0

    for fpath_str, expected_hash in files.items():
        fp = Path(fpath_str)
        if not fp.exists():
            print(f"  MISSING: {fp}")
            missing += 1
            continue

        actual = compute_sha256(fp)
        if actual == expected_hash:
            ok += 1
        else:
            print(f"  MISMATCH: {fp}")
            print(f"    expected: {expected_hash}")
            print(f"    actual:   {actual}")
            mismatch += 1

    print(f"\n{'='*60}")
    print(f"  OK:       {ok}")
    print(f"  Missing:  {missing}")
    print(f"  Mismatch: {mismatch}")

    if missing == 0 and mismatch == 0:
        print("RESULT: ALL FILES VERIFIED")
        return True
    else:
        print("RESULT: VERIFICATION FAILED")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate and verify SHA-256 file integrity manifests"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    gen_parser = sub.add_parser("generate", help="Generate a new manifest")
    gen_parser.add_argument("--input-dir", required=True, type=Path)
    gen_parser.add_argument("--output", required=True, type=Path)

    ver_parser = sub.add_parser("verify", help="Verify files against a manifest")
    ver_parser.add_argument("--manifest", required=True, type=Path)

    args = parser.parse_args()

    if args.command == "generate":
        generate_manifest(args.input_dir, args.output)
    elif args.command == "verify":
        ok = verify_manifest(args.manifest)
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
