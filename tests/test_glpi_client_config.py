import os
import unittest
from unittest.mock import patch

from src.glpi_client import GLPIClient


class GLPIClientConfigurationTests(unittest.TestCase):
    def test_uses_the_current_glpi_server_as_default(self):
        with patch.dict(os.environ, {}, clear=True):
            client = GLPIClient()

        self.assertEqual(client.base_url, "http://146.235.38.123:8080")

    def test_environment_url_overrides_the_default(self):
        with patch.dict(
            os.environ,
            {"GLPI_BASE_URL": "http://glpi.example:8080/"},
            clear=True,
        ):
            client = GLPIClient()

        self.assertEqual(client.base_url, "http://glpi.example:8080")

    def test_explicit_url_overrides_the_environment(self):
        with patch.dict(
            os.environ,
            {"GLPI_BASE_URL": "http://glpi.example:8080"},
            clear=True,
        ):
            client = GLPIClient(base_url="http://127.0.0.1:8080/")

        self.assertEqual(client.base_url, "http://127.0.0.1:8080")


if __name__ == "__main__":
    unittest.main()
