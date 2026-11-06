import json
import tempfile
import unittest
from pathlib import Path

from src.domain_store import DomainStore
from src.domains import GLPITicket, GLPIUser


class DomainStoreTests(unittest.TestCase):
    def test_should_save_and_load_cached_domains(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_path = Path(tmp_dir) / "glpi_cache.json"
            store = DomainStore(cache_path=str(cache_path))

            store.data["tickets"] = [
                GLPITicket(
                    id=1,
                    name="Teste",
                    content="<p>Conteúdo</p>",
                    status="Novo",
                    category="Rede",
                    entity="Entidade raiz",
                    requester="joao",
                )
            ]
            store.data["users"] = [
                GLPIUser(
                    id=2,
                    username="glpi",
                    realname="Sistema",
                    firstname="GLPI",
                    email=None,
                    is_active=True,
                )
            ]

            store.save()
            loaded = DomainStore(cache_path=str(cache_path))
            loaded.load()

            self.assertEqual(len(loaded.data["tickets"]), 1)
            self.assertEqual(loaded.data["tickets"][0]["name"], "Teste")
            self.assertEqual(loaded.data["users"][0]["username"], "glpi")

            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            self.assertIn("tickets", payload)
            self.assertIn("users", payload)


if __name__ == "__main__":
    unittest.main()
