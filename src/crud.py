"""CRUD genérico para os registros importados do cache local do GLPI."""

import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy import Table, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.database import (
    AsyncSessionLocal,
    CACHE_DOMAINS,
    CACHE_TABLES,
    PROJECT_ROOT,
)

CACHE_FILE = PROJECT_ROOT / "data" / "glpi_cache.json"
logger = logging.getLogger(__name__)
SENSITIVE_FIELDS = {
    "token",
    "access_token",
    "refresh_token",
    "client_secret",
    "password",
    "authorization",
}


class GenericCRUD:
    """Oferece operações CRUD comuns para qualquer tabela de domínio do cache."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _table(domain: str) -> Table:
        try:
            return CACHE_TABLES[domain]
        except KeyError as exc:
            raise ValueError(f"Domínio de cache inválido: {domain}") from exc

    async def create(self, domain: str, data: dict[str, Any]) -> dict[str, Any]:
        table = self._table(domain)
        result = await self.session.execute(
            table.insert().values(source_key=None, data=data)
        )
        record_id = result.inserted_primary_key[0]
        if record_id is None:
            raise RuntimeError("O banco não retornou o ID do registro criado.")
        await self.session.commit()
        record = await self.get(domain, record_id)
        if record is None:
            raise RuntimeError("O registro criado não pôde ser recuperado.")
        return record

    async def get(self, domain: str, record_id: int) -> dict[str, Any] | None:
        table = self._table(domain)
        result = await self.session.execute(
            select(table).where(table.c.id == record_id)
        )
        row = result.mappings().one_or_none()
        return dict(row) if row is not None else None

    async def list(
        self,
        domain: str,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if offset < 0 or limit < 1:
            raise ValueError("offset deve ser >= 0 e limit deve ser >= 1.")
        table = self._table(domain)
        result = await self.session.execute(
            select(table).order_by(table.c.id).offset(offset).limit(limit)
        )
        return [dict(row) for row in result.mappings().all()]

    async def update(
        self,
        domain: str,
        record_id: int,
        data: dict[str, Any],
    ) -> dict[str, Any] | None:
        table = self._table(domain)
        result = await self.session.execute(
            update(table).where(table.c.id == record_id).values(data=data)
        )
        if result.rowcount == 0:
            await self.session.rollback()
            return None
        await self.session.commit()
        return await self.get(domain, record_id)

    async def delete(self, domain: str, record_id: int) -> bool:
        table = self._table(domain)
        result = await self.session.execute(
            table.delete().where(table.c.id == record_id)
        )
        if result.rowcount == 0:
            await self.session.rollback()
            return False
        await self.session.commit()
        return True

    async def upsert_by_source_key(
        self,
        domain: str,
        source_key: str,
        data: dict[str, Any],
    ) -> None:
        table = self._table(domain)
        statement = sqlite_insert(table).values(source_key=source_key, data=data)
        await self.session.execute(
            statement.on_conflict_do_update(
                index_elements=[table.c.source_key],
                set_={"data": statement.excluded.data},
            )
        )


def _remove_sensitive_fields(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _remove_sensitive_fields(item)
            for key, item in value.items()
            if key.lower() not in SENSITIVE_FIELDS
        }
    if isinstance(value, list):
        return [_remove_sensitive_fields(item) for item in value]
    return value


async def import_cache(
    cache_path: Path = CACHE_FILE,
    session_factory: async_sessionmaker[AsyncSession] = AsyncSessionLocal,
) -> int:
    """Importa os domínios conhecidos de glpi_cache.json sem copiar credenciais."""
    if not cache_path.exists():
        logger.info("Cache GLPI não encontrado em %s; importação ignorada.", cache_path)
        return 0

    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("A raiz do cache do GLPI deve ser um objeto JSON.")

    imported_count = 0
    async with session_factory() as session:
        crud = GenericCRUD(session)
        for domain in CACHE_DOMAINS:
            records = payload.get(domain, [])
            if not isinstance(records, list):
                raise ValueError(f"O domínio '{domain}' deve ser uma lista.")

            for index, record in enumerate(records):
                if not isinstance(record, dict):
                    raise ValueError(
                        f"O registro {index} do domínio '{domain}' deve ser um objeto."
                    )
                source_id = record.get("id")
                source_key = str(source_id) if source_id is not None else f"seed:{index}"
                await crud.upsert_by_source_key(
                    domain,
                    source_key,
                    _remove_sensitive_fields(record),
                )
                imported_count += 1
        await session.commit()

    return imported_count
