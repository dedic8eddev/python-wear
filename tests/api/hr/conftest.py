"""Pytest fixtures to be used by all tests."""
import dns.resolver
import pytest


@pytest.fixture
def patch_dns_resolver(monkeypatch):
    """Monkeypatch dns.resolver.query so internet access is not needed."""
    monkeypatch.setattr(dns.resolver, 'query', lambda *args: None)
