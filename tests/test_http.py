"""Tests for HTTP utilities module.

This module tests the custom HTTP implementation that replaced the requests dependency.
Covers both the happy paths (200 responses, chunked downloads with progress callbacks)
and the error paths (timeouts, connection failures, HTTP 4xx/5xx, generic URLErrors).
"""

import socket
import errno
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError as UrllibHTTPError
from urllib.error import URLError

import pytest

from django_tailwind_cli.utils import http
from tests.helpers import install_fake_cli

# This module tests the HTTP layer itself, so it must see the real functions.
pytestmark = pytest.mark.unpatched_http


def urllib_error(code: int, msg: str, **hdrs: str) -> UrllibHTTPError:
    """An `HTTPError` shaped like the one urllib raises, with no body.

    `fp=None` is not a shortcut: urllib allocates a file object of its own in that case, which is
    exactly the resource `TestTheUrllibErrorIsClosed` is about.
    """
    return UrllibHTTPError(
        url="https://example.com",
        code=code,
        msg=msg,
        hdrs=hdrs,  # pyright: ignore[reportArgumentType]
        fp=None,
    )


class TestFetchRedirectLocation:
    """Test the fetch_redirect_location function error handling."""

    def test_fetch_redirect_location_timeout_error(self):
        """Test timeout error handling."""
        mock_error = URLError(socket.timeout("timeout"))

        with patch("django_tailwind_cli.utils.http.build_opener") as mock_build_opener:
            mock_opener = mock_build_opener.return_value
            mock_opener.open.side_effect = mock_error
            with pytest.raises(http.RequestTimeoutError, match="Request timeout"):
                http.fetch_redirect_location("https://example.com")

    def test_fetch_redirect_location_connection_error(self):
        """Test connection error handling."""
        mock_error = URLError(ConnectionRefusedError("connection refused"))

        with patch("django_tailwind_cli.utils.http.build_opener") as mock_build_opener:
            mock_opener = mock_build_opener.return_value
            mock_opener.open.side_effect = mock_error
            with pytest.raises(http.NetworkConnectionError, match="Connection error"):
                http.fetch_redirect_location("https://example.com")

    def test_fetch_redirect_location_generic_error(self):
        """Test generic URL error handling."""
        mock_error = URLError("generic error")

        with patch("django_tailwind_cli.utils.http.build_opener") as mock_build_opener:
            mock_opener = mock_build_opener.return_value
            mock_opener.open.side_effect = mock_error
            with pytest.raises(http.RequestError, match="URL error"):
                http.fetch_redirect_location("https://example.com")

    def test_fetch_redirect_location_timeout_error_direct(self):
        """Test direct timeout error handling."""
        with patch("django_tailwind_cli.utils.http.build_opener") as mock_build_opener:
            mock_opener = mock_build_opener.return_value
            mock_opener.open.side_effect = TimeoutError("timeout")
            with pytest.raises(http.RequestTimeoutError, match="Socket timeout"):
                http.fetch_redirect_location("https://example.com")

    def test_fetch_redirect_location_generic_exception(self):
        """Test generic exception handling."""
        with patch("django_tailwind_cli.utils.http.build_opener") as mock_build_opener:
            mock_opener = mock_build_opener.return_value
            mock_opener.open.side_effect = ValueError("unexpected")
            with pytest.raises(http.RequestError, match="Unexpected error"):
                http.fetch_redirect_location("https://example.com")


class TestDownloadWithProgress:
    """Test the download_with_progress function error handling."""

    def test_download_with_progress_timeout_error(self, tmp_path: Path):
        """Test download timeout error."""
        mock_error = URLError(socket.timeout("timeout"))
        filepath = tmp_path / "test_download.txt"

        with patch("django_tailwind_cli.utils.http.urlopen", side_effect=mock_error):
            with pytest.raises(http.RequestTimeoutError, match="Download timeout"):
                http.download_with_progress("https://example.com/file.txt", filepath)

    def test_download_with_progress_connection_error(self, tmp_path: Path):
        """Test download connection error."""
        mock_error = URLError(ConnectionRefusedError("connection refused"))
        filepath = tmp_path / "test_download.txt"

        with patch("django_tailwind_cli.utils.http.urlopen", side_effect=mock_error):
            with pytest.raises(http.NetworkConnectionError, match="Connection error"):
                http.download_with_progress("https://example.com/file.txt", filepath)

    def test_download_with_progress_timeout_error_direct(self, tmp_path: Path):
        """Test direct timeout error."""
        filepath = tmp_path / "test_download.txt"

        with patch("django_tailwind_cli.utils.http.urlopen", side_effect=TimeoutError("timeout")):
            with pytest.raises(http.RequestTimeoutError, match="Download timeout"):
                http.download_with_progress("https://example.com/file.txt", filepath)

    def test_download_with_progress_generic_exception(self, tmp_path: Path):
        """Test generic exception during download."""
        filepath = tmp_path / "test_download.txt"

        with patch("django_tailwind_cli.utils.http.urlopen", side_effect=ValueError("unexpected")):
            with pytest.raises(http.RequestError, match="Unexpected error"):
                http.download_with_progress("https://example.com/file.txt", filepath)


