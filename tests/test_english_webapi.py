from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from aiohttp import ClientSession

from ortho_game_bot.art_culture import ArtCultureContent, ArtCultureRepository
from ortho_game_bot.config import Settings
from ortho_game_bot.database import ContentRepository, Database, GameRepository, UserRepository
from ortho_game_bot.english_vocabulary import (
    EnglishVocabularyContent,
    EnglishVocabularyRepository,
)
from ortho_game_bot.game.service import GameService
from ortho_game_bot.leader_library import LeaderLibraryContent, LeaderLibraryRepository
from ortho_game_bot.webapp.server import MiniAppServer

ROOT = Path(__file__).parents[1]


class EnglishVocabularyWebApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.temp_dir.name) / "webapi.sqlite3")
        await self.database.migrate()
        self.users = UserRepository(self.database)
        content = ContentRepository(self.database)
        await content.import_directory(ROOT / "data" / "words")
        english = EnglishVocabularyContent(
            ROOT / "data" / "english_vocabulary" / "content.ru.json.gz"
        )
        settings = Settings(
            bot_token="demo-token",
            admin_ids=frozenset(),
            database_path=self.database.path,
            content_path=ROOT / "data" / "words",
            leader_library_path=ROOT / "data" / "leader_library" / "content.ru.json",
            art_culture_path=ROOT / "data" / "art_culture" / "content.ru-en-kz.json.gz",
            english_vocabulary_path=ROOT
            / "data"
            / "english_vocabulary"
            / "content.ru.json.gz",
            port=0,
            webapp_demo=True,
        )
        self.english = english
        self.server = MiniAppServer(
            settings=settings,
            users=self.users,
            content=content,
            game_service=GameService(content, GameRepository(self.database), round_size=10),
            leader_library=LeaderLibraryContent(settings.leader_library_path),
            leader_library_progress=LeaderLibraryRepository(self.database),
            art_culture=ArtCultureContent(settings.art_culture_path),
            art_culture_progress=ArtCultureRepository(self.database),
            english_vocabulary=english,
            english_vocabulary_progress=EnglishVocabularyRepository(self.database),
        )
        await self.server.start()
        site = next(iter(self.server.runner.sites))
        port = site._server.sockets[0].getsockname()[1]
        self.base_url = f"http://127.0.0.1:{port}"
        self.client = ClientSession()
        async with self.client.get(f"{self.base_url}/api/bootstrap") as response:
            self.assertEqual(response.status, 200)

    async def asyncTearDown(self) -> None:
        await self.client.close()
        await self.server.stop()
        self.temp_dir.cleanup()

    async def test_catalog_round_and_server_side_answer(self) -> None:
        async with self.client.get(f"{self.base_url}/api/english/catalog") as response:
            self.assertEqual(response.status, 200)
            catalog = await response.json()
        self.assertEqual(len(catalog["levels"]), 6)
        self.assertEqual(len(catalog["modes"]), 3)
        self.assertEqual(catalog["review_due_count"], 0)

        async with self.client.post(
            f"{self.base_url}/api/english/start",
            json={"level_code": "L1", "mode": "spelling"},
        ) as response:
            self.assertEqual(response.status, 200)
            round_data = await response.json()
        question = round_data["question"]
        self.assertNotIn("correct_answer", question)
        authored = self.english.question(question["id"])
        correct_option = chr(65 + int(authored["correct_index"]))

        async with self.client.post(
            f"{self.base_url}/api/english/answer",
            json={
                "session_id": round_data["session"]["id"],
                "question_id": question["id"],
                "option_id": correct_option,
            },
        ) as response:
            self.assertEqual(response.status, 200)
            answer = await response.json()
        self.assertTrue(answer["is_correct"])
        self.assertEqual(answer["points"], 10)
        self.assertIn("next_question", answer)


if __name__ == "__main__":
    unittest.main()
