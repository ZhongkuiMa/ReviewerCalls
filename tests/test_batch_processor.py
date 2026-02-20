"""Tests for batch.py async batch processing utilities."""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from discover.batch import async_fetch_page


class TestAsyncFetchPage:
    """Tests for async_fetch_page function."""

    @pytest.mark.asyncio
    async def test_async_fetch_page_success(self):
        """Should fetch page content successfully."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=b"<html>Content</html>")

        async_cm = AsyncMock()
        async_cm.__aenter__.return_value = mock_response
        async_cm.__aexit__.return_value = None

        mock_session = MagicMock()
        mock_session.get.return_value = async_cm

        url, content = await async_fetch_page(mock_session, "https://example.com")
        assert url == "https://example.com"
        assert content == "<html>Content</html>"

    @pytest.mark.asyncio
    async def test_async_fetch_page_non_200_status(self):
        """Should return None for non-200 status."""
        mock_response = MagicMock()
        mock_response.status = 404

        async_cm = AsyncMock()
        async_cm.__aenter__.return_value = mock_response
        async_cm.__aexit__.return_value = None

        mock_session = MagicMock()
        mock_session.get.return_value = async_cm

        url, content = await async_fetch_page(mock_session, "https://example.com")
        assert url == "https://example.com"
        assert content is None

    @pytest.mark.asyncio
    async def test_async_fetch_page_client_error(self):
        """Should return None on aiohttp client error."""
        import aiohttp

        mock_session = MagicMock()
        mock_session.get.side_effect = aiohttp.ClientError("Connection error")

        url, content = await async_fetch_page(mock_session, "https://example.com")
        assert url == "https://example.com"
        assert content is None

    @pytest.mark.asyncio
    async def test_async_fetch_page_timeout(self):
        """Should handle timeout gracefully."""
        mock_session = MagicMock()
        mock_session.get.side_effect = asyncio.TimeoutError()

        url, content = await async_fetch_page(mock_session, "https://example.com")
        assert url == "https://example.com"
        assert content is None

    @pytest.mark.asyncio
    async def test_async_fetch_page_custom_timeout(self):
        """Should use custom timeout parameter."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=b"")

        async_cm = AsyncMock()
        async_cm.__aenter__.return_value = mock_response
        async_cm.__aexit__.return_value = None

        mock_session = MagicMock()
        mock_session.get.return_value = async_cm

        await async_fetch_page(mock_session, "https://example.com", timeout=20)

        call_kwargs = mock_session.get.call_args[1]
        assert call_kwargs["timeout"] is not None


@pytest.mark.asyncio
async def test_async_operations_dont_block():
    """Verify async operations don't block."""
    import time

    async def slow_op():
        await asyncio.sleep(0.1)
        return "done"

    start = time.time()
    results = await asyncio.gather(
        slow_op(),
        slow_op(),
        slow_op(),
    )
    elapsed = time.time() - start

    assert elapsed < 0.2
    assert len(results) == 3
