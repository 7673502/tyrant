import asyncio
import unittest
from dataclasses import replace
from random import Random

from tyrant.engine.game_runner import GameRunner
from tyrant.llm.prompt import MAX_NOTES_LENGTH, SYSTEM_PROMPT, build_prompt
from tyrant.models.action import Action, SpeakAction
from tyrant.models.discussion import MAX_SPEECH_LENGTH
from tyrant.models.game_state import GameState

CHARS_PER_TOKEN = 4
PLAYER_COUNT = 10
SEEDS = (0, 1, 2)
MAX_PROMPT_TOKENS = 10_000
MAX_INPUT_TOKENS_PER_GAME = 6_000_000
MAX_OUTPUT_TOKENS_PER_GAME = 130_000


class TokenCountingAgent:
    """Plays randomly, always speaks and keeps notes at full length, and counts the text it reads and writes."""

    def __init__(self, uid: int, seed: int, prompts: list[int], outputs: list[int]):
        self.uid = uid
        self.rng = Random(seed * PLAYER_COUNT + uid)
        self.prompts = prompts
        self.outputs = outputs

    async def choose_action(
        self, state: GameState, valid_actions: tuple[Action, ...]
    ) -> Action:
        notes = "x" * MAX_NOTES_LENGTH
        prompt = SYSTEM_PROMPT + build_prompt(state, self.uid, valid_actions, notes)
        self.prompts.append(len(prompt) // CHARS_PER_TOKEN)
        speak = next((a for a in valid_actions if isinstance(a, SpeakAction)), None)
        if speak is None:
            self.outputs.append(MAX_NOTES_LENGTH // CHARS_PER_TOKEN)
            return self.rng.choice(valid_actions)
        self.outputs.append((MAX_SPEECH_LENGTH + MAX_NOTES_LENGTH) // CHARS_PER_TOKEN)
        return replace(speak, message="x" * MAX_SPEECH_LENGTH)


def simulate(seed: int) -> tuple[list[int], list[int]]:
    """Plays one game with default parameters and returns per-call prompt and output tokens."""
    prompts: list[int] = []
    outputs: list[int] = []
    agents = [
        TokenCountingAgent(uid, seed, prompts, outputs) for uid in range(PLAYER_COUNT)
    ]
    asyncio.run(GameRunner(agents, seed=seed, discussion_enabled=True).run())
    return prompts, outputs


class TestTokenBudget(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.games = {seed: simulate(seed) for seed in SEEDS}

    def test_max_prompt_tokens_within_budget(self):
        """Verifies that no single prompt exceeds the per-call token budget under default parameters."""
        for seed, (prompts, _) in self.games.items():
            with self.subTest(seed=seed):
                self.assertLessEqual(max(prompts), MAX_PROMPT_TOKENS)

    def test_input_tokens_per_game_within_budget(self):
        """Verifies that the total prompt tokens of a game stay within budget under default parameters."""
        for seed, (prompts, _) in self.games.items():
            with self.subTest(seed=seed):
                self.assertLessEqual(sum(prompts), MAX_INPUT_TOKENS_PER_GAME)

    def test_output_tokens_per_game_within_budget(self):
        """Verifies that the total speech and notes tokens of a game stay within budget under default parameters."""
        for seed, (_, outputs) in self.games.items():
            with self.subTest(seed=seed):
                self.assertLessEqual(sum(outputs), MAX_OUTPUT_TOKENS_PER_GAME)
