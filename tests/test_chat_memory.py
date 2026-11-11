import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine

import src.chat_memory as chat_memory
from src.chat_memory import build_session_id, create_chat_memory


class ChatMemoryTests(unittest.TestCase):
    def test_build_session_id_uses_user_and_conversation_ids(self):
        session_id = build_session_id(
            {"sub": "glpi-user-7"},
            "conversation-3",
        )

        self.assertEqual(session_id, '["glpi-user-7","conversation-3"]')
        self.assertNotEqual(
            session_id,
            build_session_id({"sub": "glpi-user-8"}, "conversation-3"),
        )
        self.assertNotEqual(
            session_id,
            build_session_id({"sub": "glpi-user-7"}, "conversation-4"),
        )

    def test_build_session_id_requires_user_and_conversation_ids(self):
        with self.assertRaises(ValueError):
            build_session_id({}, "conversation-3")
        with self.assertRaises(ValueError):
            build_session_id({"sub": "glpi-user-7"}, " ")
        with self.assertRaises(ValueError):
            build_session_id(None, "conversation-3")

    def test_memory_restores_persisted_history_and_limits_it_to_ten_messages(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_url = f"sqlite:///{(Path(temp_dir) / 'memory.db').as_posix()}"
            test_engine = create_engine(database_url)
            try:
                with patch.object(chat_memory, "chat_history_engine", test_engine):
                    memory = create_chat_memory("user-7:conversation-3")
                    for turn in range(6):
                        memory.save_context(
                            {"input": f"user message {turn}"},
                            {"output": f"assistant message {turn}"},
                        )

                    restored_memory = create_chat_memory("user-7:conversation-3")
                    history = restored_memory.load_memory_variables({})["chat_history"]
                    other_session_history = create_chat_memory(
                        "user-7:conversation-4"
                    ).load_memory_variables({})["chat_history"]
            finally:
                test_engine.dispose()

        self.assertEqual(len(history), 10)
        self.assertEqual(history[0].content, "user message 1")
        self.assertEqual(history[-1].content, "assistant message 5")
        self.assertEqual(other_session_history, [])


if __name__ == "__main__":
    unittest.main()
