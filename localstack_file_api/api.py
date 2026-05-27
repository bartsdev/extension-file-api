"""Generic file-upload REST API exposed under /_localstack/files.

Endpoints (also documented in openapi.yaml so they appear in /_localstack/swagger):

    POST   /_localstack/files   upload a file (multipart or raw body)
    GET    /_localstack/files   list a directory or stat a file
    DELETE /_localstack/files   delete a file

Security:
  - Writes/reads/deletes are confined to an allowlist of root directories
    (FILE_API_ALLOWED_ROOTS, comma-separated; default below). Any target that
    resolves outside the allowlist is rejected with 403.
  - If FILE_API_TOKEN is set, every request must carry it as
    `authorization: Bearer <token>` or the `ls-api-key` header.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os

from localstack.http import Request, Response

# Use the localstack.* namespace so logs flow through LocalStack's
# configured handlers, formatters, and LS_LOG level overrides.
LOG = logging.getLogger("localstack.extensions.file_api.api")

DEFAULT_ALLOWED_ROOTS = ["/tmp", "/workspace", "/etc/localstack/init"]


def _allowed_roots() -> list[str]:
    raw = os.environ.get("FILE_API_ALLOWED_ROOTS")
    roots = raw.split(",") if raw else DEFAULT_ALLOWED_ROOTS
    return [os.path.realpath(r.strip()) for r in roots if r.strip()]


def _max_bytes() -> int:
    return int(os.environ.get("FILE_API_MAX_BYTES", str(25 * 1024 * 1024)))


def _json(data: dict, status: int = 200) -> Response:
    return Response(json.dumps(data), status=status, mimetype="application/json")


def _authorized(request: Request) -> bool:
    token = os.environ.get("FILE_API_TOKEN")
    if not token:
        return True
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer ") and auth[len("Bearer ") :].strip() == token:
        return True
    if request.headers.get("ls-api-key") == token:
        return True
    return False


def _resolve_within_allowlist(path: str) -> str | None:
    """Return the realpath if it sits inside an allowlisted root, else None."""
    if not path:
        return None
    target = os.path.realpath(path)
    for root in _allowed_roots():
        if target == root or target.startswith(root + os.sep):
            return target
    return None


class FileApiResource:
    def on_post(self, request: Request) -> Response:
        if not _authorized(request):
            return _json({"error": "unauthorized"}, 401)

        target_arg, data = self._extract_upload(request)
        if target_arg is None:
            return _json({"error": "missing target path (form field 'path' or '?path=')"}, 400)
        if data is None:
            return _json({"error": "no file content (form field 'file' or raw body)"}, 400)

        if len(data) > _max_bytes():
            return _json({"error": f"file exceeds limit of {_max_bytes()} bytes"}, 413)

        target = _resolve_within_allowlist(target_arg)
        if target is None:
            return _json(
                {"error": "path not allowed", "allowed_roots": _allowed_roots()}, 403
            )

        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "wb") as f:
            f.write(data)

        digest = hashlib.sha256(data).hexdigest()
        LOG.info(
            "file-api upload: name=%s path=%s size=%d bytes",
            os.path.basename(target),
            target,
            len(data),
        )
        return _json({"path": target, "size": len(data), "sha256": digest}, 201)

    def on_get(self, request: Request) -> Response:
        if not _authorized(request):
            return _json({"error": "unauthorized"}, 401)

        path_arg = request.args.get("path")
        target = _resolve_within_allowlist(path_arg)
        if target is None:
            return _json({"error": "path not allowed or missing"}, 403)
        if not os.path.exists(target):
            return _json({"error": "not found", "path": target}, 404)

        if os.path.isdir(target):
            entries = sorted(os.listdir(target))
            return _json({"path": target, "type": "directory", "entries": entries})

        stat = os.stat(target)
        return _json(
            {"path": target, "type": "file", "size": stat.st_size, "modified": int(stat.st_mtime)}
        )

    def on_delete(self, request: Request) -> Response:
        if not _authorized(request):
            return _json({"error": "unauthorized"}, 401)

        path_arg = request.args.get("path")
        target = _resolve_within_allowlist(path_arg)
        if target is None:
            return _json({"error": "path not allowed or missing"}, 403)
        if not os.path.isfile(target):
            return _json({"error": "not a file or not found", "path": target}, 404)

        os.remove(target)
        LOG.info(
            "file-api delete: name=%s path=%s",
            os.path.basename(target),
            target,
        )
        return _json({"path": target, "deleted": True})

    @staticmethod
    def _extract_upload(request: Request) -> tuple[str | None, bytes | None]:
        # multipart/form-data: file in `file`, target in `path`
        if request.files:
            storage = request.files.get("file")
            target = request.form.get("path") or request.args.get("path")
            if storage is not None:
                return target, storage.read()
        # raw body: target from query param
        target = request.args.get("path") or request.form.get("path")
        body = request.get_data()
        return target, (body if body else None)