class TestGetContentSync:
    """Test the get_content_sync function error handling."""

    def test_get_content_sync_timeout_error(self):
        """Test content retrieval timeout."""
        mock_error = URLError(socket.timeout("timeout"))

        with patch("django_tailwind_cli.utils.http.urlopen", side_effect=mock_error):
            with pytest.raises(http.RequestTimeoutError, match="Request timeout"):
                http.get_content_sync("https://example.com/api")

    def test_get_content_sync_connection_error(self):
        """Test content retrieval connection error."""
        mock_error = URLError(ConnectionRefusedError("connection refused"))

        with patch("django_tailwind_cli.utils.http.urlopen", side_effect=mock_error):
            with pytest.raises(http.NetworkConnectionError, match="Connection error"):
                http.get_content_sync("https://example.com/api")

    def test_get_content_sync_timeout_error_direct(self):
        """Test direct timeout error."""
        with patch("django_tailwind_cli.utils.http.urlopen", side_effect=TimeoutError("timeout")):
            with pytest.raises(http.RequestTimeoutError, match="Request timeout"):
                http.get_content_sync("https://example.com/api")

    def test_get_content_sync_generic_exception(self):
        """Test generic exception during content retrieval."""
        with patch("django_tailwind_cli.utils.http.urlopen", side_effect=ValueError("unexpected")):
            with pytest.raises(http.RequestError, match="Unexpected error"):
                http.get_content_sync("https://example.com/api")


def _build_response_mock(
    *,
    code: int = 200,
    location: str | None = None,
    content_length: str | None = None,
    body: bytes = b"",
    reason: str = "OK",
) -> MagicMock:
    """Build a minimal mock for a urllib response used as a context manager."""
    response = MagicMock()
    response.getcode.return_value = code
    response.reason = reason
    response.headers = {}
    if location is not None:
        response.headers["Location"] = location
    if content_length is not None:
        response.headers["Content-Length"] = content_length
    response.read = BytesIO(body).read

    # Context manager plumbing
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    return response


class TestFetchRedirectLocationHappyPaths:
    """Happy-path tests for fetch_redirect_location."""

    def test_redirect_302_returns_location(self):
        response = _build_response_mock(code=302, location="https://example.com/target")

        with patch("django_tailwind_cli.utils.http.build_opener") as mock_build_opener:
            mock_build_opener.return_value.open.return_value = response

            success, location = http.fetch_redirect_location("https://example.com")

        assert success is True
        assert location == "https://example.com/target"

    def test_200_response_returns_success_no_location(self):
        response = _build_response_mock(code=200)

        with patch("django_tailwind_cli.utils.http.build_opener") as mock_build_opener:
            mock_build_opener.return_value.open.return_value = response

            success, location = http.fetch_redirect_location("https://example.com")

        assert success is True
        assert location is None

    def test_non_redirect_non_200_returns_failure(self):
        response = _build_response_mock(code=204)

        with patch("django_tailwind_cli.utils.http.build_opener") as mock_build_opener:
            mock_build_opener.return_value.open.return_value = response

            success, location = http.fetch_redirect_location("https://example.com")

        assert success is False
        assert location is None

    def test_urllib_httperror_with_redirect_code_returns_location(self):
        """urllib sometimes raises HTTPError for 3xx even with NoRedirectHandler."""
        error = urllib_error(301, "Moved Permanently", Location="https://example.com/new")

        with patch("django_tailwind_cli.utils.http.build_opener") as mock_build_opener:
            mock_build_opener.return_value.open.side_effect = error

            success, location = http.fetch_redirect_location("https://example.com")

        assert success is True
        assert location == "https://example.com/new"

    def test_urllib_httperror_with_non_redirect_code_returns_failure(self):
        error = urllib_error(404, "Not Found")

        with patch("django_tailwind_cli.utils.http.build_opener") as mock_build_opener:
            mock_build_opener.return_value.open.side_effect = error

            success, location = http.fetch_redirect_location("https://example.com")

        assert success is False
        assert location is None


