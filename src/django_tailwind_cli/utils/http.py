"""HTTP utilities using urllib instead of requests."""

from __future__ import annotations

import socket
from pathlib import Path
from typing import TYPE_CHECKING
from collections.abc import Callable
from urllib.error import HTTPError as UrllibHTTPError
from urllib.error import URLError
from urllib.request import Request, urlopen, HTTPRedirectHandler, build_opener
from typing import IO
from http.client import HTTPMessage

if TYPE_CHECKING:
    pass


class RequestError(Exception):
    """Base exception for HTTP requests."""


class HTTPError(RequestError):
    """HTTP status error."""


class NetworkConnectionError(RequestError):
    """Network connection error."""


class RequestTimeoutError(RequestError):
    """Request timeout error."""


class NoRedirectHandler(HTTPRedirectHandler):
    """HTTP redirect handler that captures redirect information without following."""

    def http_error_302(self, req: Request, fp: IO[bytes], code: int, msg: str, headers: HTTPMessage) -> IO[bytes]:  # noqa: ARG002
        """Handle 302 Found redirects."""
        return fp

    def http_error_301(self, req: Request, fp: IO[bytes], code: int, msg: str, headers: HTTPMessage) -> IO[bytes]:  # noqa: ARG002
        """Handle 301 Moved Permanently redirects."""
        return fp

    def http_error_303(self, req: Request, fp: IO[bytes], code: int, msg: str, headers: HTTPMessage) -> IO[bytes]:  # noqa: ARG002
        """Handle 303 See Other redirects."""
        return fp

    def http_error_307(self, req: Request, fp: IO[bytes], code: int, msg: str, headers: HTTPMessage) -> IO[bytes]:  # noqa: ARG002
        """Handle 307 Temporary Redirect redirects."""
        return fp

    def http_error_308(self, req: Request, fp: IO[bytes], code: int, msg: str, headers: HTTPMessage) -> IO[bytes]:  # noqa: ARG002
        """Handle 308 Permanent Redirect redirects."""
        return fp


def fetch_redirect_location(url: str, timeout: int = 10) -> tuple[bool, str | None]:
    """Fetch redirect location from a URL.

    Args:
        url: URL to fetch from
        timeout: Request timeout in seconds

    Returns:
        Tuple of (success, location_header)

    Raises:
        RequestError: On network or HTTP errors
    """
    try:
        # Create opener with no redirect handler to capture redirect responses
        opener = build_opener(NoRedirectHandler)

        req = Request(url)
        # Set User-Agent to avoid blocking
        req.add_header("User-Agent", "django-tailwind-cli")

        with opener.open(req, timeout=timeout) as response:
            # Check if it's a redirect status
            if response.getcode() in (301, 302, 303, 307, 308):
                location = response.headers.get("Location")
                return True, location
            elif response.getcode() == 200:
                return True, None
            else:
                return False, None

    except UrllibHTTPError as e:
        # Handle redirect responses that urllib might treat as errors
        if e.code in (301, 302, 303, 307, 308):
            location = e.headers.get("Location")
            return True, location
        return False, None
    except URLError as e:
        if isinstance(e.reason, socket.timeout):
            raise RequestTimeoutError(f"Request timeout: {e}") from e
        elif isinstance(e.reason, (ConnectionRefusedError, socket.gaierror)):
            raise NetworkConnectionError(f"Connection error: {e}") from e
        else:
            raise RequestError(f"URL error: {e}") from e
    except TimeoutError as e:
        raise RequestTimeoutError(f"Socket timeout: {e}") from e
    except Exception as e:
        raise RequestError(f"Unexpected error: {e}") from e


def download_with_progress(
    url: str, filepath: Path, timeout: int = 30, progress_callback: Callable[[int, int, float], None] | None = None
) -> None:
    """Download a file with progress indication.

    Args:
        url: Download URL
        filepath: Destination file path
        timeout: Request timeout in seconds
        progress_callback: Optional callback for progress updates

    Raises:
        RequestError: On network or HTTP errors
    """
    try:
        req = Request(url)
        req.add_header("User-Agent", "django-tailwind-cli")

        with urlopen(req, timeout=timeout) as response:
            # Check for HTTP errors
            if response.getcode() >= 400:
                raise HTTPError(f"HTTP {response.getcode()}: {response.reason}")

            # Get content length for progress tracking
            content_length_header = response.headers.get("Content-Length")
            total_size = int(content_length_header) if content_length_header else 0

            # Ensure parent directory exists
            filepath.parent.mkdir(parents=True, exist_ok=True)

            downloaded = 0
            chunk_size = 8192

            with filepath.open("wb") as f:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break

                    f.write(chunk)
                    downloaded += len(chunk)

                    # Call progress callback if provided
                    if progress_callback and total_size > 0:
                        progress = (downloaded / total_size) * 100
                        progress_callback(downloaded, total_size, progress)

    except UrllibHTTPError as e:
        raise HTTPError(f"HTTP {e.code}: {e.reason}") from e
    except URLError as e:
        if isinstance(e.reason, socket.timeout):
            raise RequestTimeoutError(f"Download timeout: {e}") from e
        elif isinstance(e.reason, (ConnectionRefusedError, socket.gaierror)):
            raise NetworkConnectionError(f"Connection error: {e}") from e
        else:
            raise RequestError(f"URL error: {e}") from e
    except TimeoutError as e:
        raise RequestTimeoutError(f"Download timeout: {e}") from e
    except OSError as e:
        raise RequestError(f"File error: {e}") from e
    except Exception as e:
        raise RequestError(f"Unexpected error: {e}") from e


def get_content_sync(url: str, timeout: int = 30) -> bytes:
    """Get content from URL synchronously.

    Args:
        url: URL to fetch from
        timeout: Request timeout in seconds

    Returns:
        Response content as bytes

    Raises:
        RequestError: On network or HTTP errors
    """
    try:
        req = Request(url)
        req.add_header("User-Agent", "django-tailwind-cli")

        with urlopen(req, timeout=timeout) as response:
            if response.getcode() >= 400:
                raise HTTPError(f"HTTP {response.getcode()}: {response.reason}")
            return response.read()

    except UrllibHTTPError as e:
        raise HTTPError(f"HTTP {e.code}: {e.reason}") from e
    except URLError as e:
        if isinstance(e.reason, socket.timeout):
            raise RequestTimeoutError(f"Request timeout: {e}") from e
        elif isinstance(e.reason, (ConnectionRefusedError, socket.gaierror)):
            raise NetworkConnectionError(f"Connection error: {e}") from e
        else:
            raise RequestError(f"URL error: {e}") from e
    except TimeoutError as e:
        raise RequestTimeoutError(f"Request timeout: {e}") from e
    except Exception as e:
        raise RequestError(f"Unexpected error: {e}") from e
