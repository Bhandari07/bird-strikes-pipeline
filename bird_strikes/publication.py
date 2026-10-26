"""Publish a complete release through one atomic pointer, with a local writer lock."""

import json, os, uuid
from contextlib import contextmanager
from pathlib import Path


def current_release(output: Path) -> Path:
    pointer = json.loads((Path(output) / "CURRENT.json").read_text())
    return Path(output) / "releases" / pointer["release_id"]


def publish(output: Path, release: Path) -> None:
    pointer = output / f".pointer-{uuid.uuid4().hex}.tmp"
    try:
        with pointer.open("w") as handle:
            json.dump({"release_id": release.name}, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(pointer, output / "CURRENT.json")
    finally:
        pointer.unlink(missing_ok=True)


@contextmanager
def writer_lock(output: Path):
    lock = output / ".writer.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise RuntimeError(
            "Another writer or stale lock exists. Check the PID in .writer.lock before removing it."
        )
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write(str(os.getpid()))
        yield
    finally:
        lock.unlink(missing_ok=True)