class TestDownloadWithProgressHappyPath:
    """Happy-path tests for download_with_progress."""

    def test_download_writes_chunks_and_invokes_progress_callback(self, tmp_path: Path):
        body = b"A" * 20000  # slightly over two 8192 chunks
        response = _build_response_mock(code=200, content_length=str(len(body)), body=body)
        filepath = tmp_path / "subdir" / "downloaded.bin"

        progress_events: list[tuple[int, int, float]] = []

        def progress_callback(downloaded: int, total_size: int, progress: float) -> None:
            progress_events.append((downloaded, total_size, progress))

        with patch("django_tailwind_cli.utils.http.urlopen", return_value=response):
            http.download_with_progress("https://example.com/file.bin", filepath, progress_callback=progress_callback)

        # Parent directory auto-created
        assert filepath.parent.exists()
        assert filepath.read_bytes() == body
        # Progress callback invoked for each chunk (at least 3 for 20000 bytes / 8192)
        assert len(progress_events) >= 3
        # Final event reports full size and 100%
        assert progress_events[-1][0] == len(body)
        assert progress_events[-1][1] == len(body)
        assert abs(progress_events[-1][2] - 100.0) < 0.01

    def test_download_without_content_length_skips_progress_callback(self, tmp_path: Path):
        body = b"small payload"
        response = _build_response_mock(code=200, content_length=None, body=body)
        filepath = tmp_path / "nocontentlength.bin"

        calls: list[object] = []

        def progress_callback(downloaded: int, total_size: int, progress: float) -> None:  # noqa: ARG001
            calls.append(object())

        with patch("django_tailwind_cli.utils.http.urlopen", return_value=response):
            http.download_with_progress("https://example.com/file.bin", filepath, progress_callback=progress_callback)

        assert filepath.read_bytes() == body
        # Without Content-Length, total_size stays 0 and the callback branch is skipped.
        assert calls == []

    def test_download_without_callback_still_writes_file(self, tmp_path: Path):
        body = b"hello world"
        response = _build_response_mock(code=200, content_length=str(len(body)), body=body)
        filepath = tmp_path / "nocallback.bin"

        with patch("django_tailwind_cli.utils.http.urlopen", return_value=response):
            http.download_with_progress("https://example.com/file.bin", filepath)

        assert filepath.read_bytes() == body


class TestDownloadWithProgressErrorBranches:
    """Missing error-branch coverage for download_with_progress."""

    def test_http_4xx_response_raises_http_error(self, tmp_path: Path):
        response = _build_response_mock(code=404, reason="Not Found")
        filepath = tmp_path / "test.bin"

        with patch("django_tailwind_cli.utils.http.urlopen", return_value=response):
            with pytest.raises(http.HTTPError, match="HTTP 404"):
                http.download_with_progress("https://example.com/missing.bin", filepath)

    def test_urllib_httperror_raises_http_error(self, tmp_path: Path):
        error = urllib_error(500, "Internal Server Error")
        filepath = tmp_path / "test.bin"

        with patch("django_tailwind_cli.utils.http.urlopen", side_effect=error):
            with pytest.raises(http.HTTPError, match="HTTP 500"):
                http.download_with_progress("https://example.com/file.bin", filepath)

    def test_generic_urlerror_raises_request_error(self, tmp_path: Path):
        """URLError with a non-timeout, non-connection reason."""
        filepath = tmp_path / "test.bin"

        with patch(
            "django_tailwind_cli.utils.http.urlopen",
            side_effect=URLError("ssl handshake failure"),
        ):
            with pytest.raises(http.RequestError, match="URL error"):
                http.download_with_progress("https://example.com/file.bin", filepath)

    def test_os_error_opening_temporary_file_raises_request_error(self, tmp_path: Path):
        body = b"data"
        response = _build_response_mock(code=200, content_length=str(len(body)), body=body)
        filepath = tmp_path / "readonly.bin"

        # Make the file unwritable by patching Path.open to raise OSError
        with patch("django_tailwind_cli.utils.http.urlopen", return_value=response):
            with patch.object(Path, "open", side_effect=OSError("disk full")):
                with pytest.raises(http.RequestError, match="File error"):
                    http.download_with_progress("https://example.com/file.bin", filepath)


