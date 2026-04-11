# pyright: reportPrivateUsage=false
from pathlib import Path

import pytest
from _pytest.recwarn import WarningsChecker
from pytest_django.fixtures import SettingsWrapper
from pytest_mock import MockerFixture

from django_tailwind_cli.config import get_config, get_version


@pytest.fixture(autouse=True)
def configure_settings(
    settings: SettingsWrapper,
    mocker: MockerFixture,
):
    settings.BASE_DIR = Path("/home/user/project")
    settings.STATICFILES_DIRS = (settings.BASE_DIR / "assets",)
    request_get = mocker.patch("django_tailwind_cli.utils.http.fetch_redirect_location")
    request_get.return_value = (True, "https://github.com/tailwindlabs/tailwindcss/releases/tag/v4.1.3")


@pytest.mark.parametrize(
    "version_str, expected_version_str, version",
    [
        ("4.0.0", "4.0.0", (4, 0, 0)),
        ("latest", "4.1.3", (4, 1, 3)),
    ],
)
def test_get_version(
    settings: SettingsWrapper,
    version_str: str,
    expected_version_str: str,
    version: tuple[int, int, int],
    mocker: MockerFixture,
):
    settings.TAILWIND_CLI_VERSION = version_str

    # For "latest" version test, mock the network request to ensure fallback
    if version_str == "latest":
        # Clear any existing cache
        from django_tailwind_cli.config import _get_cache_path

        cache_path = _get_cache_path()
        if cache_path.exists():
            cache_path.unlink()

        # Mock failed network request to force fallback
        request_get = mocker.patch("django_tailwind_cli.utils.http.fetch_redirect_location")
        request_get.return_value = (False, None)

    r_version_str, r_version = get_version()
    assert r_version_str == expected_version_str
    assert r_version.major == version[0]
    assert r_version.minor == version[1]
    assert r_version.patch == version[2]


def test_get_version_latest_without_proper_http_response(mocker: MockerFixture):
    # Clear any existing cache
    from django_tailwind_cli.config import _get_cache_path

    cache_path = _get_cache_path()
    if cache_path.exists():
        cache_path.unlink()

    request_get = mocker.patch("django_tailwind_cli.utils.http.fetch_redirect_location")
    request_get.return_value = (False, None)

    r_version_str, r_version = get_version()
    assert r_version_str == "4.1.3"
    assert r_version.major == 4
    assert r_version.minor == 1
    assert r_version.patch == 3


def test_get_version_latest_without_redirect(mocker: MockerFixture):
    # Clear any existing cache
    from django_tailwind_cli.config import _get_cache_path

    cache_path = _get_cache_path()
    if cache_path.exists():
        cache_path.unlink()

    request_get = mocker.patch("django_tailwind_cli.utils.http.fetch_redirect_location")
    request_get.return_value = (True, None)

    r_version_str, r_version = get_version()
    assert r_version_str == "4.1.3"
    assert r_version.major == 4
    assert r_version.minor == 1
    assert r_version.patch == 3


def test_get_version_with_official_repo_and_version_3(settings: SettingsWrapper):
    settings.TAILWIND_CLI_VERSION = "3.4.13"
    with pytest.raises(ValueError, match="Tailwind CSS 3.x is not supported by this version."):
        get_version()


def test_get_version_with_daisyui_enabled_latest(settings: SettingsWrapper, mocker: MockerFixture):
    """Test that DaisyUI uses the correct repository and correctly parses version."""
    # Clear any existing cache
    from django_tailwind_cli.config import _get_cache_path
    from semver import Version

    cache_path = _get_cache_path()
    if cache_path.exists():
        cache_path.unlink()

    settings.TAILWIND_CLI_USE_DAISY_UI = True
    settings.TAILWIND_CLI_VERSION = "latest"

    # Mock successful redirect to a generic valid DaisyUI version
    test_version = "9.8.7"
    request_get = mocker.patch("django_tailwind_cli.utils.http.fetch_redirect_location")
    request_get.return_value = (
        True,
        f"https://github.com/dobicinaitis/tailwind-cli-extra/releases/tag/v{test_version}",
    )

    r_version_str, r_version = get_version()

    # Test that version string is correctly extracted (without 'v' prefix)
    assert r_version_str == test_version

    # Test that version is correctly parsed as semantic version
    assert isinstance(r_version, Version)
    assert str(r_version) == test_version

    # Verify the correct DaisyUI repository URL was used (not standard Tailwind)
    request_get.assert_called_once_with(
        "https://github.com/dobicinaitis/tailwind-cli-extra/releases/latest/", timeout=10
    )


