"""Shared fixtures for the test suite."""

import socket
from collections.abc import Iterator
from pathlib import Path
from typing import Any

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
