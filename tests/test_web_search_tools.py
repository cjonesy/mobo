"""
Unit tests for web search tools with mocked Google API responses.
"""

import json
import pytest
from unittest.mock import Mock, patch, AsyncMock
from googleapiclient.errors import HttpError

from mobo.tools.web_search_tools import _search_web_impl, _search_images_impl


@pytest.fixture
def mock_google_service():
    """Mock Google API service with search results."""
    service = Mock()
    cse_mock = Mock()
    list_mock = Mock()

    # Mock successful search response
    mock_response = {
        "items": [
            {
                "title": "Python Programming Language",
                "link": "https://www.python.org/",
                "snippet": "Python is a programming language that lets you work quickly",
                "displayLink": "python.org",
            },
            {
                "title": "Learn Python - Tutorial",
                "link": "https://www.learnpython.org/",
                "snippet": "Learn Python programming online with interactive tutorials",
                "displayLink": "learnpython.org",
            },
        ],
        "searchInformation": {"totalResults": "1000000", "searchTime": 0.45},
    }

    list_mock.execute.return_value = mock_response
    cse_mock.list.return_value = list_mock
    service.cse.return_value = cse_mock

    return service


@pytest.fixture
def mock_empty_response():
    """Mock Google API service with no results."""
    service = Mock()
    cse_mock = Mock()
    list_mock = Mock()

    # Mock empty search response
    mock_response = {"searchInformation": {"totalResults": "0", "searchTime": 0.12}}

    list_mock.execute.return_value = mock_response
    cse_mock.list.return_value = list_mock
    service.cse.return_value = cse_mock

    return service


