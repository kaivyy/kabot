"""Pytest session configuration and platform-specific test harness patches."""

import os
import tempfile
from pathlib import Path


def _patch_windows_pytest_tmpdir_mode() -> None:
    """Work around Windows sandbox ACL behavior for pytest temp directories.

    In this environment, pytest's hardcoded mode=0o700 temp directories can be
    non-writable for follow-up file creation. We patch TempPathFactory to use
    writable directory modes on Windows only.
    """
    if os.name != "nt":
        return

    from _pytest.pathlib import make_numbered_dir, make_numbered_dir_with_cleanup, rm_rf
    from _pytest.tmpdir import LOCK_TIMEOUT, TempPathFactory, get_user, get_user_id

    temp_root = Path.cwd() / ".pytest-temp-root-safe"
    temp_root.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("PYTEST_DEBUG_TEMPROOT", str(temp_root))

    def patched_getbasetemp(self: TempPathFactory) -> Path:
        if self._basetemp is not None:
            return self._basetemp

        if self._given_basetemp is not None:
            basetemp = self._given_basetemp
            if basetemp.exists():
                rm_rf(basetemp)
            basetemp.mkdir(mode=0o777)
            basetemp = basetemp.resolve()
        else:
            from_env = os.environ.get("PYTEST_DEBUG_TEMPROOT")
            temproot = Path(from_env or tempfile.gettempdir()).resolve()
            user = get_user() or "unknown"
            rootdir = temproot.joinpath(f"pytest-of-{user}")
            try:
                rootdir.mkdir(mode=0o777, exist_ok=True)
            except OSError:
                rootdir = temproot.joinpath("pytest-of-unknown")
                rootdir.mkdir(mode=0o777, exist_ok=True)

            uid = get_user_id()
            if uid is not None:
                rootdir_stat = rootdir.stat()
                if rootdir_stat.st_uid != uid:
                    raise OSError(
                        f"The temporary directory {rootdir} is not owned by the current user. "
                        "Fix this and try again."
                    )

            keep = self._retention_count
            if self._retention_policy == "none":
                keep = 0
            basetemp = make_numbered_dir_with_cleanup(
                prefix="pytest-",
                root=rootdir,
                keep=keep,
                lock_timeout=LOCK_TIMEOUT,
                mode=0o777,
            )

        self._basetemp = basetemp
        self._trace("new basetemp", basetemp)
        return basetemp

    TempPathFactory.getbasetemp = patched_getbasetemp

    def patched_mktemp(self: TempPathFactory, basename: str, numbered: bool = True) -> Path:
        basename = self._ensure_relative_to_basetemp(basename)
        if not numbered:
            p = self.getbasetemp().joinpath(basename)
            p.mkdir(mode=0o777)
        else:
            p = make_numbered_dir(root=self.getbasetemp(), prefix=basename, mode=0o777)
            self._trace("mktemp", p)
        return p

    TempPathFactory.mktemp = patched_mktemp


_patch_windows_pytest_tmpdir_mode()
