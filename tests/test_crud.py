import json
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.crud import GenericCRUD, import_cache
from src.database import Base, CACHE_TABLES


class GenericCRUDTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "crud.db"
        self.engine = create_async_engine(
            f"sqlite+aiosqlite:///{database_path.as_posix()}"
        )
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def asyncTearDown(self):
        await self.engine.dispose()
        self.temp_dir.cleanup()

    async def test_generic_crud_supports_create_read_update_and_delete(self):
        async with self.session_factory() as session:
            crud = GenericCRUD(session)

            created = await crud.create("tickets", {"name": "Teste"})
            self.assertEqual(created["data"], {"name": "Teste"})

            loaded = await crud.get("tickets", created["id"])
            self.assertEqual(loaded, created)
            self.assertEqual(await crud.list("tickets"), [created])

            updated = await crud.update(
                "tickets",
                created["id"],
                {"name": "Atualizado"},
            )
            self.assertEqual(updated["data"], {"name": "Atualizado"})
            self.assertTrue(await crud.delete("tickets", created["id"]))
            self.assertIsNone(await crud.get("tickets", created["id"]))
            self.assertFalse(await crud.delete("tickets", created["id"]))

    async def test_cache_import_creates_domain_tables_without_persisting_tokens(self):
        cache_path = Path(self.temp_dir.name) / "glpi_cache.json"
        cache_path.write_text(
            json.dumps(
                {
                    "account": [
                        {
                            "access_token": "do-not-copy",
                            "refresh_token": "also-do-not-copy",
                            "token_type": "Bearer",
                            "extra": {"token": "nested-token"},
                        }
                    ],
                    "users": [{"id": 7, "username": "ana"}],
                    "tickets": [{"id": 21, "name": "Rede"}],
                    "articles": [{"id": 2, "name": "VPN"}],
                    "categories": [{"id": 3, "name": "Suporte"}],
                    "timeline": [],
                }
            ),
            encoding="utf-8",
        )

        self.assertEqual(
            await import_cache(cache_path, self.session_factory),
            5,
        )
        self.assertEqual(
            await import_cache(cache_path, self.session_factory),
            5,
        )

        async with self.session_factory() as session:
            accounts = await session.execute(select(CACHE_TABLES["account"]))
            account = accounts.mappings().one()
            users = await session.execute(select(CACHE_TABLES["users"]))
            user_records = users.mappings().all()

        self.assertEqual(account["data"], {"token_type": "Bearer", "extra": {}})
        self.assertEqual(len(user_records), 1)

        async with self.engine.connect() as connection:
            tables = await connection.run_sync(
                lambda sync_connection: set(
                    inspect(sync_connection).get_table_names()
                )
            )
        self.assertTrue(
            {f"cache_{domain}" for domain in CACHE_TABLES}.issubset(tables)
        )


if __name__ == "__main__":
    unittest.main()
