"""Tests for HTTP utilities module.

This module tests the custom HTTP implementation that replaced the requests dependency.
Focuses on error handling paths that were previously uncovered.
"""

import socket
from pathlib import Path
from unittest.mock import patch
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
