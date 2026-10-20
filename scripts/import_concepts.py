#!/usr/bin/env python3
"""Import concept geometry (cubeescape-formgen geometry-spec 1, ``KXnn.geo.json``) into data/concepts/ with its provenance.

The build never touches the network: it reads data/concepts/ only (scripts/tool_assets/concept_spec.py checks every file
against provenance.json). This tool is the one way in:

    python3 scripts/import_concepts.py --zip <claude-geo-claude-vX.zip> --golden <formgen claude/tests/golden.json> \
        --release claude-v0.14 --commit 28aa956 --zip-sha256 <sha256> KG02 [KG05 ...]
    python3 scripts/import_concepts.py --zip <zip> --release claude-v0.14 KG05   # known release: hashes from provenance.json
    python3 scripts/import_concepts.py --check                   # data/concepts/ matches provenance.json

``--zip`` is a local copy of the release asset (download it with ``gh release download <tag> -R
ffunkfabian-hash/cubeescape-formgen -p 'claude-geo-*.zip'``). The zip must have the given sha256, every imported file
the sha256 of formgen's golden list (``golden.json`` › ``geo``, or the release list kept in provenance.json), the format
``cubeescape-design/geometry-spec`` and version 1. Only the named sheets are copied; their bytes stay unchanged.
"""
import argparse
import datetime
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONCEPTS = ROOT / "data" / "concepts"
PROVENANCE = "provenance.json"
FORMAT = "cubeescape-design/geometry-spec"
FORMAT_VERSION = 1
REPOSITORY = "ffunkfabian-hash/cubeescape-formgen"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def read_provenance(folder=CONCEPTS):
    path = folder / PROVENANCE
    return json.loads(path.read_text()) if path.is_file() else None


def write_provenance(record, folder=CONCEPTS):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / PROVENANCE).write_text(json.dumps(record, indent=2, ensure_ascii=False, sort_keys=False) + "\n")


def check(folder=CONCEPTS):
    """Errors of data/concepts/: every imported file present with its sha256 and listed by its release, no file without an
    entry, corrections only for imported sheets."""
    record = read_provenance(folder)
    if record is None:
        return [f"{folder / PROVENANCE} missing"]
    errors = []
    listed = set()
    for sheet, entry in sorted(record["imported"].items()):
        path = folder / entry["file"]
        listed.add(entry["file"])
        release = record["releases"].get(entry["release"])
        if release is None:
            errors.append(f"{sheet}: release {entry['release']} has no provenance")
            continue
        if not path.is_file():
            errors.append(f"{sheet}: {entry['file']} missing")
            continue
        data = path.read_bytes()
        if sha256(data) != entry["sha256"]:
            errors.append(f"{sheet}: sha256 differs from provenance")
        if release["files"].get(sheet) != entry["sha256"]:
            errors.append(f"{sheet}: sha256 differs from the file list of {entry['release']}")
        spec = json.loads(data)
        if (spec.get("format"), spec.get("format_version")) != (FORMAT, FORMAT_VERSION):
            errors.append(f"{sheet}: format {spec.get('format')} {spec.get('format_version')}")
        if spec["sheet"]["id"] != sheet:
            errors.append(f"{sheet}: sheet id {spec['sheet']['id']}")
    for path in folder.glob("*.geo.json"):
        if path.name not in listed:
            errors.append(f"{path.name} has no provenance entry")
    corrections = folder / "corrections.json"
    if corrections.is_file():
        for sheet in json.loads(corrections.read_text())["sheets"]:
            if sheet not in record["imported"]:
                errors.append(f"corrections.json names {sheet}, which is not imported")
    return errors