class TestGetContentSyncHappyPath:
    """Happy-path tests for get_content_sync."""

    def test_returns_response_bytes(self):
        body = b'{"version": "4.1.3"}'
        response = _build_response_mock(code=200, body=body)

        with patch("django_tailwind_cli.utils.http.urlopen", return_value=response):
            result = http.get_content_sync("https://example.com/api")

        assert result == body


class TestGetContentSyncErrorBranches:
    """Missing error-branch coverage for get_content_sync."""

    def test_http_4xx_response_raises_http_error(self):
        response = _build_response_mock(code=403, reason="Forbidden")

        with patch("django_tailwind_cli.utils.http.urlopen", return_value=response):
            with pytest.raises(http.HTTPError, match="HTTP 403"):
                http.get_content_sync("https://example.com/api")

    def test_urllib_httperror_raises_http_error(self):
        error = urllib_error(502, "Bad Gateway")

        with patch("django_tailwind_cli.utils.http.urlopen", side_effect=error):
            with pytest.raises(http.HTTPError, match="HTTP 502"):
                http.get_content_sync("https://example.com/api")

    def test_generic_urlerror_raises_request_error(self):
        with patch(
            "django_tailwind_cli.utils.http.urlopen",
            side_effect=URLError("no route to host"),
        ):
            with pytest.raises(http.RequestError, match="URL error"):
                http.get_content_sync("https://example.com/api")


class TestNoRedirectHandler:
    """Direct tests for NoRedirectHandler's redirect methods."""

    @pytest.mark.parametrize(
        "method_name",
        ["http_error_301", "http_error_302", "http_error_303", "http_error_307", "http_error_308"],
    )
    def test_redirect_handlers_return_fp_unchanged(self, method_name: str):
        handler = http.NoRedirectHandler()
        method = getattr(handler, method_name)
        fp = MagicMock()

        result = method(MagicMock(), fp, 301, "msg", MagicMock())

        assert result is fp


class TestExceptionClasses:
    """Test the custom exception classes."""

    def test_request_error_is_base_exception(self):
        """Test that RequestError is the base exception."""
        with pytest.raises(http.RequestError):
            raise http.RequestError("test error")

    def test_http_error_inherits_from_request_error(self):
        """Test HTTPError inheritance."""
        with pytest.raises(http.RequestError):
            raise http.HTTPError("http error")

    def test_network_connection_error_inherits_from_request_error(self):
        """Test NetworkConnectionError inheritance."""
        with pytest.raises(http.RequestError):
            raise http.NetworkConnectionError("connection error")

    def test_request_timeout_error_inherits_from_request_error(self):
        """Test RequestTimeoutError inheritance."""
        with pytest.raises(http.RequestError):
            raise http.RequestTimeoutError("timeout error")


class TestTheUrllibErrorIsClosed:
    """The three branches that catch urllib's HTTPError have to close it — see http.py.

    Asserted on the file object rather than on the ResourceWarning it would otherwise trigger:
    that warning only exists on Python 3.14+, so a test watching for it would be vacuously green
    on every older interpreter in the matrix.
    """

    @pytest.mark.parametrize(
        ("error", "expected"),
        [
            (
                urllib_error(301, "Moved Permanently", Location="https://example.com/new"),
                (True, "https://example.com/new"),
            ),
            (urllib_error(404, "Not Found"), (False, None)),
        ],
        ids=["redirect", "non-redirect"],
    )
    def test_fetch_redirect_location_closes_it(self, error: UrllibHTTPError, expected: tuple[bool, str | None]):
        with patch("django_tailwind_cli.utils.http.build_opener") as mock_build_opener:
            mock_build_opener.return_value.open.side_effect = error
            result = http.fetch_redirect_location("https://example.com")

        # The Location header is read out of the error, so closing must not cost us that.
        assert result == expected
        assert error.fp.closed

    def test_get_content_sync_closes_it(self):
        error = urllib_error(404, "Not Found")

        with patch("django_tailwind_cli.utils.http.urlopen", side_effect=error):
            with pytest.raises(http.HTTPError):
                http.get_content_sync("https://example.com")

        assert error.fp.closed

    def test_download_with_progress_closes_it(self, tmp_path: Path):
        error = urllib_error(404, "Not Found")

        with patch("django_tailwind_cli.utils.http.urlopen", side_effect=error):
            with pytest.raises(http.HTTPError):
                http.download_with_progress("https://example.com", tmp_path / "cli")

        assert error.fp.closed


