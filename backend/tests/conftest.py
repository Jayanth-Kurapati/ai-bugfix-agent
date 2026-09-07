"""Test configuration and fixtures."""

import pytest
from backend.api import routes


@pytest.fixture(autouse=True)
def reset_limits_per_test():
    """Ensure rate limits and concurrency cap are clean for every test."""
    routes._reset_limits()
    yield
    routes._reset_limits()
