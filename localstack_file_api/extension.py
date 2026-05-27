import logging

from localstack.extensions.api import Extension, http

# Use the localstack.* namespace so logs flow through LocalStack's
# configured handlers, formatters, and LS_LOG level overrides.
LOG = logging.getLogger("localstack.extensions.file_api")


class FileApiExtension(Extension):
    name = "file-api"

    def on_extension_load(self):
        LOG.info("file-api extension loaded successfully")

    def update_gateway_routes(self, router: http.Router[http.RouteHandler]):
        from localstack_file_api.api import FileApiResource

        resource = FileApiResource()
        router.add("/_localstack/files", endpoint=resource.on_post, methods=["POST"])
        router.add("/_localstack/files", endpoint=resource.on_get, methods=["GET"])
        router.add("/_localstack/files", endpoint=resource.on_delete, methods=["DELETE"])
        LOG.info("file-api routes registered at /_localstack/files")