class TestWebSearchTools:
    """Test suite for web search tools."""

    @patch("mobo.tools.web_search_tools.build")
    @patch("mobo.tools.web_search_tools.get_google_custom_search_api_key")
    @patch("mobo.tools.web_search_tools.get_google_cse_id")
    @pytest.mark.asyncio
    async def test_search_web_success(
        self, mock_get_cse_id, mock_get_api_key, mock_build, mock_google_service
    ):
        """Test successful web search."""
        # Setup mocks
        mock_get_api_key.return_value = "test_api_key"
        mock_get_cse_id.return_value = "test_cse_id"
        mock_build.return_value = mock_google_service

        # Execute search
        result = await _search_web_impl("Python programming", num_results=2)

        # Verify API was called correctly
        mock_build.assert_called_once_with(
            "customsearch", "v1", developerKey="test_api_key"
        )
        mock_google_service.cse().list.assert_called_once_with(
            q="Python programming", cx="test_cse_id", num=2, safe="off"
        )

        # Verify result format
        result_data = json.loads(result)
        assert result_data["success"] is True
        assert result_data["query"] == "Python programming"
        assert "Python Programming Language" in result
        assert "https://www.python.org/" in result
        assert "Python is a programming language" in result
        assert result_data["total_results"] == "1000000"
        assert result_data["search_time"] == 0.45

    @patch("mobo.tools.web_search_tools.build")
    @patch("mobo.tools.web_search_tools.get_google_custom_search_api_key")
    @patch("mobo.tools.web_search_tools.get_google_cse_id")
    @pytest.mark.asyncio
    async def test_search_web_no_results(
        self, mock_get_cse_id, mock_get_api_key, mock_build, mock_empty_response
    ):
        """Test web search with no results."""
        # Setup mocks
        mock_get_api_key.return_value = "test_api_key"
        mock_get_cse_id.return_value = "test_cse_id"
        mock_build.return_value = mock_empty_response

        # Execute search
        result = await _search_web_impl("nonexistent query")

        # Verify result
        assert "No search results found for 'nonexistent query'" in result

    @patch("mobo.tools.web_search_tools.build")
    @patch("mobo.tools.web_search_tools.get_google_custom_search_api_key")
    @patch("mobo.tools.web_search_tools.get_google_cse_id")
    @pytest.mark.asyncio
    async def test_search_web_api_error(
        self, mock_get_cse_id, mock_get_api_key, mock_build
    ):
        """Test web search with API error."""
        # Setup mocks
        mock_get_api_key.return_value = "test_api_key"
        mock_get_cse_id.return_value = "test_cse_id"

        # Mock HTTP error
        error_mock = Mock()
        error_mock.status_code = 403
        error_mock.error_details = "Daily quota exceeded"

        service_mock = Mock()
        service_mock.cse().list().execute.side_effect = HttpError(
            resp=Mock(status=403),
            content=b'{"error": {"message": "Daily quota exceeded"}}',
        )
        mock_build.return_value = service_mock

        # Execute search
        result = await _search_web_impl("test query")

        # Verify error handling
        assert "Search failed due to API error" in result

    @patch("mobo.tools.web_search_tools.get_google_custom_search_api_key")
    @pytest.mark.asyncio
    async def test_search_web_missing_api_key(self, mock_get_api_key):
        """Test web search with missing API key."""
        # Mock missing API key
        mock_get_api_key.side_effect = ValueError(
            "Google Custom Search API key not configured"
        )

        # Execute search
        result = await _search_web_impl("test query")

        # Verify error handling
        assert (
            "Search unavailable: Google Custom Search API key not configured" in result
        )

    @patch("mobo.tools.web_search_tools.build")
    @patch("mobo.tools.web_search_tools.get_google_custom_search_api_key")
    @patch("mobo.tools.web_search_tools.get_google_cse_id")
    @pytest.mark.asyncio
    async def test_search_images_success(
        self, mock_get_cse_id, mock_get_api_key, mock_build
    ):
        """Test successful image search."""
        # Setup mocks
        mock_get_api_key.return_value = "test_api_key"
        mock_get_cse_id.return_value = "test_cse_id"

        # Mock image search response
        service = Mock()
        cse_mock = Mock()
        list_mock = Mock()

        mock_response = {
            "items": [
                {
                    "title": "Cute Cat Photo",
                    "link": "https://example.com/cat1.jpg",
                    "displayLink": "example.com",
                },
                {
                    "title": "Adorable Kitten",
                    "link": "https://example.com/cat2.jpg",
                    "displayLink": "example.com",
                },
            ],
            "searchInformation": {"totalResults": "50000"},
        }

        list_mock.execute.return_value = mock_response
        cse_mock.list.return_value = list_mock
        service.cse.return_value = cse_mock
        mock_build.return_value = service

        # Execute image search
        result = await _search_images_impl(
            "cute cats", num_results=2, image_size="medium"
        )

        # Verify API was called correctly
        service.cse().list.assert_called_once_with(
            q="cute cats",
            cx="test_cse_id",
            num=2,
            safe="active",
            searchType="image",
            imgSize="medium",
        )

        # Verify result format
        result_data = json.loads(result)
        assert result_data["success"] is True
        assert result_data["query"] == "cute cats"
        assert "Cute Cat Photo" in result
        assert "https://example.com/cat1.jpg" in result
        assert result_data["total_results"] == "50000"

    @pytest.mark.asyncio
    async def test_search_web_parameter_validation(self):
        """Test that search parameters are properly validated."""
        with (
            patch(
                "mobo.tools.web_search_tools.get_google_custom_search_api_key"
            ) as mock_get_api_key,
            patch("mobo.tools.web_search_tools.get_google_cse_id") as mock_get_cse_id,
            patch("mobo.tools.web_search_tools.build") as mock_build,
        ):

            mock_get_api_key.return_value = "test_api_key"
            mock_get_cse_id.return_value = "test_cse_id"

            # Mock successful response
            service = Mock()
            cse_mock = Mock()
            list_mock = Mock()

            mock_response = {
                "items": [
                    {
                        "title": "Test",
                        "link": "http://test.com",
                        "snippet": "Test snippet",
                    }
                ],
                "searchInformation": {"totalResults": "1", "searchTime": 0.1},
            }

            list_mock.execute.return_value = mock_response
            cse_mock.list.return_value = list_mock
            service.cse.return_value = cse_mock
            mock_build.return_value = service

            # Test with num_results > 10 (should be capped at 10)
            await _search_web_impl("test", num_results=15)

            # Verify num parameter was capped at 10
            service.cse().list.assert_called_once_with(
                q="test",
                cx="test_cse_id",
                num=10,  # Should be capped at 10
                safe="off",
            )
