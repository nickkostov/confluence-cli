import pytest

from src.confluence.client import ConfluenceClient


class DummyResp:
    def __init__(self, status, json_data=None, headers=None, text=""):
        self.status_code = status
        self._json = json_data
        self.headers = headers or {}
        self.text = text

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json


class DummySession:
    def __init__(self, responses):
        self.headers = {}
        self._responses = responses
        self._i = 0

    def request(self, *a, **kw):
        resp = self._responses[self._i]
        self._i = min(self._i + 1, len(self._responses) - 1)
        return resp


def test_retry_and_success(monkeypatch):
    c = ConfluenceClient(base_url='https://x', pat='t', retries=2, backoff=0.0)
    responses = [DummyResp(500), DummyResp(200, {"ok": True})]
    c.session = DummySession(responses)  # inject
    out = c._request('GET', '/rest/api/content')
    assert out == {"ok": True}


def test_raise_for_status(monkeypatch):
    c = ConfluenceClient(base_url='https://x', pat='t', retries=0)
    c.session = DummySession([DummyResp(404)])
    with pytest.raises(Exception):
        c._request('GET', '/nope')
