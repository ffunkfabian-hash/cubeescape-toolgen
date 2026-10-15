"""Shared content cache of the tool generator (0.4.0): one store for the main checkout, every worktree and output.

Pure Python (no bpy). generate_tools.py keeps the result of every build stage here, named by the stage's content key
(sources, tool data, Blender version, input hashes; see generate_tools.stage_key). Keys never contain paths of a
checkout or an output folder, so a fresh worktree or another --output folder is warm right away.

    TOOLGEN_CACHE            the folder (default ~/Library/Caches/CubeEscapeToolgen/cache,
                             elsewhere $XDG_CACHE_HOME/CubeEscapeToolgen/cache)
    TOOLGEN_CACHE_LIMIT_GB   size limit for prune() (default 4): least recently used entries go first

Layout: <root>/<kind>/<key>/ with entry.json ({"key", "files": {relative path: sha256}, "removed": [...], ...}) and
the files under files/. Rules that keep concurrent runs safe (the same as Robogen's shared cache):
  * writes are atomic: an entry is built under a temp name (".tmp-<pid>-<random>-<key>") and renamed in one step;
    a reader sees a complete entry or none, never half a file; two writers of one key store it exactly once;
  * copies are APFS clones where possible (no extra space, instant), else plain copies;
  * every hit is checked: restore() hashes each restored file against entry.json before anything replaces a file
    in the target folder; a damaged entry is discarded and counts as a miss;
  * nothing deletes an entry because a newer one exists (another checkout may need the older one) - only prune() by
    size, and never an entry used within GRACE_SECONDS (a run elsewhere may be reading it right now);
  * a lookup or restore touches the entry (mtime = last use) - prune() removes the least recently used first.
"""
from __future__ import annotations

import ctypes
import ctypes.util
import hashlib
import json
import os
import shutil
import sys
import time
import uuid
from pathlib import Path

ENV_DIR = "TOOLGEN_CACHE"
ENV_LIMIT = "TOOLGEN_CACHE_LIMIT_GB"
DEFAULT_LIMIT_GB = 4.0
GRACE_SECONDS = 2 * 3600            # a cold full run takes well under that; its entries are never pruned meanwhile
STALE_TMP_SECONDS = 24 * 3600       # temp folders of a crashed run
TMP_PREFIX = ".tmp-"
ENTRY = "entry.json"
FILES = "files"


def default_root() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "CubeEscapeToolgen" / "cache"
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "CubeEscapeToolgen" / "cache"


def root() -> Path:
    configured = os.environ.get(ENV_DIR)
    return Path(configured).expanduser().resolve() if configured else default_root()


def limit_bytes() -> int:
    try:
        gigabytes = float(os.environ.get(ENV_LIMIT, DEFAULT_LIMIT_GB))
    except ValueError:
        gigabytes = DEFAULT_LIMIT_GB
    return int(gigabytes * 1024 ** 3)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def tmp_path(path: Path) -> Path:
    path = Path(path)
    return path.with_name(f"{TMP_PREFIX}{os.getpid()}-{uuid.uuid4().hex[:8]}-{path.name}")


