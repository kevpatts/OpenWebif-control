"""Pytest fixtures for the local HA integration test."""
import pytest


@pytest.fixture(autouse=True)
def _enable_custom(enable_custom_integrations):
    """Allow HA to load our custom integration."""
    yield