def test_get_version_with_daisyui_fallback_when_network_fails(settings: SettingsWrapper, mocker: MockerFixture):
    """Test fallback behavior when DaisyUI is enabled but network request fails."""
    # Clear any existing cache
    from django_tailwind_cli.config import _get_cache_path, FALLBACK_VERSION
    from semver import Version

    cache_path = _get_cache_path()
    if cache_path.exists():
        cache_path.unlink()

    settings.TAILWIND_CLI_USE_DAISY_UI = True
    settings.TAILWIND_CLI_VERSION = "latest"

    # Mock failed network request
    request_get = mocker.patch("django_tailwind_cli.utils.http.fetch_redirect_location")
    request_get.return_value = (False, None)

    r_version_str, r_version = get_version()

    # Should fall back to the configured fallback version
    assert r_version_str == FALLBACK_VERSION
    assert isinstance(r_version, Version)
    assert str(r_version) == FALLBACK_VERSION

    # Verify the correct DaisyUI repository URL was still used in the attempt
    request_get.assert_called_once_with(
        "https://github.com/dobicinaitis/tailwind-cli-extra/releases/latest/", timeout=10
    )


def test_get_version_with_unofficial_repo_and_version_3(settings: SettingsWrapper):
    settings.TAILWIND_CLI_VERSION = "3.4.13"
    settings.TAILWIND_CLI_SRC_REPO = "oliverandrich/my-tailwindcss-cli"

    r_version_str, r_version = get_version()
    assert r_version_str == "3.4.13"
    assert r_version.major == 3
    assert r_version.minor == 4
    assert r_version.patch == 13


def test_default_config():
    c = get_config()
    assert c.version.major >= 4
    assert ".django_tailwind_cli/tailwindcss" in str(c.cli_path)
    assert c.version_str in str(c.cli_path)
    assert c.download_url.startswith(
        f"https://github.com/tailwindlabs/tailwindcss/releases/download/v{c.version_str}/tailwindcss-"
    )
    assert str(c.dist_css) == "/home/user/project/assets/css/tailwind.css"
    assert c.src_css is not None
    assert str(c.src_css).endswith(".django_tailwind_cli/source.css")
    assert c.overwrite_default_config


@pytest.mark.parametrize(
    "src_path",
    ["relative/source.css", "/absolute/src.css"],
)
def test_overwrite_src_css(settings: SettingsWrapper, src_path: str):
    settings.TAILWIND_CLI_SRC_CSS = src_path
    c = get_config()
    assert not c.overwrite_default_config
    assert str(c.src_css).endswith(src_path)


def test_invalid_settings_for_staticfiles_dirs(settings: SettingsWrapper):
    settings.STATICFILES_DIRS = []
    with pytest.raises(ValueError, match="STATICFILES_DIRS is empty. Please add a path to your static files."):
        get_config()

    settings.STATICFILES_DIRS = None
    with pytest.raises(ValueError, match="STATICFILES_DIRS is empty. Please add a path to your static files."):
        get_config()


def test_string_setting_for_staticfiles_dirs(settings: SettingsWrapper):
    settings.STATICFILES_DIRS = ["path"]
    c = get_config()
    assert c.dist_css == Path("path/css/tailwind.css")


def test_path_setting_for_staticfiles_dirs(settings: SettingsWrapper):
    settings.STATICFILES_DIRS = [Path("path")]
    c = get_config()
    assert c.dist_css == Path("path/css/tailwind.css")


def test_prefixed_setting_for_staticfiles_dirs(settings: SettingsWrapper):
    settings.STATICFILES_DIRS = (("prefix", "path"),)
    c = get_config()
    assert c.dist_css == Path("path/css/tailwind.css")


def test_invalid_settings_for_tailwind_cli_dist_css(settings: SettingsWrapper):
    settings.TAILWIND_CLI_DIST_CSS = None
    with pytest.raises(ValueError, match="TAILWIND_CLI_DIST_CSS must not be None."):
        get_config()