class TestAtomicDownloads:
    @pytest.mark.parametrize("existing", [False, True])
    @pytest.mark.parametrize("failure", ["timeout", "short", "interrupt"])
    def test_failed_transfer_leaves_destination_untouched(self, tmp_path: Path, existing: bool, failure: str):
        filepath = tmp_path / "tailwindcss"
        if existing:
            install_fake_cli(filepath, content=b"working binary")
        before_mode = filepath.stat().st_mode if existing else None
        response = _build_response_mock(content_length="10")
        endings = {"timeout": TimeoutError("connection lost"), "short": b"", "interrupt": KeyboardInterrupt()}
        response.read = MagicMock(side_effect=[b"part", endings[failure]])
        expected = KeyboardInterrupt if failure == "interrupt" else http.RequestError

        with patch("django_tailwind_cli.utils.http.urlopen", return_value=response):
            with pytest.raises(expected):
                http.download_with_progress("https://example.com/cli", filepath)

        if existing:
            assert filepath.read_bytes() == b"working binary"
            assert filepath.stat().st_mode == before_mode
        else:
            assert not filepath.exists()
        assert set(tmp_path.iterdir()) == ({filepath} if existing else set())

    @pytest.mark.parametrize("content_length", ["0", "2", "10"])
    def test_content_length_must_match_bytes_received(self, tmp_path: Path, content_length: str):
        filepath = tmp_path / "tailwindcss"
        response = _build_response_mock(content_length=content_length, body=b"data")
        with patch("django_tailwind_cli.utils.http.urlopen", return_value=response):
            with pytest.raises(http.RequestError, match="Content-Length mismatch"):
                http.download_with_progress("https://example.com/cli", filepath)
        assert list(tmp_path.iterdir()) == []

    @pytest.mark.parametrize("existing", [False, True])
    def test_destination_is_published_only_after_transfer(self, tmp_path: Path, existing: bool):
        filepath = tmp_path / "tailwindcss"
        if existing:
            install_fake_cli(filepath, content=b"working binary")
        body = b"A" * 20000
        response = _build_response_mock(content_length=str(len(body)), body=body)
        progress_events: list[int] = []

        def progress_callback(downloaded: int, total_size: int, progress: float) -> None:
            progress_events.append(downloaded)
            assert total_size == len(body)
            assert progress > 0
            if existing:
                assert filepath.read_bytes() == b"working binary"
            else:
                assert not filepath.exists()

        with patch("django_tailwind_cli.utils.http.urlopen", return_value=response):
            http.download_with_progress("https://example.com/cli", filepath, progress_callback=progress_callback)

        assert progress_events == [8192, 16384, 20000]
        assert filepath.read_bytes() == body
        assert set(tmp_path.iterdir()) == {filepath}

    def test_failed_replace_preserves_binary_and_removes_temporary_files(self, tmp_path: Path):
        filepath = install_fake_cli(tmp_path / "tailwindcss", content=b"working binary")
        before_mode = filepath.stat().st_mode
        response = _build_response_mock(content_length="4", body=b"data")
        with (
            patch("django_tailwind_cli.utils.http.urlopen", return_value=response),
            patch.object(Path, "replace", side_effect=PermissionError("replacement denied")),
        ):
            with pytest.raises(http.RequestError, match="replacement denied"):
                http.download_with_progress("https://example.com/cli", filepath)

        assert filepath.read_bytes() == b"working binary"
        assert filepath.stat().st_mode == before_mode
        assert set(tmp_path.iterdir()) == {filepath}

    def test_disk_full_during_write_preserves_destination(self, tmp_path: Path):
        filepath = install_fake_cli(tmp_path / "tailwindcss", content=b"working binary")
        before_mode = filepath.stat().st_mode
        response = _build_response_mock(content_length="4", body=b"data")
        with (
            patch("django_tailwind_cli.utils.http.urlopen", return_value=response),
            patch.object(Path, "open") as open_file,
        ):
            writer = open_file.return_value.__enter__.return_value
            writer.write.side_effect = OSError(errno.ENOSPC, "No space left on device")
            with pytest.raises(http.RequestError, match="File error") as error:
                http.download_with_progress("https://example.com/cli", filepath)
            assert isinstance(error.value.__cause__, OSError)
            assert error.value.__cause__.errno == errno.ENOSPC
            writer.write.assert_called_once_with(b"data")

        assert filepath.read_bytes() == b"working binary"
        assert filepath.stat().st_mode == before_mode
        assert set(tmp_path.iterdir()) == {filepath}
