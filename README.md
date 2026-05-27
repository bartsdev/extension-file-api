# LocalStack File API Extension

> Push files into a running LocalStack instance over HTTP — no volume mounts required.

Adds three REST endpoints under `/_localstack/files` to a LocalStack instance and
registers them automatically in the Swagger UI at `/_localstack/swagger`.

---

## Why this exists

Ephemeral (cloud-hosted) LocalStack instances can't have host files volume-mounted
or init-hook scripts pre-placed. This extension works around that by providing a
small, authenticated REST API you can `curl` to write Terraform configs, init
scripts, or any other file the instance needs — before or after startup.

---

## Endpoints

All endpoints live at `/_localstack/files`.

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/_localstack/files` | Upload a file (multipart or raw body) |
| `GET` | `/_localstack/files?path=…` | Stat a file or list a directory |
| `DELETE` | `/_localstack/files?path=…` | Delete a file |

Full OpenAPI spec shipped with the package — see `/_localstack/swagger` inside your instance.

### POST — upload a file

**Multipart** (file in `file` field, destination in `path` field):

```sh
curl -X POST "$LS_URL/_localstack/files" \
  -F "path=/etc/localstack/init/ready.d/setup.sh" \
  -F "file=@./setup.sh"
```

**Raw body** (destination in `?path=` query param):

```sh
curl -X POST "$LS_URL/_localstack/files?path=/workspace/main.tf" \
  --data-binary @./main.tf
```

Response `201`:

```json
{
  "path":   "/workspace/main.tf",
  "size":   1234,
  "sha256": "e3b0c44298fc1c149afb…"
}
```

### GET — stat or list

```sh
# stat a file
curl "$LS_URL/_localstack/files?path=/workspace/main.tf"
# {"path":"/workspace/main.tf","type":"file","size":1234,"modified":1716800000}

# list a directory
curl "$LS_URL/_localstack/files?path=/workspace"
# {"path":"/workspace","type":"directory","entries":["main.tf","variables.tf"]}
```

### DELETE — remove a file

```sh
curl -X DELETE "$LS_URL/_localstack/files?path=/workspace/main.tf"
# {"path":"/workspace/main.tf","deleted":true}
```

---

## Security

| Concern | Mechanism |
|---------|-----------|
| **Path containment** | Every target is resolved with `os.path.realpath` and checked against `FILE_API_ALLOWED_ROOTS`. Symlink traversal and `../..` escapes are caught. Returns `403`. |
| **Auth** | Set `FILE_API_TOKEN` to require `Authorization: Bearer <token>` **or** `ls-api-key: <token>` on every request. Unset = open (fine for local dev). |
| **Size cap** | Uploads larger than `FILE_API_MAX_BYTES` are rejected with `413`. |

---

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FILE_API_ALLOWED_ROOTS` | `/tmp,/workspace,/etc/localstack/init` | Comma-separated list of paths inside which the API may read/write/delete. |
| `FILE_API_TOKEN` | _(unset = open)_ | Shared secret. Set to enforce bearer-token / `ls-api-key` auth on every request. |
| `FILE_API_MAX_BYTES` | `26214400` (25 MiB) | Maximum upload size in bytes. |

---

## Installation

### Local development (developer mode)

```sh
git clone https://github.com/localstack/localstack-file-api
cd localstack-file-api

# 1. Create .venv, install the extension + dev deps, generate plux entrypoints
make install

# 2. Register the local checkout with the LocalStack CLI
localstack extensions dev enable .

# 3. Start LocalStack with dev mode on — your extension is loaded automatically
EXTENSION_DEV_MODE=1 localstack start
```

> **What `make install` does** — creates `.venv`, installs `.[dev]` in editable mode,
> then runs `python -m plux entrypoints` to regenerate the entry-point cache that
> LocalStack reads at startup. Re-run it whenever you add a new plugin.

### Install from this GitHub repository

```sh
localstack extensions install \
  "git+https://github.com/localstack/localstack-file-api/#egg=localstack-file-api"
```

### Auto-install on an ephemeral instance

```sh
EXTENSION_AUTO_INSTALL=localstack-file-api localstack start
```

### Install from PyPI (once published)

```sh
localstack extensions install localstack-file-api
```

### Docker Compose example

```yaml
services:
  localstack:
    image: localstack/localstack-pro:latest
    environment:
      EXTENSION_AUTO_INSTALL: "localstack-file-api"
      FILE_API_TOKEN: "${FILE_API_TOKEN}"
      FILE_API_ALLOWED_ROOTS: "/tmp,/workspace,/etc/localstack/init"
    ports:
      - "4566:4566"
    volumes:
      - "./workspace:/workspace"
```

---

## Development

### Common tasks

```sh
make install       # create .venv, install deps, generate plux entrypoints
make test          # run the full test suite
make test-cov      # tests + HTML coverage report (htmlcov/)
make lint          # ruff checks
make format        # black + isort
make check         # format-check + lint + test  (CI gate)
make build         # build sdist + wheel
make clean         # remove build/test artefacts
```

### Running tests directly

```sh
pytest tests/ -v
pytest tests/test_upload_delete.py -v   # upload + delete only
pytest tests/test_path_safety.py   -v   # path allowlist + auth only
```

---

## Project layout

```
localstack_file_api/
├── api.py          # FileApiResource — POST / GET / DELETE handlers + security helpers
├── extension.py    # LocalStack Extension — registers routes on the gateway
├── plugins.py      # OAS plugin — merges openapi.yaml into /_localstack/swagger
└── openapi.yaml    # OpenAPI 3.0 spec for the three endpoints

tests/
├── test_path_safety.py    # unit tests: path allowlist + auth helpers
└── test_upload_delete.py  # unit tests: upload and delete endpoints
```

---

## How it plugs into LocalStack

1. **Entry points** in `setup.cfg` register two plux plugins:
   - `localstack.extensions → FileApiExtension` — calls `update_gateway_routes` to mount the three HTTP handlers.
   - `localstack.openapi.spec → FileApiOASPlugin` — ships `openapi.yaml`; LocalStack merges it into `/openapi.yaml`.
2. No patches to LocalStack's own code. The extension is self-contained and safe to remove.

---

## License

Apache 2.0 — see [LICENSE](LICENSE).
