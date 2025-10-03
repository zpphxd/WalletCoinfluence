"""Base client with retry logic and error handling."""

import logging
from typing import Any, Dict, Optional
import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Custom exception for API errors."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class BaseAPIClient:
    """Base HTTP client with retry logic and timeouts."""

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
    ):
        """Initialize base client.

        Args:
            base_url: Base URL for API
            api_key: Optional API key
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.client = httpx.AsyncClient(timeout=timeout)

    def _get_headers(self) -> Dict[str, str]:
        """Get default headers for requests."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPStatusError)),
    )
    async def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Make GET request with retry logic.

        Args:
            endpoint: API endpoint (without base URL)
            params: Query parameters
            headers: Additional headers

        Returns:
            JSON response

        Raises:
            APIError: If request fails
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        request_headers = self._get_headers()
        if headers:
            request_headers.update(headers)

        try:
            logger.debug(f"GET {url} with params {params}")
            response = await self.client.get(url, params=params, headers=request_headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
            raise APIError(f"HTTP {e.response.status_code}: {e.response.text}", e.response.status_code)
        except httpx.TimeoutException as e:
            logger.error(f"Timeout error for {url}")
            raise APIError(f"Request timeout for {url}")
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            raise APIError(f"Unexpected error: {str(e)}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPStatusError)),
    )
    async def post(
        self,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Make POST request with retry logic.

        Args:
            endpoint: API endpoint
            data: Request body
            headers: Additional headers

        Returns:
            JSON response

        Raises:
            APIError: If request fails
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        request_headers = self._get_headers()
        if headers:
            request_headers.update(headers)

        try:
            logger.debug(f"POST {url} with data {data}")
            response = await self.client.post(url, json=data, headers=request_headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
            raise APIError(f"HTTP {e.response.status_code}: {e.response.text}", e.response.status_code)
        except httpx.TimeoutException:
            logger.error(f"Timeout error for {url}")
            raise APIError(f"Request timeout for {url}")
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            raise APIError(f"Unexpected error: {str(e)}")

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()
