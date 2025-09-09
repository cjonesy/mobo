"""
Unit tests for rate limiting functionality.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock

from mobo.tools.rate_limiting import (
    rate_limited,
    check_and_increment_rate_limit,
    get_rate_limit_status,
    RateLimitExceeded,
    cleanup_expired_rate_limits,
)
from mobo.memory.models import RateLimit


class MockAsyncSession:
    """Mock async database session."""

    def __init__(self):
        self.rate_limits = {}
        self.committed = False
        self.rolled_back = False
        self.last_added = None

    async def execute(self, stmt):
        """Mock execute method."""
        # Simple mock that returns rate limit if it exists
        result = Mock()

        # For select statements
        if hasattr(stmt, "compile"):
            # If we just added a rate limit, return None to simulate it not being found
            # This allows the code to create a new rate limit for each user
            if self.last_added is not None:
                rate_limit = None
                self.last_added = None  # Reset for next query
            else:
                # Return the first rate limit we have stored
                rate_limit = None
                if self.rate_limits:
                    rate_limit = list(self.rate_limits.values())[0]

            result.scalar_one_or_none = Mock(return_value=rate_limit)
            result.scalars = Mock(
                return_value=Mock(
                    all=Mock(return_value=[rate_limit] if rate_limit else [])
                )
            )
        else:
            result.scalar_one_or_none = Mock(return_value=None)
            result.scalars = Mock(return_value=Mock(all=Mock(return_value=[])))

        return result

    def add(self, obj):
        """Mock add method."""
        if isinstance(obj, RateLimit):
            key = (obj.resource_name, obj.period_start, obj.user_id)
            self.rate_limits[key] = obj
            self.last_added = obj

    async def flush(self):
        """Mock flush method."""
        pass

    async def commit(self):
        """Mock commit method."""
        self.committed = True

    async def rollback(self):
        """Mock rollback method."""
        self.rolled_back = True

    async def delete(self, obj):
        """Mock delete method."""
        if isinstance(obj, RateLimit):
            key = (obj.resource_name, obj.period_start, obj.user_id)
            if key in self.rate_limits:
                del self.rate_limits[key]


@pytest.fixture
def mock_session():
    """Fixture providing a mock async session."""
    return MockAsyncSession()


@pytest.fixture
def mock_rate_limit_session(mock_session):
    """Mock the get_rate_limit_session context manager."""

    class AsyncContextManager:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return None

    return AsyncContextManager()


class TestRateLimiting:
    """Test suite for rate limiting functionality."""

    @patch("mobo.tools.rate_limiting.get_rate_limit_session")
    @pytest.mark.asyncio
    async def test_first_request_creates_rate_limit(
        self, mock_get_session, mock_rate_limit_session
    ):
        """Test that first request creates a new rate limit record."""
        mock_get_session.return_value = mock_rate_limit_session

        result = await check_and_increment_rate_limit(
            resource="test-api", max_requests=10, period_type="hour", increment=1
        )

        assert result["resource"] == "test-api"
        assert result["current_usage"] == 1
        assert result["max_usage"] == 10
        assert result["remaining"] == 9
        assert result["period_type"] == "hour"
        assert result["user_id"] is None

    @patch("mobo.tools.rate_limiting.get_rate_limit_session")
    @pytest.mark.asyncio
    async def test_subsequent_requests_increment_usage(
        self, mock_get_session, mock_session
    ):
        """Test that subsequent requests increment usage correctly."""
        # Setup existing rate limit
        period_start, period_end = RateLimit.get_period_bounds("hour")
        existing_limit = RateLimit(
            resource_name="test-api",
            period_start=period_start,
            period_end=period_end,
            current_usage=3,
            max_usage=10,
            period_type="hour",
        )

        mock_session.rate_limits[("test-api", period_start, None)] = existing_limit

        class AsyncContextManager:
            async def __aenter__(self):
                return mock_session

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None

        mock_get_session.return_value = AsyncContextManager()

        result = await check_and_increment_rate_limit(
            resource="test-api", max_requests=10, period_type="hour", increment=2
        )

        assert result["current_usage"] == 5  # 3 + 2
        assert result["remaining"] == 5  # 10 - 5

    @patch("mobo.tools.rate_limiting.get_rate_limit_session")
    @pytest.mark.asyncio
    async def test_rate_limit_exceeded_raises_exception(
        self, mock_get_session, mock_session
    ):
        """Test that exceeding rate limit raises RateLimitExceeded."""
        # Setup rate limit near maximum
        period_start, period_end = RateLimit.get_period_bounds("day")
        existing_limit = RateLimit(
            resource_name="test-api",
            period_start=period_start,
            period_end=period_end,
            current_usage=10,  # Already at max
            max_usage=10,
            period_type="day",
        )

        mock_session.rate_limits[("test-api", period_start, None)] = existing_limit

        class AsyncContextManager:
            async def __aenter__(self):
                return mock_session

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None

        mock_get_session.return_value = AsyncContextManager()

        # This should fail (10 + 1 = 11, which exceeds max)
        with pytest.raises(RateLimitExceeded) as exc_info:
            await check_and_increment_rate_limit(
                resource="test-api", max_requests=10, period_type="day", increment=1
            )

        assert exc_info.value.resource == "test-api"
        assert exc_info.value.limit == 10

    @patch("mobo.tools.rate_limiting.get_rate_limit_session")
    @pytest.mark.asyncio
    async def test_user_specific_rate_limiting(self, mock_get_session, mock_session):
        """Test user-specific rate limiting."""

        class AsyncContextManager:
            async def __aenter__(self):
                return mock_session

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None

        mock_get_session.return_value = AsyncContextManager()

        # User 1 makes a request
        result1 = await check_and_increment_rate_limit(
            resource="user-api",
            max_requests=5,
            period_type="hour",
            user_id="user123",
            increment=1,
        )

        # User 2 makes a request
        result2 = await check_and_increment_rate_limit(
            resource="user-api",
            max_requests=5,
            period_type="hour",
            user_id="user456",
            increment=1,
        )

        # Both should have usage of 1 (separate limits)
        assert result1["current_usage"] == 1
        assert result1["user_id"] == "user123"
        assert result2["current_usage"] == 1
        assert result2["user_id"] == "user456"

    @patch("mobo.tools.rate_limiting.get_rate_limit_session")
    @pytest.mark.asyncio
    async def test_get_rate_limit_status(self, mock_get_session, mock_session):
        """Test getting rate limit status."""
        # Setup existing rate limit
        period_start, period_end = RateLimit.get_period_bounds("day")
        existing_limit = RateLimit(
            resource_name="status-test",
            period_start=period_start,
            period_end=period_end,
            current_usage=7,
            max_usage=20,
            period_type="day",
        )

        mock_session.rate_limits[("status-test", period_start, None)] = existing_limit

        class AsyncContextManager:
            async def __aenter__(self):
                return mock_session

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None

        mock_get_session.return_value = AsyncContextManager()

        status = await get_rate_limit_status("status-test", "day")

        assert status is not None
        assert status["resource"] == "status-test"
        assert status["current_usage"] == 7
        assert status["max_usage"] == 20
        assert status["remaining"] == 13
        assert status["is_exceeded"] is False

    @patch("mobo.tools.rate_limiting.get_rate_limit_session")
    @pytest.mark.asyncio
    async def test_get_rate_limit_status_not_found(
        self, mock_get_session, mock_session
    ):
        """Test getting status for non-existent rate limit."""

        class AsyncContextManager:
            async def __aenter__(self):
                return mock_session

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None

        mock_get_session.return_value = AsyncContextManager()

        status = await get_rate_limit_status("nonexistent", "day")
        assert status is None

    @patch("mobo.tools.rate_limiting.get_rate_limit_session")
    @pytest.mark.asyncio
    async def test_rate_limited_decorator_success(self, mock_get_session, mock_session):
        """Test rate limited decorator with successful request."""

        class AsyncContextManager:
            async def __aenter__(self):
                return mock_session

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None

        mock_get_session.return_value = AsyncContextManager()

        @rate_limited(resource="decorator-test", max_requests=5, period="hour")
        async def test_function(message: str) -> str:
            return f"Success: {message}"

        result = await test_function("hello")
        assert result == "Success: hello"

    @patch("mobo.tools.rate_limiting.get_rate_limit_session")
    @pytest.mark.asyncio
    async def test_rate_limited_decorator_exceeded(
        self, mock_get_session, mock_session
    ):
        """Test rate limited decorator when limit is exceeded."""
        # Setup rate limit at maximum
        period_start, period_end = RateLimit.get_period_bounds("minute")
        existing_limit = RateLimit(
            resource_name="decorator-exceeded",
            period_start=period_start,
            period_end=period_end,
            current_usage=3,
            max_usage=3,
            period_type="minute",
        )

        mock_session.rate_limits[("decorator-exceeded", period_start, None)] = (
            existing_limit
        )

        class AsyncContextManager:
            async def __aenter__(self):
                return mock_session

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None

        mock_get_session.return_value = AsyncContextManager()

        @rate_limited(resource="decorator-exceeded", max_requests=3, period="minute")
        async def test_function(message: str) -> str:
            return f"Should not reach this: {message}"

        result = await test_function("test")

        # Should return rate limit error message instead of calling function
        assert "Rate limit reached" in result
        assert "decorator-exceeded" in result

    @patch("mobo.tools.rate_limiting.get_rate_limit_session")
    @pytest.mark.asyncio
    async def test_rate_limited_decorator_with_cost(
        self, mock_get_session, mock_session
    ):
        """Test rate limited decorator with custom cost."""

        class AsyncContextManager:
            async def __aenter__(self):
                return mock_session

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None

        mock_get_session.return_value = AsyncContextManager()

        @rate_limited(resource="cost-test", max_requests=10, period="hour", cost=3)
        async def expensive_function() -> str:
            return "Expensive operation"

        result = await expensive_function()
        assert result == "Expensive operation"

        # Check that usage increased by 3
        period_start, period_end = RateLimit.get_period_bounds("hour")
        key = ("cost-test", period_start, None)
        rate_limit = mock_session.rate_limits.get(key)
        assert rate_limit is not None
        assert rate_limit.current_usage == 3

    def test_rate_limit_period_bounds(self):
        """Test period bound calculations."""
        base_time = datetime(2024, 3, 15, 14, 30, 45)

        # Test minute bounds
        start, end = RateLimit.get_period_bounds("minute", base_time)
        assert start == datetime(2024, 3, 15, 14, 30, 0)
        assert end == datetime(2024, 3, 15, 14, 31, 0)

        # Test hour bounds
        start, end = RateLimit.get_period_bounds("hour", base_time)
        assert start == datetime(2024, 3, 15, 14, 0, 0)
        assert end == datetime(2024, 3, 15, 15, 0, 0)

        # Test day bounds
        start, end = RateLimit.get_period_bounds("day", base_time)
        assert start == datetime(2024, 3, 15, 0, 0, 0)
        assert end == datetime(2024, 3, 16, 0, 0, 0)

        # Test month bounds
        start, end = RateLimit.get_period_bounds("month", base_time)
        assert start == datetime(2024, 3, 1, 0, 0, 0)
        assert end == datetime(2024, 4, 1, 0, 0, 0)

        # Test December month bounds (year rollover)
        dec_time = datetime(2024, 12, 15, 10, 0, 0)
        start, end = RateLimit.get_period_bounds("month", dec_time)
        assert start == datetime(2024, 12, 1, 0, 0, 0)
        assert end == datetime(2025, 1, 1, 0, 0, 0)

    def test_rate_limit_model_methods(self):
        """Test RateLimit model utility methods."""
        period_start = datetime(2024, 3, 15, 0, 0, 0)
        period_end = datetime(2024, 3, 16, 0, 0, 0)

        rate_limit = RateLimit(
            resource_name="test",
            period_start=period_start,
            period_end=period_end,
            current_usage=7,
            max_usage=10,
            period_type="day",
        )

        # Test is_exceeded
        assert rate_limit.is_exceeded() is False
        rate_limit.current_usage = 10
        assert rate_limit.is_exceeded() is True

        # Test can_make_requests
        rate_limit.current_usage = 7
        assert rate_limit.can_make_requests(1) is True
        assert rate_limit.can_make_requests(3) is True
        assert rate_limit.can_make_requests(4) is False

        # Test remaining_requests
        assert rate_limit.remaining_requests() == 3
        rate_limit.current_usage = 10
        assert rate_limit.remaining_requests() == 0
