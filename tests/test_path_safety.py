"""Unit tests for the security boundary: path allowlisting.

These don't need a running LocalStack — they exercise the pure path-resolution
and auth helpers directly.
"""
import os

import pytest

from localstack_file_api.api import _authorized, _resolve_within_allowlist


@pytest.fixture
def allowlist(tmp_path, monkeypatch):
    root = tmp_path / "workspace"
    root.mkdir()
    monkeypatch.setenv("FILE_API_ALLOWED_ROOTS", str(root))
    return root


def test_allows_path_inside_root(allowlist):
    target = str(allowlist / "main.tf")
    assert _resolve_within_allowlist(target) == os.path.realpath(target)


def test_allows_nested_path(allowlist):
    target = str(allowlist / "module" / "vpc.tf")
    assert _resolve_within_allowlist(target) == os.path.realpath(target)


def test_rejects_path_outside_root(allowlist):
    assert _resolve_within_allowlist("/etc/passwd") is None


def test_rejects_traversal_escape(allowlist):
    # ../../etc/passwd style escape must be caught after realpath resolution
    escape = str(allowlist / ".." / ".." / "etc" / "passwd")
    assert _resolve_within_allowlist(escape) is None


def test_rejects_empty_path(allowlist):
    assert _resolve_within_allowlist("") is None
    assert _resolve_within_allowlist(None) is None


def test_sibling_prefix_not_confused(tmp_path, monkeypatch):
    # /a/workspace must NOT permit /a/workspace-evil (prefix-string bug guard)
    root = tmp_path / "workspace"
    root.mkdir()
    evil = tmp_path / "workspace-evil"
    evil.mkdir()
    monkeypatch.setenv("FILE_API_ALLOWED_ROOTS", str(root))
    assert _resolve_within_allowlist(str(evil / "x")) is None


class _FakeRequest:
    def __init__(self, headers):
        self.headers = headers


def test_auth_open_when_no_token(monkeypatch):
    monkeypatch.delenv("FILE_API_TOKEN", raising=False)
    assert _authorized(_FakeRequest({})) is True


def test_auth_requires_token_when_set(monkeypatch):
    monkeypatch.setenv("FILE_API_TOKEN", "secret")
    assert _authorized(_FakeRequest({})) is False
    assert _authorized(_FakeRequest({"authorization": "Bearer secret"})) is True
    assert _authorized(_FakeRequest({"ls-api-key": "secret"})) is True
    assert _authorized(_FakeRequest({"authorization": "Bearer wrong"})) is False
