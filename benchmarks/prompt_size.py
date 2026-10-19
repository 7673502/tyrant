"""Measures how large LLM prompts get over random games with discussion on.

Every player plays randomly but always speaks, with a speech of
MAX_SPEECH_LENGTH characters, so discussions run their full rounds. Tokens
are estimated as CHARS_PER_TOKEN characters each. A prompt is SYSTEM_PROMPT
plus build_prompt, and output tokens count only speeches.

The shared prefix is the average fraction of each user message that starts
identically to the same player's previous one, which is what a provider's
prompt cache can reuse beyond the system message.
"""

import argparse
import asyncio
import os
from dataclasses import replace
from random import Random

from frozendict import frozendict

from tyrant.engine.game_runner import GameRunner
from tyrant.llm.prompt import SYSTEM_PROMPT, build_prompt
from tyrant.models.action import Action, SpeakAction
from tyrant.models.discussion import MAX_SPEECH_LENGTH
from tyrant.models.game_state import GameState

CHARS_PER_TOKEN = 4
COLUMNS = (
    ("Seed", "seed"),
    ("Max tokens/call", "max_prompt_tokens"),
    ("Mean tokens/call", "mean_prompt_tokens"),
    ("Input tokens/game", "input_tokens"),
    ("Output tokens/game", "output_tokens"),
    ("Shared prefix", "shared_prefix"),
)


class PromptRecordingAgent:
    """Plays randomly, always speaks at full length, and records each user message it would send."""

    def __init__(self, uid: int, rng: Random, prompts: list[str]):
        self.uid = uid
        self.rng = rng
        self.prompts = prompts

    async def choose_action(
        self, state: GameState, valid_actions: tuple[Action, ...]
    ) -> Action:
        self.prompts.append(build_prompt(state, self.uid, valid_actions))
        speak = next((a for a in valid_actions if isinstance(a, SpeakAction)), None)
        if speak is None:
            return self.rng.choice(valid_actions)
        return replace(speak, message="x" * MAX_SPEECH_LENGTH)


def shared_prefix(prompts: list[str]) -> list[float]:
    """Returns the fraction of each prompt that starts identically to the previous one.

    Args:
        prompts: One player's prompts, in order.

    Returns:
        One fraction per prompt after the first.
    """
    return [
        len(os.path.commonprefix((previous, current))) / len(current)
        for previous, current in zip(prompts, prompts[1:])
    ]


def measure(seed: int, player_count: int) -> frozendict:
    """Plays one game and returns its prompt size numbers.

    Args:
        seed: The game seed.
        player_count: The number of players.

    Returns:
        `max_prompt_tokens` and `mean_prompt_tokens` per call, `input_tokens`
        and `output_tokens` per game, and `shared_prefix`, the average
        fraction of a user message shared with the same player's previous one.
    """
    prompts: dict[int, list[str]] = {uid: [] for uid in range(player_count)}
    agents = [
        PromptRecordingAgent(uid, Random(seed * player_count + uid), prompts[uid])
        for uid in prompts
    ]
    runner = GameRunner(agents, seed=seed, discussion_enabled=True)
    asyncio.run(runner.run())
    tokens = [
        len(SYSTEM_PROMPT + prompt) // CHARS_PER_TOKEN
        for player_prompts in prompts.values()
        for prompt in player_prompts
    ]
    speeches = sum(isinstance(step.action, SpeakAction) for step in runner.replay.steps)
    fractions = [f for p in prompts.values() for f in shared_prefix(p)]
    return frozendict(
        max_prompt_tokens=max(tokens),
        mean_prompt_tokens=sum(tokens) // len(tokens),
        input_tokens=sum(tokens),
        output_tokens=speeches * MAX_SPEECH_LENGTH // CHARS_PER_TOKEN,
        shared_prefix=sum(fractions) / len(fractions),
    )


def _cell(value: int | float) -> str:
    return f"{value:.0%}" if isinstance(value, float) else f"{value:,}"


def main(argv: list[str] | None = None) -> None:
    """Prints a table of prompt size numbers with one row per seed.

    Args:
        argv: The command-line arguments, or None to read them from sys.argv.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    parser.add_argument("--players", type=int, default=10)
    args = parser.parse_args(argv)
    results = [measure(seed, args.players) | {"seed": seed} for seed in args.seeds]
    table = [[label for label, _ in COLUMNS]] + [
        [_cell(result[key]) for _, key in COLUMNS] for result in results
    ]
    widths = [max(len(row[i]) for row in table) for i in range(len(COLUMNS))]
    for row in table:
        print("  ".join(cell.ljust(width) for cell, width in zip(row, widths)).rstrip())


if __name__ == "__main__":
    main()
