import unittest
from contextlib import redirect_stdout
from io import StringIO

from benchmarks.prompt_size import main, measure, shared_prefix

PLAYER_COUNT = 10
SEEDS = (0, 1, 2)
MAX_PROMPT_TOKENS = 135_000
MAX_INPUT_TOKENS_PER_GAME = 50_000_000
MAX_OUTPUT_TOKENS_PER_GAME = 125_000
MIN_SHARED_PREFIX = 0.4


class TestPromptSize(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = {seed: measure(seed, PLAYER_COUNT) for seed in SEEDS}

    def test_max_prompt_tokens_under_threshold(self):
        """Verifies that no single prompt grows past the loose per-call threshold."""
        for seed, result in self.results.items():
            with self.subTest(seed=seed):
                self.assertLessEqual(result["max_prompt_tokens"], MAX_PROMPT_TOKENS)

    def test_input_tokens_per_game_under_threshold(self):
        """Verifies that the prompt tokens of a game stay under the loose per-game threshold."""
        for seed, result in self.results.items():
            with self.subTest(seed=seed):
                self.assertLessEqual(result["input_tokens"], MAX_INPUT_TOKENS_PER_GAME)

    def test_output_tokens_per_game_under_threshold(self):
        """Verifies that the speech tokens of a game stay under the loose per-game threshold."""
        for seed, result in self.results.items():
            with self.subTest(seed=seed):
                self.assertLessEqual(
                    result["output_tokens"], MAX_OUTPUT_TOKENS_PER_GAME
                )

    def test_shared_prefix_above_floor(self):
        """Verifies that consecutive prompts for one player share a long common start."""
        for seed, result in self.results.items():
            with self.subTest(seed=seed):
                self.assertGreaterEqual(result["shared_prefix"], MIN_SHARED_PREFIX)


class TestSharedPrefix(unittest.TestCase):
    def test_shared_prefix_fractions(self):
        """Verifies that each prompt's fraction is its common start with the previous prompt over its own length."""
        self.assertEqual(shared_prefix(["abcd", "abxy", "abxyzzzz"]), [0.5, 0.5])

    def test_shared_prefix_immutability(self):
        """Verifies that shared_prefix returns a new list and leaves the prompts unchanged."""
        prompts = ["abcd", "abxy"]
        self.assertIsNot(shared_prefix(prompts), prompts)
        self.assertEqual(prompts, ["abcd", "abxy"])


class TestMain(unittest.TestCase):
    def _run(self, argv: list[str]) -> str:
        output = StringIO()
        with redirect_stdout(output):
            main(argv)
        return output.getvalue()

    def test_main_table(self):
        """Verifies that main prints a header and one row per seed."""
        lines = self._run(["--seeds", "3", "4", "--players", "5"]).splitlines()
        self.assertTrue(lines[0].startswith("Seed  Max tokens/call"))
        self.assertEqual([line.split()[0] for line in lines[1:]], ["3", "4"])

    def test_main_immutability(self):
        """Verifies that main does not mutate its argument list."""
        argv = ["--seeds", "3", "--players", "5"]
        self._run(argv)
        self.assertEqual(argv, ["--seeds", "3", "--players", "5"])


if __name__ == "__main__":
    unittest.main()
