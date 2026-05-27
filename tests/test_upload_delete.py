"""Unit tests for the upload (POST) and delete (DELETE) endpoints.

These don't need a running LocalStack — they call FileApiResource methods
directly using a lightweight fake Request.
"""
from __future__ import annotations

import hashlib
import io
import json
import os

import pytest

from localstack_file_api.api import FileApiResource


# ---------------------------------------------------------------------------
# Helpers / fake request
# ---------------------------------------------------------------------------


class _FakeStorage:
    """Minimal stand-in for werkzeug FileStorage."""

    def __init__(self, data: bytes):
        self._data = data

    def read(self) -> bytes:
        return self._data


class _FakeRequest:
    """Minimal stand-in for localstack.http.Request."""

    def __init__(
        self,
        *,
        headers: dict | None = None,
        args: dict | None = None,
        form: dict | None = None,
        files: dict | None = None,
        body: bytes = b"",
    ):
        self.headers = headers or {}
        self.args = args or {}
        self.form = form or {}
        self.files = files or {}
        self._body = body

    def get_data(self) -> bytes:
        return self._body


def _raw_upload(path: str, body: bytes, *, headers: dict | None = None) -> _FakeRequest:
    """Raw-body upload: path in query param, content in body."""
    return _FakeRequest(headers=headers or {}, args={"path": path}, body=body)


def _multipart_upload(
    path: str, body: bytes, *, headers: dict | None = None
) -> _FakeRequest:
    """Multipart upload: path in form field, file bytes in files['file']."""
    return _FakeRequest(
        headers=headers or {},
        form={"path": path},
        files={"file": _FakeStorage(body)},
    )


def _delete_request(path: str, *, headers: dict | None = None) -> _FakeRequest:
    return _FakeRequest(headers=headers or {}, args={"path": path})


@pytest.fixture
def resource():
    return FileApiResource()


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """A temporary allowed root dir."""
    root = tmp_path / "workspace"
    root.mkdir()
    monkeypatch.setenv("FILE_API_ALLOWED_ROOTS", str(root))
    return root


# ---------------------------------------------------------------------------
# Upload — raw body
# ---------------------------------------------------------------------------


class TestUploadRawBody:
    def test_creates_file(self, resource, workspace):
        content = b"resource 'aws_s3_bucket' 'my_bucket' {}"
        req = _raw_upload(str(workspace / "main.tf"), content)
        resp = resource.on_post(req)
        body = json.loads(resp.data)

        assert resp.status_code == 201
        assert body["size"] == len(content)
        assert body["sha256"] == hashlib.sha256(content).hexdigest()
        assert (workspace / "main.tf").read_bytes() == content

    def test_creates_intermediate_directories(self, resource, workspace):
        content = b"variable 'region' {}"
        target = workspace / "modules" / "vpc" / "variables.tf"
        req = _raw_upload(str(target), content)
        resp = resource.on_post(req)

        assert resp.status_code == 201
        assert target.read_bytes() == content

    def test_overwrites_existing_file(self, resource, workspace):
        target = workspace / "overwrite.txt"
        target.write_bytes(b"old content")
        new_content = b"new content"
        req = _raw_upload(str(target), new_content)
        resp = resource.on_post(req)

        assert resp.status_code == 201
        assert target.read_bytes() == new_content

    def test_rejects_path_outside_allowlist(self, resource, workspace):
        req = _raw_upload("/etc/passwd", b"pwned")
        resp = resource.on_post(req)
        body = json.loads(resp.data)

        assert resp.status_code == 403
        assert "not allowed" in body["error"]

    def test_rejects_traversal_escape(self, resource, workspace):
        escape = str(workspace / ".." / ".." / "etc" / "shadow")
        req = _raw_upload(escape, b"pwned")
        resp = resource.on_post(req)

        assert resp.status_code == 403

    def test_rejects_missing_path(self, resource, workspace):
        req = _FakeRequest(body=b"some content")  # no 'path' anywhere
        resp = resource.on_post(req)
        body = json.loads(resp.data)

        assert resp.status_code == 400
        assert "target path" in body["error"]

    def test_rejects_empty_body(self, resource, workspace):
        req = _raw_upload(str(workspace / "empty.txt"), b"")
        resp = resource.on_post(req)
        body = json.loads(resp.data)

        assert resp.status_code == 400
        assert "no file content" in body["error"]

    def test_rejects_oversized_file(self, resource, workspace, monkeypatch):
        monkeypatch.setenv("FILE_API_MAX_BYTES", "10")
        req = _raw_upload(str(workspace / "big.bin"), b"x" * 11)
        resp = resource.on_post(req)
        body = json.loads(resp.data)

        assert resp.status_code == 413
        assert "exceeds limit" in body["error"]

    def test_rejects_unauthorized(self, resource, workspace, monkeypatch):
        monkeypatch.setenv("FILE_API_TOKEN", "secret")
        req = _raw_upload(str(workspace / "file.txt"), b"data")
        resp = resource.on_post(req)

        assert resp.status_code == 401

    def test_accepts_bearer_token(self, resource, workspace, monkeypatch):
        monkeypatch.setenv("FILE_API_TOKEN", "secret")
        req = _raw_upload(
            str(workspace / "file.txt"),
            b"data",
            headers={"authorization": "Bearer secret"},
        )
        resp = resource.on_post(req)

        assert resp.status_code == 201

    def test_accepts_ls_api_key_header(self, resource, workspace, monkeypatch):
        monkeypatch.setenv("FILE_API_TOKEN", "secret")
        req = _raw_upload(
            str(workspace / "file.txt"),
            b"data",
            headers={"ls-api-key": "secret"},
        )
        resp = resource.on_post(req)

        assert resp.status_code == 201

    def test_path_from_query_when_no_form(self, resource, workspace):
        """Raw upload: path must be resolved from args, not form."""
        content = b"hello"
        req = _FakeRequest(args={"path": str(workspace / "q.txt")}, body=content)
        resp = resource.on_post(req)

        assert resp.status_code == 201