def import_sheets(zip_path, sheets, release, commit=None, zip_sha256=None, golden=None, today=None, folder=CONCEPTS):
    """Import ``sheets`` from the local release asset ``zip_path`` of ``release``. A release already in provenance.json
    needs nothing else; a new one needs commit, zip sha256 and formgen's golden list. Sheets of other releases keep their
    entries (each sheet names its release). Every requested sheet is checked before anything is written."""
    record = read_provenance(folder) or {
        "format": "toolgen/concepts", "format_version": 1,
        "note": "Concept geometry imported by scripts/import_concepts.py; concept_spec.py refuses a file whose sha256 differs "
                "from its entry. Each sheet names the release it comes from. Never edit the .geo.json files: re-import them.",
        "releases": {}, "imported": {}}
    data = Path(zip_path).read_bytes()
    source = record["releases"].get(release)
    if source is None:
        if not (commit and zip_sha256 and golden):
            raise SystemExit(f"the new release {release} needs --commit, --zip-sha256 and --golden")
        files = dict(sorted(json.loads(Path(golden).read_text())["geo"].items()))
        source = {"repository": REPOSITORY, "former_name": "ffunkfabian-hash/cubeescape-design", "release": release,
                  "commit": commit, "asset": Path(zip_path).name, "asset_sha256": zip_sha256, "asset_bytes": len(data),
                  "asset_folder": "geo/", "asset_files": len(files), "format": FORMAT, "format_version": FORMAT_VERSION,
                  "file_hashes": "claude/tests/golden.json › geo at the commit (equal for every file of the asset)",
                  "files": files}
    if sha256(data) != source["asset_sha256"]:
        raise SystemExit(f"{zip_path}: sha256 {sha256(data)} is not the release asset's {source['asset_sha256']}")
    checked = {}
    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
        if len([name for name in names if name.endswith(".geo.json")]) != source["asset_files"]:
            raise SystemExit(f"{zip_path}: not {source['asset_files']} geo files")
        for sheet in sheets:
            member = f"geo/{sheet}.geo.json"
            if member not in names:
                raise SystemExit(f"{member} not in {zip_path}")
            content = archive.read(member)
            if sha256(content) != source["files"].get(sheet):
                raise SystemExit(f"{member}: sha256 {sha256(content)} is not the golden {source['files'].get(sheet)}")
            spec = json.loads(content)
            if (spec.get("format"), spec.get("format_version")) != (FORMAT, FORMAT_VERSION):
                raise SystemExit(f"{member}: format {spec.get('format')} {spec.get('format_version')}")
            checked[sheet] = (content, spec)
    folder.mkdir(parents=True, exist_ok=True)
    for sheet, (content, spec) in checked.items():          # only now: every requested sheet passed
        (folder / f"{sheet}.geo.json").write_bytes(content)
        record["imported"][sheet] = {"file": f"{sheet}.geo.json", "release": release, "sha256": sha256(content),
                                     "bytes": len(content), "toolgen_id": spec["sheet"]["toolgen_id"],
                                     "variant": spec["sheet"]["variant"], "name_de": spec["sheet"]["name_de"],
                                     "imported": today or datetime.date.today().isoformat()}
    record["releases"][release] = source
    used = {entry["release"] for entry in record["imported"].values()}
    record["releases"] = {name: value for name, value in sorted(record["releases"].items()) if name in used}
    record["imported"] = dict(sorted(record["imported"].items()))
    write_provenance(record, folder)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("sheets", nargs="*")
    parser.add_argument("--zip", type=Path)
    parser.add_argument("--release", help="release tag of the zip (e.g. claude-v0.14)")
    parser.add_argument("--commit")
    parser.add_argument("--zip-sha256")
    parser.add_argument("--golden", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        errors = check()
        print("\n".join(errors) or f"data/concepts OK ({len(read_provenance()['imported'])} sheets)")
        return 1 if errors else 0
    if not args.zip or not args.sheets or not args.release:
        parser.error("--zip, --release and at least one sheet id are needed (or --check)")
    record = import_sheets(args.zip, args.sheets, args.release, args.commit, args.zip_sha256, args.golden)
    print(f"imported {', '.join(args.sheets)} from {args.release} into {CONCEPTS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
