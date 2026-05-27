import logging

from localstack.extensions.api import Extension

# Use the localstack.* namespace so logs flow through LocalStack's
# configured handlers, formatters, and LS_LOG level overrides.
LOG = logging.getLogger("localstack.extensions.file_api")


class FileApiExtension(Extension):
    name = "file-api"

    def on_extension_load(self):
        LOG.info("file-api extension loaded successfully")

    def on_platform_start(self):
        """Register /_localstack/files into the internal resource router.

        update_gateway_routes() plugs into the AWS-service gateway, which
        never sees /_localstack/* paths — those go through LocalstackResources
        (the internal handler). We therefore add our Resource directly to that
        router here, which is the same mechanism LocalStack uses for its own
        /_localstack/health, /_localstack/init, etc. endpoints.
        """
        from localstack.services.internal import Resource, get_internal_apis

        from localstack_file_api.api import FileApiResource

        get_internal_apis().add(Resource("/_localstack/files", FileApiResource()))
        LOG.info("file-api routes registered at /_localstack/files")
