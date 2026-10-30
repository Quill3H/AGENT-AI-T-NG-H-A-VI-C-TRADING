"""Nonblocking, OS-backed ownership for a local paper account, not a port."""
import os
from pathlib import Path


LOCK_FILENAME = ".paper-owner.lock"


class AccountInUseError(RuntimeError):
    pass


class AccountOwnershipLock:
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self._stream = None
        self._pid = None

    def acquire(self):
        if self._stream is not None:
            self.assert_owned()
            return
        self.directory.mkdir(parents=True, exist_ok=True)
        stream = (self.directory / LOCK_FILENAME).open("a+b")
        try:
            if os.name == "nt":
                import msvcrt
                # Windows permits locking beyond EOF; the marker needs no writes.
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            stream.close()
            raise AccountInUseError("paper account is in use or its ownership lock is unavailable") from exc
        self._stream, self._pid = stream, os.getpid()

    def assert_owned(self):
        if self._stream is None or self._stream.closed or self._pid != os.getpid():
            raise RuntimeError("paper account writer ownership is not held")

    def release(self):
        if self._stream is not None:
            # Do not unlink: competing owners must continue locking the same file.
            self._stream.close()
            self._stream, self._pid = None, None