def test_invalid_settings_for_tailwind_cli_assert_name(settings: SettingsWrapper):
    settings.TAILWIND_CLI_ASSET_NAME = None
    with pytest.raises(ValueError, match="TAILWIND_CLI_ASSET_NAME must not be None."):
        get_config()


def test_invalid_settings_for_tailwind_cli_src_repo(settings: SettingsWrapper):
    settings.TAILWIND_CLI_SRC_REPO = None
    with pytest.raises(ValueError, match="TAILWIND_CLI_SRC_REPO must not be None."):
        get_config()


@pytest.mark.parametrize(
    "platform,machine,result",
    [
        ("Windows", "x86_64", "tailwindcss-windows-x64.exe"),
        ("Windows", "amd64", "tailwindcss-windows-x64.exe"),
        ("Darwin", "aarch64", "tailwindcss-macos-arm64"),
        ("Darwin", "arm64", "tailwindcss-macos-arm64"),
    ],
)
def test_download_url(mocker: MockerFixture, platform: str, machine: str, result: str):
    platform_system = mocker.patch("platform.system")
    platform_system.return_value = platform

    platform_machine = mocker.patch("platform.machine")
    platform_machine.return_value = machine

    c = get_config()
    assert c.download_url.endswith(result)


@pytest.mark.parametrize(
    "platform,machine,result",
    [
        ("Windows", "x86_64", "tailwindcss-windows-x64-4.0.0.exe"),
        ("Windows", "amd64", "tailwindcss-windows-x64-4.0.0.exe"),
        ("Darwin", "aarch64", "tailwindcss-macos-arm64-4.0.0"),
        ("Darwin", "arm64", "tailwindcss-macos-arm64-4.0.0"),
    ],
)
def test_get_cli_path(settings: SettingsWrapper, mocker: MockerFixture, platform: str, machine: str, result: str):
    settings.TAILWIND_CLI_VERSION = "4.0.0"

    platform_system = mocker.patch("platform.system")
    platform_system.return_value = platform

    platform_machine = mocker.patch("platform.machine")
    platform_machine.return_value = machine

    c = get_config()
    assert str(c.cli_path).endswith(result)


def test_cli_path_to_existing_file(settings: SettingsWrapper, tmp_path: Path):
    settings.TAILWIND_CLI_PATH = tmp_path / "tailwindcss"
    settings.TAILWIND_CLI_PATH.touch(mode=0o755, exist_ok=True)
    c = get_config()
    assert str(c.cli_path) == str(tmp_path / "tailwindcss")


def test_cli_path_to_existing_directory(settings: SettingsWrapper):
    settings.TAILWIND_CLI_PATH = "/opt/bin"
    c = get_config()
    assert "/opt/bin/tailwindcss-" in str(c.cli_path)


@pytest.mark.parametrize(
    "system, result",
    [
        ("Windows", "windows"),
        ("Darwin", "macos"),
        ("Linux", "linux"),
    ],
)
def test_system(system: str, result: str, mocker: MockerFixture):
    platform_system = mocker.patch("platform.system")
    platform_system.return_value = system

    c = get_config()
    assert result in str(c.cli_path)
    assert result in c.download_url


@pytest.mark.parametrize(
    "machine, result",
    [
        ("x86_64", "x64"),
        ("amd64", "x64"),
        ("aarch64", "arm64"),
    ],
)
def test_machine(machine: str, result: str, mocker: MockerFixture):
    platform_machine = mocker.patch("platform.machine")
    platform_machine.return_value = machine

    c = get_config()
    assert result in str(c.cli_path)
    assert result in c.download_url


def test_build_cmd():
    c = get_config()
    assert c.build_cmd == [
        str(c.cli_path),
        "--input",
        str(c.src_css),
        "--output",
        str(c.dist_css),
        "--minify",
    ]


def test_watch_cmd():
    c = get_config()
    assert c.watch_cmd == [
        str(c.cli_path),
        "--input",
        str(c.src_css),
        "--output",
        str(c.dist_css),
        "--watch",
    ]


