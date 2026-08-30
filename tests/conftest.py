"""Shared fixtures for the test suite."""

import hashlib
import socket
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, Mock

import pytest
from pytest_mock import MockerFixture

from tests.helpers import install_fake_cli

# Deliberately not FALLBACK_VERSION: if the two matched, a test could not tell
# "the fixture answered" from "the lookup failed and fell back". Tests that care
# about a specific version pin it themselves.
LATEST_RELEASE_URL = "https://github.com/tailwindlabs/tailwindcss/releases/tag/v4.2.7"


@pytest.fixture(autouse=True)
def fail_on_network_access(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Fail any test that resolves a hostname.

    Blocking the socket is not enough on its own: the version lookup swallows
    connection errors and falls back to a pinned version, so a test that reaches
    for the network passes either way and the attempt stays invisible. Recording
    the attempt and failing afterwards is what makes it visible.

    This catches name resolution, not every conceivable socket. That covers
    everything this package does — urllib reaches the network through
    `socket.create_connection`, which resolves even an IP literal — but a raw
    `socket.connect()` to an address would slip past.
    """
    attempts: list[str] = []

    def record(host: Any, port: Any, *args: Any, **kwargs: Any) -> Any:
        attempts.append(f"{host}:{port}")
        raise OSError(f"network access to {host}:{port} is blocked in tests")

    monkeypatch.setattr(socket, "getaddrinfo", record)
    yield
    if attempts:
        pytest.fail(f"test attempted network access: {', '.join(attempts)}")


@pytest.fixture(autouse=True)
def version_cache_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Give every test its own version cache, and hand it out on request.

    The real cache lives in the system temp directory and is shared by every run
    on the machine, so whether a test resolved a version from cache or over the
    network depended on what ran before it. Worse, tests that exercise cache
    handling used to delete and overwrite that shared file, which is the same
    file a developer's own `manage.py tailwind` reads.
    """
    cache_path = tmp_path / "version_cache.txt"
    monkeypatch.setattr("django_tailwind_cli.config._get_cache_path", lambda: cache_path)
    return cache_path


@pytest.fixture(autouse=True)
def reset_binary_version_cache() -> Iterator[None]:
    """Keep the per-path binary version cache from leaking between tests.

    ``detect_binary_version`` is a process-global ``functools.cache``. Tests that reuse a path —
    anything built on ``fake_project_settings`` — would otherwise read the previous test's answer,
    which makes failures depend on execution order.
    """
    from django_tailwind_cli.config import detect_binary_version

    detect_binary_version.cache_clear()
    yield
    detect_binary_version.cache_clear()


@pytest.fixture(autouse=True)
def patch_version_lookup(request: pytest.FixtureRequest, mocker: MockerFixture) -> None:
    """Answer the "what is the latest release" lookup without a network call.

    Modules that need a different answer patch this again; a later patch wins.
    Tests of the lookup itself opt out with the `unpatched_http` marker.
    """
    if "unpatched_http" in request.keywords:
        return
    mocker.patch(
        "django_tailwind_cli.utils.http.fetch_redirect_location",
        return_value=(True, LATEST_RELEASE_URL),
    )


def call_directly(func: Any, *args: Any, **kwargs: Any) -> Any:
    """Call ``func`` instead of handing it to Django's autoreloader."""
    return func(*args, **kwargs)


@pytest.fixture
def bypass_autoreload(mocker: MockerFixture) -> None:
    """Run `tailwind watch` in-process instead of under Django's autoreloader.

    The command wraps its loop in ``django.utils.autoreload.run_with_reloader``, which forks a
    child process. Calling the inner callable directly keeps the assertions in the same process.

    Opt in with ``@pytest.mark.usefixtures("bypass_autoreload")``.
    """
    mocker.patch("django.utils.autoreload.run_with_reloader", side_effect=call_directly)


@pytest.fixture
def fake_project_settings(settings: Any) -> None:
    """Point the settings at a project directory that does not exist on disk.

    Path resolution is pure string work, so tests that only assert resolved paths do not need a
    real directory — and a fixed path keeps their expected values readable as literals.

    Opt in with ``@pytest.mark.usefixtures("fake_project_settings")``.
    """
    settings.BASE_DIR = Path("/home/user/project")
    settings.STATICFILES_DIRS = (settings.BASE_DIR / "assets",)


@pytest.fixture
def tmp_project(settings: Any, tmp_path: Path) -> Path:
    """A real project directory under ``tmp_path``, with the CLI settings pointing inside it.

    Puts no binary on disk on purpose: whether the CLI exists is what several tests are about —
    the download path, ``TAILWIND_CLI_AUTOMATIC_DOWNLOAD``, the "not installed" error — so a
    fixture that installed one would answer that question for them. Use ``tmp_project_with_cli``
    when the binary should already be there.

    Returns the project root.
    """
    settings.BASE_DIR = tmp_path
    settings.STATICFILES_DIRS = (tmp_path / "assets",)
    settings.TAILWIND_CLI_PATH = tmp_path / "tailwindcss"
    settings.TAILWIND_CLI_VERSION = "4.0.0"
    return tmp_path


@pytest.fixture
def tmp_project_with_cli(tmp_project: Path, settings: Any) -> Path:
    """``tmp_project`` with the CLI binary already on disk and executable.

    For tests about what a command does once the CLI is there, not about getting it there.
    Returns the binary's path.
    """
    return install_fake_cli(settings.TAILWIND_CLI_PATH)


def _tree_state(root: Path) -> dict[str, bytes]:
    """Content digests, not mtimes: a `git checkout` restores content but not the timestamp.

    Source files are skipped: the leak this guards against is build output, and a test that
    rewrote a test module would have bigger problems than this fixture.
    """
    return {
        str(p.relative_to(root)): hashlib.blake2b(p.read_bytes(), digest_size=8).digest()
        for p in root.rglob("*")
        if p.is_file() and p.suffix != ".py" and "__pycache__" not in p.parts
    }


@pytest.fixture(autouse=True)
def no_writes_into_the_checkout() -> Iterator[None]:
    """Fail a test that builds into the repository instead of into its tmp_path sandbox.

    `tests/settings.py` sets `BASE_DIR` to the real `tests/` directory, so a test that forgets to
    point it at `tmp_path` writes its source CSS, its compiled CSS and its downloaded binary
    straight into the checkout — and still passes, because nothing asserted otherwise.

    That is not hypothetical: consolidating the per-test setup in this suite removed 54 lines of
    it, and the suite stayed green while six CSS files appeared in `tests/`. They are all named in
    `tests/.gitignore` — `assets/css/tailwind.css`, `assets/css/source.css`, `.django_tailwind_cli`
    — so `git status` says nothing either. That is why nothing caught it, and why this looks at
    content rather than at git.
    """
    root = Path(__file__).parent
    before = _tree_state(root)
    yield
    after = _tree_state(root)

    created = sorted(set(after) - set(before))
    deleted = sorted(set(before) - set(after))
    changed = sorted(name for name, state in after.items() if before.get(name, state) != state)
    assert not (created or deleted or changed), (
        f"the test wrote into the checkout — created {created}, deleted {deleted}, "
        f"changed {changed}. Point settings.BASE_DIR at tmp_path, as the tmp_project fixture does."
    )


@pytest.fixture
def stub_subprocess_run(mocker: MockerFixture) -> MagicMock:
    """A `subprocess.run` that succeeds and says nothing.

    Not interchangeable with a bare `mocker.patch("subprocess.run")`: that yields a MagicMock
    whose `.stdout` is truthy, so a command reading it takes a different branch. The bare patches
    are left as they are — several of them are `detect_binary_version` tests that parse stdout,
    and converting the rest changes what they observe for no gain.
    """
    return mocker.patch("subprocess.run", return_value=Mock(returncode=0, stdout="", stderr=""))
