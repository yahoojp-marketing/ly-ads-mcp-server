from __future__ import annotations

from contextlib import contextmanager

from ly_ads_mcp.servers.common.pagination import InMemoryCursorStore


class FakeAccount:
    def __init__(self, data: dict):
        self._data = data

    def to_dict(self):
        return dict(self._data)


class FakeValue:
    def __init__(self, account=None):
        self.account = account


class FakeRval:
    def __init__(self, values=None, total=0):
        self.values = values or []
        self.total_num_entries = total


class FakeApiResponse:
    def __init__(self, rval=None, errors=None):
        self.rval = rval
        self.errors = errors


class FakeHandlers:
    def __init__(self, *, auth_fingerprint="test-auth", cursor_store=None):
        self._auth_fingerprint = auth_fingerprint
        self.cursor_store = cursor_store or InMemoryCursorStore()

    def access_token_fingerprint(self):
        return self._auth_fingerprint

    @contextmanager
    def api_client(self):
        yield object()
