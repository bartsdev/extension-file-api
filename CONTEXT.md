# Context

Glossary for the LocalStack File API extension. Terms only — no implementation.

## Glossary

### File API
A generic REST endpoint, served at `/_localstack/files` by a LocalStack Extension, for writing/reading/deleting files inside a running LocalStack instance. Exists to work around the fact that ephemeral (cloud-hosted) instances cannot have host files mounted or init-hooks delivered.

### Extension
The LocalStack Extension (`localstack.extensions` plux namespace) that registers the File API routes on the gateway via `update_gateway_routes`. Auto-installable on ephemeral instances via `EXTENSION_AUTO_INSTALL`.

### OAS Plugin
The `localstack.openapi.spec` plux plugin that ships this package's `openapi.yaml`. LocalStack merges it into the spec served at `/openapi.yaml`, so the File API appears in the existing Swagger UI at `/_localstack/swagger`. No edit to LocalStack's built-in spec.

### Allowlisted root
A directory under which the File API permits writes/reads/deletes. Any target path resolving outside every allowlisted root is rejected. Configured via `FILE_API_ALLOWED_ROOTS`; defaults to `/tmp`, `/workspace`, `/etc/localstack/init`.

### Target path
The absolute in-container destination for an uploaded file, supplied per-request (multipart field `path` or `?path=`). Always validated against the allowlist after symlink resolution.
