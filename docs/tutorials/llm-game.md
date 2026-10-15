# Running an LLM game

This tutorial runs a game where language models play each other through [`LLMAgent`](../reference/llm.md#tyrant.llm.agent.LLMAgent).

## Install and set a key

Install the `llm` extra, which adds [litellm](https://docs.litellm.ai/):

```sh
pip install "tyrant[llm]"
```

litellm reads provider keys from its usual environment variables, such as `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` or `GEMINI_API_KEY`. Set the one for your provider:

```sh
export ANTHROPIC_API_KEY=...
```

## One model against random players

A five-player game with discussion takes a few hundred actions, so five `LLMAgent`s make a few hundred model calls. To try things out cheaply, seat one `LLMAgent` with four [`RandomAgent`](../reference/agents.md#tyrant.agents.RandomAgent)s:

```python
import asyncio

from tyrant import GameRunner, RandomAgent
from tyrant.llm.agent import LLMAgent


async def main():
    llm = LLMAgent(0, "anthropic/claude-haiku-5-5")
    agents = [llm] + [RandomAgent(uid) for uid in range(1, 5)]
    runner = GameRunner(agents, discussion_enabled=True)
    final_state = await runner.run()

    print(f"Winner: {final_state.winner}")
    print(f"Tokens: {llm.prompt_tokens} in, {llm.completion_tokens} out")
    print(f"Cost: ${llm.cost:.4f}")
    print(f"Notes: {llm.notes}")


asyncio.run(main())
```

The model is any litellm model string. Anything else for `litellm.acompletion`, such as `temperature` or `api_base`, goes in `completion_kwargs`:

```python
from frozendict import frozendict

agent = LLMAgent(0, "openai/gpt-5", completion_kwargs=frozendict(temperature=0.7))
```

To give a player a playing style, pass a `persona`. It should describe how the player plays, not what they want, since a persona that clashes with the role adds noise when you're comparing models:

```python
agent = LLMAgent(0, "anthropic/claude-haiku-5-5", persona="Cautious, rarely accuses without a contradiction.")
```

## What the model sees

Each turn the agent sends two messages:

1. [`SYSTEM_PROMPT`](../reference/llm.md#tyrant.llm.SYSTEM_PROMPT), with the rules and the reply format. It's the same for every game, so providers can cache it. A `persona` is appended after it under `## Your Personality`, so the cached prefix still matches.
2. [`build_prompt`](../reference/llm.md#tyrant.llm.build_prompt), with the player's [rendered view](../guides/rendering.md), their private notes, and their numbered options.

The model may reason first, then ends its reply with a JSON object such as `{"action": 3, "message": "...", "notes": "..."}`. [`parse_action`](../reference/llm.md#tyrant.llm.parse_action) turns that into one of the offered actions. If the reply can't be used, the agent raises, and on the retry for the same decision it shows the model its rejected reply and the reason. The [prompting guide](../guides/prompting.md) covers this in detail.

## A full LLM game

`examples/llm_game.py` seats five `LLMAgent`s with discussion on and prints the winner, the faults, the token totals, the cost and each agent's final notes:

```python
--8<-- "examples/llm_game.py"
```

```sh
export ANTHROPIC_API_KEY=...
TYRANT_MODEL=anthropic/claude-haiku-5-5 uv run --extra llm python examples/llm_game.py
```

## Save the game

`GameRunner` records every action it applies. Write the replay to a file to review the game later:

```python
from tyrant import write_replay

write_replay(runner.replay, "game.json.gz")
```

See [Replays](../guides/replays.md) for the file format.