def test_daisy_ui_support(
    settings: SettingsWrapper,
    mocker: MockerFixture,
):
    from django_tailwind_cli.config import _get_cache_path
    from semver import Version

    # Clear any existing cache to prevent interference from other tests
    cache_path = _get_cache_path()
    if cache_path.exists():
        cache_path.unlink()

    settings.TAILWIND_CLI_USE_DAISY_UI = True
    test_version = "7.6.5"
    request_get = mocker.patch("django_tailwind_cli.utils.http.fetch_redirect_location")
    request_get.return_value = (
        True,
        f"https://github.com/dobicinaitis/tailwind-cli-extra/releases/tag/v{test_version}",
    )

    c = get_config()

    # Test DaisyUI configuration is properly applied
    assert c.use_daisy_ui
    assert "tailwindcss-extra" in str(c.cli_path)
    assert "dobicinaitis/tailwind-cli-extra" in c.download_url

    # Test version parsing works correctly
    r_version_str, r_version = get_version()
    assert r_version_str == test_version
    assert isinstance(r_version, Version)
    assert str(r_version) == test_version


def test_css_map_creates_multiple_entries(settings: SettingsWrapper):
    settings.TAILWIND_CLI_CSS_MAP = [
        ("admin.css", "admin.output.css"),
        ("web.css", "web.output.css"),
    ]
    c = get_config()
    assert len(c.css_entries) == 2
    assert c.css_entries[0].name == "admin"
    assert c.css_entries[1].name == "web"
    assert str(c.css_entries[0].dist_css).endswith("admin.output.css")
    assert str(c.css_entries[1].dist_css).endswith("web.output.css")


def test_css_map_backward_compatibility_properties(settings: SettingsWrapper):
    settings.TAILWIND_CLI_CSS_MAP = [
        ("admin.css", "admin.output.css"),
        ("web.css", "web.output.css"),
    ]
    c = get_config()
    assert str(c.src_css).endswith("admin.css")
    assert str(c.dist_css).endswith("admin.output.css")
    assert c.dist_css_base == "admin.output.css"


def test_css_map_get_build_cmd(settings: SettingsWrapper):
    settings.TAILWIND_CLI_CSS_MAP = [
        ("admin.css", "admin.output.css"),
        ("web.css", "web.output.css"),
    ]
    c = get_config()
    for entry in c.css_entries:
        cmd = c.get_build_cmd(entry)
        assert "--input" in cmd
        assert "--output" in cmd
        assert "--minify" in cmd
        assert str(entry.src_css) in cmd
        assert str(entry.dist_css) in cmd


def test_get_build_cmd_without_minify(settings: SettingsWrapper):
    settings.TAILWIND_CLI_CSS_MAP = [("admin.css", "admin.output.css")]
    c = get_config()
    cmd = c.get_build_cmd(c.css_entries[0], minify=False)
    assert "--minify" not in cmd
    assert "--input" in cmd
    assert "--output" in cmd


def test_css_map_get_watch_cmd(settings: SettingsWrapper):
    settings.TAILWIND_CLI_CSS_MAP = [
        ("admin.css", "admin.output.css"),
        ("web.css", "web.output.css"),
    ]
    c = get_config()
    for entry in c.css_entries:
        cmd = c.get_watch_cmd(entry)
        assert "--input" in cmd
        assert "--output" in cmd
        assert "--watch" in cmd
        assert str(entry.src_css) in cmd
        assert str(entry.dist_css) in cmd


def test_css_map_mutual_exclusivity_with_src_css(settings: SettingsWrapper):
    settings.TAILWIND_CLI_CSS_MAP = [("a.css", "b.css")]
    settings.TAILWIND_CLI_SRC_CSS = "source.css"
    with pytest.raises(ValueError, match="Cannot use TAILWIND_CLI_CSS_MAP together"):
        get_config()


def test_css_map_mutual_exclusivity_with_dist_css(settings: SettingsWrapper):
    settings.TAILWIND_CLI_CSS_MAP = [("a.css", "b.css")]
    settings.TAILWIND_CLI_DIST_CSS = "output.css"
    with pytest.raises(ValueError, match="Cannot use TAILWIND_CLI_CSS_MAP together"):
        get_config()


def test_css_map_invalid_format_not_list(settings: SettingsWrapper):
    settings.TAILWIND_CLI_CSS_MAP = "invalid"
    with pytest.raises(ValueError, match="must be a list or tuple"):
        get_config()


def test_css_map_invalid_entry_format(settings: SettingsWrapper):
    settings.TAILWIND_CLI_CSS_MAP = [("only_one",)]
    with pytest.raises(ValueError, match="must be a .* pair"):
        get_config()


def test_css_map_empty_source(settings: SettingsWrapper):
    settings.TAILWIND_CLI_CSS_MAP = [("", "output.css")]
    with pytest.raises(ValueError, match="empty source or destination"):
        get_config()


