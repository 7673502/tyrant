# Tyrant

Tyrant is a Python implementation of the social-deduction board game [Secret Hitler](https://www.secrethitler.com/). It's built for language models, search agents such as MCTS, and people to play against each other.

- **Immutable and functional.** Every state is a frozen value, and every move returns a new one. Branch, store and compare states freely. See [Design](concepts.md).
- **Fair by construction.** Agents only ever see a state scrubbed for their seat.
- **Ready for LLMs.** Prompt rendering, reply parsing and an optional [litellm](https://docs.litellm.ai/) agent are included.
- **Replayable.** Every game can be saved as a JSON replay with a full board snapshot after each move, or streamed live in the same format.

## Quick start

```sh
pip install tyrant
```

```python
import asyncio

from tyrant import GameRunner, RandomAgent


async def main():
    agents = [RandomAgent(uid) for uid in range(5)]
    final_state = await GameRunner(agents, seed=7).run()
    print(final_state.winner)


asyncio.run(main())
```

## Where to go next

| Section | For |
|---|---|
| [Installation](getting-started/installation.md) | Installing Tyrant and the `llm` extra |
| [Tutorials](tutorials/first-game.md) | Running a game, writing an agent, and playing LLMs against each other |
| [Guides](guides/discussion.md) | Discussion, the event log, private knowledge, rendering, replays, prompting and agent resilience |
| [API reference](reference/index.md) | Every public class and function, generated from the docstrings |
