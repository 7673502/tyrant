import asyncio
import os
import unittest
from dataclasses import replace
from random import Random

from tyrant.engine.game_runner import GameRunner
from tyrant.engine.renderer import render_text
from tyrant.models.action import Action, SpeakAction
from tyrant.models.game_state import GameState

PLAYER_COUNT = 10
VIEWER_UID = 0
SEEDS = (0, 1, 2)
MIN_AVERAGE_SHARED_START = 0.5


class PromptRecordingAgent:
    """Plays randomly and records the text prompts it would send."""

    def __init__(self, uid: int, seed: int, prompts: list[str]):
        self.uid = uid
        self.rng = Random(seed * PLAYER_COUNT + uid)
        self.prompts = prompts

    async def choose_action(
        self, state: GameState, valid_actions: tuple[Action, ...]
    ) -> Action:
        self.prompts.append(render_text(state, self.uid))
        action = self.rng.choice(valid_actions)
        if isinstance(action, SpeakAction):
            return replace(action, message=f"Player {self.uid} has something to say.")
        return action


def viewer_prompts(seed: int) -> list[str]:
    """Plays one game with discussion and returns every prompt rendered for the viewer."""
    prompts: list[str] = []
    agents = [
        PromptRecordingAgent(uid, seed, prompts if uid == VIEWER_UID else [])
        for uid in range(PLAYER_COUNT)
    ]
    asyncio.run(GameRunner(agents, seed=seed, discussion_enabled=True).run())
    return prompts


def average_shared_start(prompts: list[str]) -> float:
    """Returns the average fraction of each prompt that starts identically to the previous one."""
    fractions = [
        len(os.path.commonprefix((previous, current))) / len(current)
        for previous, current in zip(prompts, prompts[1:])
    ]
    return sum(fractions) / len(fractions)


class TestPromptCache(unittest.TestCase):
    def test_render_text_shares_long_start_between_calls(self):
        """Verifies that consecutive prompts for one viewer share a long common start."""
        for seed in SEEDS:
            with self.subTest(seed=seed):
                self.assertGreaterEqual(
                    average_shared_start(viewer_prompts(seed)),
                    MIN_AVERAGE_SHARED_START,
                )


if __name__ == "__main__":
    unittest.main()
