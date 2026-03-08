#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from context_db import load_config
from path_globs import matches_include_globs


IGNORE_SUFFIXES = (".swp", ".tmp", ".bak", ".pyc", "~")


def _run(py: Path, args: list[str]) -> int:
    cmd = [sys.executable, str(py), *args]
    p = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return p.returncode


def _should_track(path: Path, cfg) -> bool:
    if any(str(path).endswith(s) for s in IGNORE_SUFFIXES):
        return False
    try:
        rel = path.relative_to(cfg.root)
    except ValueError:
        return False
    parts = {p.lower() for p in rel.parts}
    if any(ex.lower() in parts for ex in cfg.exclude_dirs):
        return False
    return matches_include_globs(rel.as_posix(), cfg.include_globs)


@dataclass
class Pending:
    last_ts: float


@dataclass
class WatchState:
    pending_files: dict[Path, Pending]
    full_rescan_ts: float | None = None


def _mark_pending_file(state: WatchState, lock: threading.Lock, path: Path, now: float) -> None:
    with lock:
        state.pending_files[path] = Pending(last_ts=now)


def _mark_full_rescan(state: WatchState, lock: threading.Lock, now: float) -> None:
    with lock:
        if state.full_rescan_ts is None or now > state.full_rescan_ts:
            state.full_rescan_ts = now


def _collect_tracked_files(cfg) -> dict[Path, float]:
    tracked: dict[Path, float] = {}
    for path in cfg.root.rglob("*"):
        if not path.is_file() or not _should_track(path, cfg):
            continue
        try:
            tracked[path] = path.stat().st_mtime
        except OSError:
            continue
    return tracked


def _diff_tracked_files(previous: dict[Path, float], current: dict[Path, float]) -> tuple[list[Path], bool]:
    modified: list[Path] = []
    created: list[Path] = []
    for path, mtime in current.items():
        if path not in previous:
            created.append(path)
        elif previous[path] != mtime:
            modified.append(path)
    has_deleted = any(path not in current for path in previous)
    modified.sort()
    created.sort()
    return modified + created, has_deleted


def _classify_tracked_files(
    previous: dict[Path, float], current: dict[Path, float]
) -> tuple[list[Path], list[Path], bool]:
    modified: list[Path] = []
    created: list[Path] = []
    for path, mtime in current.items():
        if path not in previous:
            created.append(path)
        elif previous[path] != mtime:
            modified.append(path)
    has_deleted = any(path not in current for path in previous)
    modified.sort()
    created.sort()
    return modified, created, has_deleted


def _reconcile_tracked_files(cfg, tracked: dict[Path, float]) -> tuple[dict[Path, float], list[Path], list[Path], bool]:
    current = _collect_tracked_files(cfg)
    modified, created, has_deleted = _classify_tracked_files(tracked, current)
    return current, modified, created, has_deleted


def _loop(cfg, state: WatchState, lock: threading.Lock, debounce_s: float) -> None:
    brain = cfg.root / ".vibe" / "brain"
    while True:
        time.sleep(0.2)
        now = time.time()
        ready: list[Path] = []
        run_full_rescan = False
        with lock:
            if state.full_rescan_ts is not None and now - state.full_rescan_ts >= debounce_s:
                run_full_rescan = True
                state.full_rescan_ts = None
                state.pending_files.clear()
            else:
                for p, meta in list(state.pending_files.items()):
                    if now - meta.last_ts >= debounce_s:
                        ready.append(p)
                        state.pending_files.pop(p, None)

        if run_full_rescan:
            rc = _run(brain / "indexer.py", ["--scan-all"])
            if rc != 0:
                time.sleep(0.3)
                _run(brain / "indexer.py", ["--scan-all"])
            _run(brain / "summarizer.py", ["--full"])
            continue

        if not ready:
            continue

        for p in ready:
            if not p.exists():
                _mark_full_rescan(state, lock, time.time())
                continue
            rel = p.relative_to(cfg.root).as_posix()
            rc = _run(brain / "indexer.py", ["--file", rel])
            if rc != 0:
                # one retry (sqlite lock etc)
                time.sleep(0.3)
                retry_rc = _run(brain / "indexer.py", ["--file", rel])
                if retry_rc != 0:
                    _mark_full_rescan(state, lock, time.time())

        _run(brain / "summarizer.py", [])


def _watch_with_watchdog(cfg, debounce_s: float) -> int:
    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer
    except Exception as ex:
        print(
            "[watcher] missing dependency: watchdog. Install with:\n"
            "  python3 scripts/vibe.py bootstrap --install-deps\n"
            "or:\n"
            "  python3 -m pip install -r .vibe/brain/requirements.txt\n"
            f"(details: {ex})",
            file=sys.stderr,
        )
        return 1

    state = WatchState(pending_files={})
    lock = threading.Lock()

    class Handler(FileSystemEventHandler):
        def on_modified(self, event):  # noqa: N802
            if event.is_directory:
                return
            p = Path(event.src_path)
            if not _should_track(p, cfg):
                return
            _mark_pending_file(state, lock, p, time.time())

        def on_created(self, event):  # noqa: N802
            if event.is_directory:
                return
            p = Path(event.src_path)
            if not _should_track(p, cfg):
                return
            _mark_full_rescan(state, lock, time.time())

        def on_deleted(self, event):  # noqa: N802
            if event.is_directory:
                return
            p = Path(event.src_path)
            if not _should_track(p, cfg):
                return
            _mark_full_rescan(state, lock, time.time())

        def on_moved(self, event):  # noqa: N802
            if event.is_directory:
                return
            src = Path(event.src_path)
            dest = Path(getattr(event, "dest_path", event.src_path))
            if not _should_track(src, cfg) and not _should_track(dest, cfg):
                return
            _mark_full_rescan(state, lock, time.time())

    observer = Observer()
    handler = Handler()
    observer.schedule(handler, str(cfg.root), recursive=True)

    thread = threading.Thread(target=_loop, args=(cfg, state, lock, debounce_s), daemon=True)
    thread.start()

    observer.start()
    print(f"[watcher] watching: {cfg.root} (debounce={debounce_s:.2f}s)")
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("[watcher] stopping...")
        observer.stop()
    observer.join()
    return 0


def _watch_with_polling(cfg, debounce_s: float) -> int:
    # Fallback when watchdog isn't installed: poll mtimes.
    tracked = _collect_tracked_files(cfg)
    state = WatchState(pending_files={})
    lock = threading.Lock()
    thread = threading.Thread(target=_loop, args=(cfg, state, lock, debounce_s), daemon=True)
    thread.start()

    print(f"[watcher] watchdog not available; polling every 1s (debounce={debounce_s:.2f}s)")
    try:
        while True:
            time.sleep(1.0)
            tracked, modified, created, has_deleted = _reconcile_tracked_files(cfg, tracked)
            now = time.time()
            for path in modified:
                _mark_pending_file(state, lock, path, now)
            if created or has_deleted:
                _mark_full_rescan(state, lock, now)
    except KeyboardInterrupt:
        print("[watcher] stopping...")
        return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Watch repo changes and refresh LATEST_CONTEXT.md.")
    parser.add_argument("--debounce-ms", type=int, default=400)
    args = parser.parse_args(argv)

    cfg = load_config()
    debounce_s = max(0.3, min(1.0, args.debounce_ms / 1000.0))
    rc = _watch_with_watchdog(cfg, debounce_s)
    if rc == 0:
        return 0
    return _watch_with_polling(cfg, debounce_s)


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