def test_css_map_empty_destination(settings: SettingsWrapper):
    settings.TAILWIND_CLI_CSS_MAP = [("source.css", "")]
    with pytest.raises(ValueError, match="empty source or destination"):
        get_config()


def test_css_map_duplicate_names(settings: SettingsWrapper):
    settings.TAILWIND_CLI_CSS_MAP = [
        ("admin.css", "admin1.output.css"),
        ("admin.css", "admin2.output.css"),
    ]
    with pytest.raises(ValueError, match="duplicate entry name"):
        get_config()


def test_css_map_single_file_still_works(settings: SettingsWrapper):
    settings.TAILWIND_CLI_SRC_CSS = "my/source.css"
    settings.TAILWIND_CLI_DIST_CSS = "my/output.css"
    c = get_config()
    assert len(c.css_entries) == 1
    assert c.css_entries[0].name == "tailwind"
    assert c.src_css == c.css_entries[0].src_css
    assert c.dist_css == c.css_entries[0].dist_css


def test_css_map_overwrite_default_config_false(settings: SettingsWrapper):
    settings.TAILWIND_CLI_CSS_MAP = [
        ("admin.css", "admin.output.css"),
    ]
    c = get_config()
    assert c.overwrite_default_config is False


# System binary support ---------------------------------------------------------------------------


def test_system_binary_happy_path(settings: SettingsWrapper, mocker: MockerFixture):
    """System binary resolved via shutil.which when USE_SYSTEM_BINARY is True."""
    settings.TAILWIND_CLI_USE_SYSTEM_BINARY = True
    mocker.patch("shutil.which", return_value="/opt/homebrew/bin/tailwindcss")
    # Avoid real subprocess calls during version detection
    mocker.patch("django_tailwind_cli.config.detect_binary_version", return_value=None)

    c = get_config()

    assert c.uses_system_binary is True
    assert c.cli_path == Path("/opt/homebrew/bin/tailwindcss")
    # Auto-download is implicitly disabled in system-binary mode
    assert c.automatic_download is False


def test_system_binary_uses_shutil_which_with_default_name(settings: SettingsWrapper, mocker: MockerFixture):
    """The default binary name is 'tailwindcss'."""
    settings.TAILWIND_CLI_USE_SYSTEM_BINARY = True
    which_mock = mocker.patch("shutil.which", return_value="/usr/local/bin/tailwindcss")
    mocker.patch("django_tailwind_cli.config.detect_binary_version", return_value=None)

    get_config()

    which_mock.assert_called_once_with("tailwindcss")


def test_system_binary_custom_name(settings: SettingsWrapper, mocker: MockerFixture):
    """TAILWIND_CLI_SYSTEM_BINARY_NAME overrides the lookup name."""
    settings.TAILWIND_CLI_USE_SYSTEM_BINARY = True
    settings.TAILWIND_CLI_SYSTEM_BINARY_NAME = "tailwindcss-extra"
    which_mock = mocker.patch("shutil.which", return_value="/opt/homebrew/bin/tailwindcss-extra")
    mocker.patch("django_tailwind_cli.config.detect_binary_version", return_value=None)

    c = get_config()

    which_mock.assert_called_once_with("tailwindcss-extra")
    assert c.cli_path == Path("/opt/homebrew/bin/tailwindcss-extra")


def test_system_binary_daisyui_default_name(settings: SettingsWrapper, mocker: MockerFixture):
    """When DaisyUI is enabled, the default system binary name is tailwindcss-extra."""
    settings.TAILWIND_CLI_USE_SYSTEM_BINARY = True
    settings.TAILWIND_CLI_USE_DAISY_UI = True
    which_mock = mocker.patch("shutil.which", return_value="/opt/homebrew/bin/tailwindcss-extra")
    mocker.patch("django_tailwind_cli.config.detect_binary_version", return_value=None)

    get_config()

    which_mock.assert_called_once_with("tailwindcss-extra")


def test_system_binary_not_found(settings: SettingsWrapper, mocker: MockerFixture):
    """A clear error is raised when the system binary cannot be located."""
    settings.TAILWIND_CLI_USE_SYSTEM_BINARY = True
    mocker.patch("shutil.which", return_value=None)

    with pytest.raises(ValueError, match="TAILWIND_CLI_USE_SYSTEM_BINARY"):
        get_config()


