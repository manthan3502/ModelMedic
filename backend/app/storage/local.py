import os
import re
import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile


class LocalArtifactStore:
    """Server-generated relative keys only; write-once, private local objects.

    The root must be controlled by the service account, not untrusted local users.
    Atomic hard-link publication prevents partial reads and accidental replacement.
    """

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        if not key or any(
            not re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9_.-]*", part) for part in key.split("/")
        ):
            raise ValueError("Invalid artifact key")
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root) or path == self.root:
            raise ValueError("Artifact key escapes storage root")
        return path

    def put(self, key: str, content: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            try:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            except BaseException:
                handle.close()
                temporary.unlink(missing_ok=True)
                raise
        try:
            os.link(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def delete_prefix(self, prefix: str) -> None:
        path = self._path(prefix.rstrip("/"))
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)
