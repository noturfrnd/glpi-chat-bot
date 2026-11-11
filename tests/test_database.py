import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import src.database as database
from src.database import Base, ChatMessage, init_db


class ChatMessageDatabaseTests(unittest.IsolatedAsyncioTestCase):
    async def test_init_db_creates_the_chat_message_table(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            test_engine = create_async_engine(
                f"sqlite+aiosqlite:///{(Path(temp_dir) / 'chat.db').as_posix()}"
            )
            try:
                with patch.object(database, "engine", test_engine):
                    await init_db()

                async with test_engine.connect() as connection:
                    table_exists = await connection.run_sync(
                        lambda sync_connection: "chat_messages"
                        in inspect(sync_connection).get_table_names()
                    )

                self.assertTrue(table_exists)
            finally:
                await test_engine.dispose()

    async def test_messages_are_persisted_and_queryable_by_conversation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "chat.db"
            test_engine = create_async_engine(
                f"sqlite+aiosqlite:///{database_path.as_posix()}"
            )
            test_session_factory = async_sessionmaker(
                test_engine,
                expire_on_commit=False,
            )

            try:
                async with test_engine.begin() as connection:
                    await connection.run_sync(Base.metadata.create_all)

                async with test_session_factory() as session:
                    session.add_all(
                        [
                            ChatMessage(
                                conversation_id="conversation-1",
                                role="user",
                                content="Olá",
                            ),
                            ChatMessage(
                                conversation_id="conversation-1",
                                role="assistant",
                                content="Como posso ajudar?",
                            ),
                        ]
                    )
                    await session.commit()

                async with test_session_factory() as session:
                    result = await session.scalars(
                        select(ChatMessage)
                        .where(ChatMessage.conversation_id == "conversation-1")
                        .order_by(ChatMessage.id)
                    )
                    messages = result.all()

                self.assertEqual(
                    [(message.role, message.content) for message in messages],
                    [
                        ("user", "Olá"),
                        ("assistant", "Como posso ajudar?"),
                    ],
                )
                self.assertTrue(database_path.exists())
            finally:
                await test_engine.dispose()


if __name__ == "__main__":
    unittest.main()
