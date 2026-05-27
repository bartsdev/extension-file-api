from localstack.plugins import OASPlugin


class FileApiOASPlugin(OASPlugin):
    """Registers this package's openapi.yaml so the /_localstack/files endpoints
    are merged into the LocalStack OpenAPI spec served at /_localstack/swagger.

    Convention (see localstack.plugins.OASPlugin): plugins.py and openapi.yaml
    live at the same pathname.
    """

    name = "localstack_file_api"
