"""Tests for HTTP utilities module.

This module tests the custom HTTP implementation that replaced the requests dependency.
Covers both the happy paths (200 responses, chunked downloads with progress callbacks)
and the error paths (timeouts, connection failures, HTTP 4xx/5xx, generic URLErrors).
"""

import socket
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError as UrllibHTTPError
from urllib.error import URLError

import pytest

from django_tailwind_cli.utils import http


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
        error = UrllibHTTPError(
            url="https://example.com",
            code=301,
            msg="Moved Permanently",
            hdrs={"Location": "https://example.com/new"},  # pyright: ignore[reportArgumentType]
            fp=None,
        )

        with patch("django_tailwind_cli.utils.http.build_opener") as mock_build_opener:
            mock_build_opener.return_value.open.side_effect = error

            success, location = http.fetch_redirect_location("https://example.com")

        assert success is True
        assert location == "https://example.com/new"

    def test_urllib_httperror_with_non_redirect_code_returns_failure(self):
        error = UrllibHTTPError(
            url="https://example.com",
            code=404,
            msg="Not Found",
            hdrs={},  # pyright: ignore[reportArgumentType]
            fp=None,
        )

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
        error = UrllibHTTPError(
            url="https://example.com",
            code=500,
            msg="Internal Server Error",
            hdrs={},  # pyright: ignore[reportArgumentType]
            fp=None,
        )
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

    def test_os_error_during_file_write_raises_request_error(self, tmp_path: Path):
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
        error = UrllibHTTPError(
            url="https://example.com",
            code=502,
            msg="Bad Gateway",
            hdrs={},  # pyright: ignore[reportArgumentType]
            fp=None,
        )

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