def test_system_binary_not_found_error_mentions_binary_name(settings: SettingsWrapper, mocker: MockerFixture):
    """The error message includes the binary name that was searched for."""
    settings.TAILWIND_CLI_USE_SYSTEM_BINARY = True
    settings.TAILWIND_CLI_SYSTEM_BINARY_NAME = "tailwindcss-extra"
    mocker.patch("shutil.which", return_value=None)

    with pytest.raises(ValueError, match="tailwindcss-extra"):
        get_config()


def test_system_binary_mutually_exclusive_with_cli_path(
    settings: SettingsWrapper, mocker: MockerFixture, tmp_path: Path
):
    """Combining TAILWIND_CLI_USE_SYSTEM_BINARY with TAILWIND_CLI_PATH raises."""
    settings.TAILWIND_CLI_USE_SYSTEM_BINARY = True
    settings.TAILWIND_CLI_PATH = str(tmp_path / "tailwindcss")
    mocker.patch("shutil.which", return_value="/opt/homebrew/bin/tailwindcss")

    with pytest.raises(
        ValueError,
        match="Cannot use TAILWIND_CLI_USE_SYSTEM_BINARY together with TAILWIND_CLI_PATH",
    ):
        get_config()


def test_system_binary_system_binary_name_without_flag_is_ignored(settings: SettingsWrapper):
    """Setting TAILWIND_CLI_SYSTEM_BINARY_NAME alone does not enable system mode."""
    settings.TAILWIND_CLI_SYSTEM_BINARY_NAME = "tailwindcss"
    c = get_config()
    assert c.uses_system_binary is False
    # Falls back to the normal download path
    assert ".django_tailwind_cli/tailwindcss" in str(c.cli_path)


def test_system_binary_empty_name_raises(settings: SettingsWrapper):
    """An empty TAILWIND_CLI_SYSTEM_BINARY_NAME is rejected."""
    settings.TAILWIND_CLI_USE_SYSTEM_BINARY = True
    settings.TAILWIND_CLI_SYSTEM_BINARY_NAME = ""

    with pytest.raises(ValueError, match="TAILWIND_CLI_SYSTEM_BINARY_NAME"):
        get_config()


def test_system_binary_version_match_no_warning(
    settings: SettingsWrapper, mocker: MockerFixture, recwarn: WarningsChecker
):
    """When system binary version matches TAILWIND_CLI_VERSION, no warning is emitted."""
    from semver import Version

    settings.TAILWIND_CLI_VERSION = "4.1.3"
    settings.TAILWIND_CLI_USE_SYSTEM_BINARY = True
    mocker.patch("shutil.which", return_value="/opt/homebrew/bin/tailwindcss")
    mocker.patch(
        "django_tailwind_cli.config.detect_binary_version",
        return_value=Version.parse("4.1.3"),
    )

    get_config()

    assert len(recwarn) == 0


def test_system_binary_version_mismatch_warns(settings: SettingsWrapper, mocker: MockerFixture):
    """Version mismatch with explicit TAILWIND_CLI_VERSION emits a warning."""
    from semver import Version

    settings.TAILWIND_CLI_VERSION = "4.1.3"
    settings.TAILWIND_CLI_USE_SYSTEM_BINARY = True
    mocker.patch("shutil.which", return_value="/opt/homebrew/bin/tailwindcss")
    mocker.patch(
        "django_tailwind_cli.config.detect_binary_version",
        return_value=Version.parse("4.2.0"),
    )

    with pytest.warns(UserWarning, match="4.1.3.*4.2.0"):
        get_config()


def test_system_binary_version_mismatch_with_latest_no_warning(
    settings: SettingsWrapper, mocker: MockerFixture, recwarn: WarningsChecker
):
    """When TAILWIND_CLI_VERSION is 'latest', version mismatch does not warn."""
    from semver import Version

    settings.TAILWIND_CLI_VERSION = "latest"
    settings.TAILWIND_CLI_USE_SYSTEM_BINARY = True
    mocker.patch("shutil.which", return_value="/opt/homebrew/bin/tailwindcss")
    mocker.patch(
        "django_tailwind_cli.config.detect_binary_version",
        return_value=Version.parse("4.2.0"),
    )

    get_config()

    # Filter out unrelated warnings (e.g. deprecation warnings from deps)
    user_warnings = [w for w in recwarn.list if issubclass(w.category, UserWarning)]
    assert len(user_warnings) == 0


