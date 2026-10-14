#!/usr/bin/env python3
"""Run the Blender-backed Cube Escape tool generator."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from tool_contract import build_tool_contract, validate_contract


TOOLGEN_ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = TOOLGEN_ROOT / "output"
IMPLEMENTED_TOOLS = ("portal_emitter",)
REQUIRED_OUTPUTS = (
    "PortalEmitter.blend",
    "PortalEmitter.fbx",
    "PortalEmitter.glb",
    "PortalEmitter.obj",
    "PortalEmitter.mtl",
    "preview.png",
    "tool_contract.json",
    "qa_geometry.json",
    "manifest.json",
)
REQUIRED_QA_CHECKS = (
    "mesh_closed",
    "positive_volume",
    "finite_coordinates",
    "uvs_valid",
    "meter_scale",
    "front_faces_negative_y",
    "muzzle_in_front_of_grip",
    "fbx_roundtrip",
)


def find_blender(explicit: str | None = None) -> str:
    candidates = [
        explicit,
        os.environ.get("TOOLGEN_BLENDER"),
        shutil.which("blender"),
        "/Applications/Blender.app/Contents/MacOS/Blender",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file() and os.access(candidate, os.X_OK):
            return str(Path(candidate).resolve())
    raise FileNotFoundError(
        "Blender was not found. Set TOOLGEN_BLENDER or pass --blender with the Blender executable path."
    )


def verify_generated_output(output_dir: Path, tool_id: str) -> None:
    missing = [name for name in REQUIRED_OUTPUTS if not (output_dir / name).is_file()]
    if missing:
        raise RuntimeError(f"Blender output is incomplete; missing: {', '.join(missing)}")

    qa = json.loads((output_dir / "qa_geometry.json").read_text(encoding="utf-8"))
    if qa.get("tool_id") != tool_id:
        raise RuntimeError(f"QA report tool_id mismatch: {qa.get('tool_id')!r}")
    checks = qa.get("checks")
    if not isinstance(checks, dict):
        raise RuntimeError("QA report has no checks object")
    failed = [name for name in REQUIRED_QA_CHECKS if checks.get(name) is not True]
    if failed:
        raise RuntimeError(f"Geometry QA failed: {', '.join(failed)}")
    geometry_hash = qa.get("geometry_sha256")
    if (
        not isinstance(geometry_hash, str)
        or len(geometry_hash) != 64
        or any(character not in "0123456789abcdef" for character in geometry_hash)
    ):
        raise RuntimeError("QA report has no valid canonical geometry SHA-256")

    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("tool_id") != tool_id:
        raise RuntimeError(f"Manifest tool_id mismatch: {manifest.get('tool_id')!r}")
    files = manifest.get("files")
    if not isinstance(files, dict):
        raise RuntimeError("Manifest has no files object")
    if manifest.get("geometry", {}).get("sha256") != geometry_hash:
        raise RuntimeError("Manifest geometry checksum does not match the QA report")
    missing_manifest_entries = [name for name in REQUIRED_OUTPUTS if name != "manifest.json" and name not in files]
    if missing_manifest_entries:
        raise RuntimeError(f"Manifest is incomplete: {', '.join(missing_manifest_entries)}")
    for name, expected_hash in files.items():
        if Path(name).name != name:
            raise RuntimeError(f"Manifest contains an unsafe file path: {name}")
        path = output_dir / name
        if not path.is_file():
            raise RuntimeError(f"Manifest references missing output: {name}")
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            raise RuntimeError(f"Output checksum mismatch: {name}")


def install_output(staged_dir: Path, target_dir: Path, force: bool) -> None:
    if target_dir.exists() and not force:
        raise FileExistsError(f"{target_dir} already exists; use --force to replace it.")

    if not target_dir.exists():
        staged_dir.rename(target_dir)
        return

    backup_dir = target_dir.with_name(f".{target_dir.name}.previous")
    if backup_dir.exists():
        raise FileExistsError(f"Refusing to replace existing backup directory: {backup_dir}")
    target_dir.rename(backup_dir)
    try:
        staged_dir.rename(target_dir)
    except OSError:
        backup_dir.rename(target_dir)
        raise
    shutil.rmtree(backup_dir)


def build_tool_package(
    tool_id: str,
    output_root: Path,
    blender: str | None = None,
    force: bool = False,
) -> Path:
    if tool_id not in IMPLEMENTED_TOOLS:
        raise ValueError(f"{tool_id!r} has no Blender generator yet; implemented tools: {', '.join(IMPLEMENTED_TOOLS)}")

    contract = build_tool_contract(tool_id)
    issues = validate_contract(contract)
    if issues:
        raise ValueError(f"invalid contract for {tool_id}: {'; '.join(issues)}")

    output_root = output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    target_dir = output_root / tool_id
    if target_dir.exists() and not force:
        raise FileExistsError(f"{target_dir} already exists; use --force to replace it.")
    blender_executable = find_blender(blender)
    worker = TOOLGEN_ROOT / "blender_worker.py"

    with tempfile.TemporaryDirectory(prefix=f".{tool_id}-", dir=output_root) as temporary:
        staged_dir = Path(temporary) / tool_id
        staged_dir.mkdir()
        contract_path = staged_dir / "tool_contract.json"
        contract_path.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        command = [
            blender_executable,
            "--background",
            "--factory-startup",
            "--python",
            str(worker),
            "--",
            "--contract",
            str(contract_path),
            "--output",
            str(staged_dir),
        ]
        completed = subprocess.run(command, check=False, text=True)
        if completed.returncode != 0:
            raise subprocess.CalledProcessError(completed.returncode, command)

        verify_generated_output(staged_dir, tool_id)
        install_output(staged_dir, target_dir, force)

    return target_dir


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate Cube Escape tool assets with Blender, then run export and geometry QA."
    )
    parser.add_argument("--tool", required=True, choices=IMPLEMENTED_TOOLS, help="Tool generator to run")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output root directory")
    parser.add_argument("--blender", help="Blender executable; defaults to TOOLGEN_BLENDER, PATH, or the macOS app")
    parser.add_argument("--force", action="store_true", help="Replace this tool's previous output after a successful build")
    args = parser.parse_args()

    try:
        package_dir = build_tool_package(args.tool, args.output, args.blender, args.force)
    except (FileNotFoundError, FileExistsError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"toolgen: {error}", file=sys.stderr)
        return 1
    print(f"Generated and verified tool package: {package_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
