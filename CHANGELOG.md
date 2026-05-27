# Changelog

All notable changes to this project are documented here.
Versioning follows [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

### Added
- `tests/test_upload_delete.py` — 27 unit tests covering POST and DELETE endpoints
  (raw body, multipart, auth, path safety, size limit, error cases)

---

## [0.1.0] — 2025-05-27

### Added
- `FileApiResource` — POST / GET / DELETE handlers under `/_localstack/files`
- Path allowlist enforcement via `FILE_API_ALLOWED_ROOTS` (default `/tmp,/workspace,/etc/localstack/init`)
- Optional bearer-token / `ls-api-key` auth via `FILE_API_TOKEN`
- Configurable upload size cap via `FILE_API_MAX_BYTES` (default 25 MiB)
- OpenAPI spec plugin — endpoints appear in LocalStack's Swagger UI automatically
- `tests/test_path_safety.py` — unit tests for path resolution and auth helpers
- `Makefile`, `.gitignore`, `CHANGELOG.md`