def test_system_binary_version_detection_failure_no_warning(
    settings: SettingsWrapper, mocker: MockerFixture, recwarn: WarningsChecker
):
    """If version detection fails (subprocess error), no warning is emitted."""
    settings.TAILWIND_CLI_VERSION = "4.1.3"
    settings.TAILWIND_CLI_USE_SYSTEM_BINARY = True
    mocker.patch("shutil.which", return_value="/opt/homebrew/bin/tailwindcss")
    mocker.patch("django_tailwind_cli.config.detect_binary_version", return_value=None)

    get_config()

    user_warnings = [w for w in recwarn.list if issubclass(w.category, UserWarning)]
    assert len(user_warnings) == 0


# detect_binary_version helper --------------------------------------------------------------------


def test_detect_binary_version_parses_help_output(mocker: MockerFixture, tmp_path: Path):
    """detect_binary_version parses the version from tailwindcss --help output."""
    from django_tailwind_cli.config import detect_binary_version

    binary = tmp_path / "tailwindcss"
    binary.touch()

    # Clear lru_cache so previous tests don't leak
    detect_binary_version.cache_clear()

    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = mocker.Mock(
        returncode=0,
        stdout="≈ tailwindcss v4.1.3\n\nUsage:\n  tailwindcss [options]\n",
        stderr="",
    )

    version = detect_binary_version(binary)

    assert version is not None
    assert str(version) == "4.1.3"
    mock_run.assert_called_once()
    # Verify --help was used, not --version
    assert "--help" in mock_run.call_args[0][0]


def test_detect_binary_version_handles_subprocess_failure(mocker: MockerFixture, tmp_path: Path):
    """detect_binary_version returns None when subprocess raises."""
    import subprocess

    from django_tailwind_cli.config import detect_binary_version

    binary = tmp_path / "tailwindcss-fail"
    binary.touch()

    detect_binary_version.cache_clear()

    mocker.patch(
        "subprocess.run",
        side_effect=subprocess.SubprocessError("boom"),
    )

    assert detect_binary_version(binary) is None


def test_detect_binary_version_handles_timeout(mocker: MockerFixture, tmp_path: Path):
    """detect_binary_version returns None when subprocess times out."""
    import subprocess

    from django_tailwind_cli.config import detect_binary_version

    binary = tmp_path / "tailwindcss-timeout"
    binary.touch()

    detect_binary_version.cache_clear()

    mocker.patch(
        "subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="tailwindcss", timeout=5),
    )

    assert detect_binary_version(binary) is None


def test_detect_binary_version_handles_unparseable_output(mocker: MockerFixture, tmp_path: Path):
    """detect_binary_version returns None when version pattern is missing."""
    from django_tailwind_cli.config import detect_binary_version

    binary = tmp_path / "tailwindcss-weird"
    binary.touch()

    detect_binary_version.cache_clear()

    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = mocker.Mock(
        returncode=0,
        stdout="Welcome to a totally different tool\n",
        stderr="",
    )

    assert detect_binary_version(binary) is None


def test_detect_binary_version_handles_nonzero_exit(mocker: MockerFixture, tmp_path: Path):
    """detect_binary_version returns None when the subprocess exits non-zero."""
    from django_tailwind_cli.config import detect_binary_version

    binary = tmp_path / "tailwindcss-crash"
    binary.touch()

    detect_binary_version.cache_clear()

    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = mocker.Mock(returncode=1, stdout="", stderr="crash")

    assert detect_binary_version(binary) is None


def test_detect_binary_version_handles_semver_parse_failure(mocker: MockerFixture, tmp_path: Path):
    """Defensive: if the regex matches but Version.parse raises, return None."""
    from django_tailwind_cli.config import detect_binary_version

    binary = tmp_path / "tailwindcss-badparse"
    binary.touch()

    detect_binary_version.cache_clear()

    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = mocker.Mock(
        returncode=0,
        stdout="≈ tailwindcss v1.2.3\n",
        stderr="",
    )
    # Force semver.Version.parse to fail even though the regex matched.
    mocker.patch("django_tailwind_cli.config.Version.parse", side_effect=ValueError("simulated"))

    assert detect_binary_version(binary) is None