# ---------------------------------------------------------------------------
# Upload — multipart
# ---------------------------------------------------------------------------


class TestUploadMultipart:
    def test_creates_file_from_form_fields(self, resource, workspace):
        content = b"multipart content"
        req = _multipart_upload(str(workspace / "upload.bin"), content)
        resp = resource.on_post(req)
        body = json.loads(resp.data)

        assert resp.status_code == 201
        assert body["sha256"] == hashlib.sha256(content).hexdigest()
        assert (workspace / "upload.bin").read_bytes() == content

    def test_path_from_query_param_when_form_has_none(self, resource, workspace):
        """Multipart: path can also live in query args."""
        content = b"via query"
        req = _FakeRequest(
            args={"path": str(workspace / "q.bin")},
            files={"file": _FakeStorage(content)},
        )
        resp = resource.on_post(req)

        assert resp.status_code == 201

    def test_rejects_when_file_field_missing(self, resource, workspace):
        """files dict present but no 'file' key → falls through to raw body check."""
        req = _FakeRequest(
            form={"path": str(workspace / "x.txt")},
            files={"other": _FakeStorage(b"data")},  # wrong key
            body=b"",
        )
        resp = resource.on_post(req)
        body = json.loads(resp.data)

        # falls back to raw body check; body is empty → 400
        assert resp.status_code == 400
        assert "no file content" in body["error"]

    def test_rejects_path_outside_allowlist(self, resource, workspace):
        req = _multipart_upload("/etc/hosts", b"data")
        resp = resource.on_post(req)

        assert resp.status_code == 403

    def test_rejects_unauthorized(self, resource, workspace, monkeypatch):
        monkeypatch.setenv("FILE_API_TOKEN", "token123")
        req = _multipart_upload(str(workspace / "file.bin"), b"data")
        resp = resource.on_post(req)

        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


class TestDelete:
    def test_deletes_existing_file(self, resource, workspace):
        target = workspace / "to_delete.txt"
        target.write_bytes(b"bye")
        req = _delete_request(str(target))
        resp = resource.on_delete(req)
        body = json.loads(resp.data)

        assert resp.status_code == 200
        assert body["deleted"] is True
        assert body["path"] == str(target.resolve())
        assert not target.exists()

    def test_returns_404_for_missing_file(self, resource, workspace):
        req = _delete_request(str(workspace / "ghost.txt"))
        resp = resource.on_delete(req)
        body = json.loads(resp.data)

        assert resp.status_code == 404
        assert "not found" in body["error"]

    def test_returns_404_for_directory(self, resource, workspace):
        subdir = workspace / "mydir"
        subdir.mkdir()
        req = _delete_request(str(subdir))
        resp = resource.on_delete(req)
        body = json.loads(resp.data)

        assert resp.status_code == 404
        assert "not a file" in body["error"]

    def test_rejects_path_outside_allowlist(self, resource, workspace):
        req = _delete_request("/etc/passwd")
        resp = resource.on_delete(req)
        body = json.loads(resp.data)

        assert resp.status_code == 403
        assert "not allowed" in body["error"]

    def test_rejects_traversal_escape(self, resource, workspace):
        escape = str(workspace / ".." / ".." / "etc" / "shadow")
        req = _delete_request(escape)
        resp = resource.on_delete(req)

        assert resp.status_code == 403

    def test_rejects_missing_path(self, resource, workspace):
        req = _FakeRequest()  # no 'path'
        resp = resource.on_delete(req)
        body = json.loads(resp.data)

        assert resp.status_code == 403  # _resolve_within_allowlist(None) → None

    def test_rejects_unauthorized(self, resource, workspace, monkeypatch):
        monkeypatch.setenv("FILE_API_TOKEN", "s3cr3t")
        target = workspace / "file.txt"
        target.write_bytes(b"data")
        req = _delete_request(str(target))
        resp = resource.on_delete(req)

        assert resp.status_code == 401
        assert target.exists()  # file must NOT have been deleted

    def test_accepts_bearer_token(self, resource, workspace, monkeypatch):
        monkeypatch.setenv("FILE_API_TOKEN", "s3cr3t")
        target = workspace / "file.txt"
        target.write_bytes(b"data")
        req = _delete_request(str(target), headers={"authorization": "Bearer s3cr3t"})
        resp = resource.on_delete(req)

        assert resp.status_code == 200
        assert not target.exists()

    def test_accepts_ls_api_key_header(self, resource, workspace, monkeypatch):
        monkeypatch.setenv("FILE_API_TOKEN", "s3cr3t")
        target = workspace / "file.txt"
        target.write_bytes(b"data")
        req = _delete_request(str(target), headers={"ls-api-key": "s3cr3t"})
        resp = resource.on_delete(req)

        assert resp.status_code == 200
        assert not target.exists()

    def test_file_untouched_on_403(self, resource, workspace):
        """A forbidden delete must not remove the target even if it exists."""
        # create a file at a path the API cannot see (outside allowlist)
        # We can only verify the response — the file lives outside tmp workspace
        req = _delete_request("/etc/passwd")
        resp = resource.on_delete(req)

        assert resp.status_code == 403