def write_json(path: Path, data) -> None:
    """Atomic JSON write: temp file next to the target, then os.replace."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = tmp_path(path)
    try:
        temporary.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def read_json(path: Path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


_CLONEFILE = None


def _clonefile():
    global _CLONEFILE
    if _CLONEFILE is None:
        _CLONEFILE = False
        if sys.platform == "darwin":
            try:
                libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
                function = libc.clonefile
                function.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
                function.restype = ctypes.c_int
                _CLONEFILE = function
            except (OSError, AttributeError):
                pass
    return _CLONEFILE


def clone(source: Path, destination: Path) -> None:
    """Copy source to a not yet existing destination: an APFS clone where possible, else a copy."""
    function = _clonefile()
    if function and function(os.fsencode(str(source)), os.fsencode(str(destination)), 0) == 0:
        return
    shutil.copyfile(source, destination)


def clone_tree(source: Path, destination: Path, ignore=None) -> None:
    """copytree with clones (the authoring copy, scratch folders for image stages)."""
    shutil.copytree(source, destination, ignore=ignore, copy_function=lambda a, b: clone(Path(a), Path(b)))


def touch(path: Path) -> None:
    try:
        os.utime(path, None)
    except OSError:
        pass


def _remove(path: Path) -> None:
    path = Path(path)
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path, ignore_errors=True)
    else:
        path.unlink(missing_ok=True)


def _safe_relative(name: str) -> bool:
    relative = Path(name)
    return bool(name) and not relative.is_absolute() and ".." not in relative.parts


class Store:
    """Content-addressed entries of one kind of result (here: build stages) in the shared cache folder."""

    def __init__(self, base: Path | None = None, kind: str = "stages"):
        self.base = Path(base) if base else root()
        self.kind = kind

    @property
    def folder(self) -> Path:
        return self.base / self.kind

    def entry(self, key: str) -> Path:
        if not key or any(character not in "0123456789abcdef" for character in key):
            raise ValueError(f"cache keys are hex digests: {key!r}")
        return self.folder / key

    def lookup(self, key: str) -> dict | None:
        """The entry's metadata (files and their hashes) without copying anything, or None. Touches the entry."""
        entry = self.entry(key)
        meta = read_json(entry / ENTRY)
        if not isinstance(meta, dict) or meta.get("key") != key or not isinstance(meta.get("files"), dict):
            return None
        if not all(_safe_relative(name) for name in [*meta["files"], *meta.get("removed", [])]):
            return None
        touch(entry)
        return meta

    def store(self, key: str, source: Path, files: dict, removed=(), info=None) -> bool:
        """Stores {relative path: sha256} from the folder source as one entry. An existing entry is kept (same key =
        same content); returns True when this call stored it. The hashes are checked while copying."""
        entry = self.entry(key)
        if (entry / ENTRY).is_file():
            touch(entry)
            return False
        self.folder.mkdir(parents=True, exist_ok=True)
        temporary = tmp_path(entry)
        try:
            (temporary / FILES).mkdir(parents=True)     # also for a stage that only removes files
            for name, expected in files.items():
                if not _safe_relative(name):
                    raise ValueError(f"unsafe cache path: {name}")
                destination = temporary / FILES / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                clone(Path(source) / name, destination)
                if sha256_file(destination) != expected:
                    raise RuntimeError(f"output changed while it was cached: {name}")
            meta = dict(info or {}, key=key, files=dict(files), removed=sorted(removed), stored=time.time())
            (temporary / ENTRY).write_text(json.dumps(meta, indent=1, sort_keys=True) + "\n", encoding="utf-8")
            try:
                os.rename(temporary, entry)
            except OSError:         # another run stored it first
                return False
            return True
        finally:
            if temporary.exists():
                shutil.rmtree(temporary, ignore_errors=True)

    def restore(self, key: str, destination: Path, meta: dict | None = None) -> dict | None:
        """Copies the entry's files into destination and applies its removals. Every file is cloned under a temp
        name and hashed first; only when all match are they moved into place, so a damaged or pruned entry never
        leaves half a stage behind. Returns the metadata, or None (miss; a damaged entry is discarded)."""
        meta = meta or self.lookup(key)
        if meta is None:
            return None
        entry = self.entry(key)
        destination = Path(destination)
        staged = []
        try:
            for name, expected in meta["files"].items():
                target = destination / name
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary = tmp_path(target)
                staged.append((temporary, target))
                clone(entry / FILES / name, temporary)
                if sha256_file(temporary) != expected:
                    raise ValueError(f"hash mismatch in cache entry {key[:12]}: {name}")
        except FileNotFoundError:   # pruned meanwhile: a plain miss
            for temporary, _ in staged:
                temporary.unlink(missing_ok=True)
            return None
        except ValueError:
            for temporary, _ in staged:
                temporary.unlink(missing_ok=True)
            self.discard(key)
            return None
        for temporary, target in staged:
            os.replace(temporary, target)
        for name in meta.get("removed", []):
            (destination / name).unlink(missing_ok=True)
        touch(entry)
        return meta

    def discard(self, key: str) -> None:
        """Removes a damaged entry (renamed first, so a concurrent reader never sees it half deleted)."""
        entry = self.entry(key)
        doomed = tmp_path(entry)
        try:
            os.rename(entry, doomed)
        except OSError:
            return
        shutil.rmtree(doomed, ignore_errors=True)


# ------------------------------------------------------------------------------------------------------------------
# Size, pruning
# ------------------------------------------------------------------------------------------------------------------

def _tree_size(path: Path) -> int:
    total = 0
    for folder, _, names in os.walk(path):
        for name in names:
            try:
                total += os.lstat(os.path.join(folder, name)).st_size
            except OSError:
                pass
    return total


def entries(base: Path | None = None) -> list:
    """(path, size, last use) of every entry of every kind; stale temp folders count with last use 0."""
    base = Path(base) if base else root()
    found = []
    if not base.is_dir():
        return found
    for kind in sorted(base.iterdir()):
        if kind.name.startswith(".") or not kind.is_dir():
            continue
        for item in os.scandir(kind):
            try:
                status = item.stat(follow_symlinks=False)
            except OSError:
                continue
            size = _tree_size(Path(item.path)) if item.is_dir(follow_symlinks=False) else status.st_size
            used = status.st_mtime
            if item.name.startswith(TMP_PREFIX):
                if time.time() - used < STALE_TMP_SECONDS:
                    continue            # a write in progress
                used = 0.0
            found.append((Path(item.path), size, used))
    return found


def usage(base: Path | None = None) -> int:
    return sum(size for _, size, _ in entries(base))


class _Lock:
    """Non-blocking lock on a file in base: prune() runs one at a time and is skipped otherwise."""

    def __init__(self, base: Path, name: str):
        self.path, self.handle = Path(base) / name, None

    def __enter__(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a")
        try:
            import fcntl
            fcntl.flock(self.handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.handle.close()
            self.handle = None
        except ImportError:         # no fcntl (not macOS/Linux): no lock
            pass
        return self.handle is not None

    def __exit__(self, *exc):
        if self.handle:
            self.handle.close()


def prune(base: Path | None = None, limit: int | None = None, now: float | None = None,
          grace: float = GRACE_SECONDS) -> dict:
    """Removes the least recently used entries until the cache fits the limit. Entries used within grace stay even
    when that leaves the cache above the limit (another run may need them right now)."""
    base = Path(base) if base else root()
    limit = limit_bytes() if limit is None else limit
    now = time.time() if now is None else now
    with _Lock(base, ".prune.lock") as locked:
        if not locked:
            return {"skipped": True, "total": None, "removed": 0, "freed": 0}
        found = sorted(entries(base), key=lambda item: item[2])
        total = sum(size for _, size, _ in found)
        before, removed, freed = total, 0, 0
        for path, size, used in found:
            if total <= limit and used > 0:
                break
            if used > now - grace:
                continue
            doomed = tmp_path(path)
            try:
                os.rename(path, doomed)     # out of sight first: a reader sees the entry or nothing
            except OSError:
                continue
            _remove(doomed)
            total -= size
            removed += 1
            freed += size
        return {"skipped": False, "before": before, "total": total, "limit": limit, "removed": removed,
                "freed": freed}
