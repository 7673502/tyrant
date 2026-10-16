# Prompting LLM agents

[`tyrant.llm`](../reference/llm.md) holds the pieces every LLM agent needs, with no provider calls, so it works without the `llm` extra. [`LLMAgent`](../reference/llm.md#tyrant.llm.agent.LLMAgent) is built from these pieces; use them directly to write an agent for another client library.

## Building prompts

[`SYSTEM_PROMPT`](../reference/llm.md#tyrant.llm.SYSTEM_PROMPT) explains the rules and asks the model to end its reply with `{"action": N, "message": "...", "notes": "..."}`. It is the same for every game, so send it first to benefit from prompt caching. Its discussion rules tell the model that repeating the board state is pointless and that it should stay silent unless it has a new claim, question or accusation, so discussions stay short. [`build_prompt`](../reference/llm.md#tyrant.llm.build_prompt) renders the viewer's state followed by their numbered options, and [`parse_action`](../reference/llm.md#tyrant.llm.parse_action) turns the reply back into one of the offered actions:

```python
from tyrant.llm import SYSTEM_PROMPT, build_prompt, parse_action

async def choose_action(self, state, valid_actions):
    prompt = build_prompt(state, self.uid, valid_actions)
    reply = await call_llm(system=SYSTEM_PROMPT, user=prompt)
    return parse_action(reply, valid_actions)
```

`parse_action` reads the last JSON object in the reply, so the model may reason before it. It raises [`InvalidMoveError`](../reference/exceptions.md#tyrant.exceptions.InvalidMoveError) when the reply has no usable choice, which [`GameRunner`](../reference/engine.md#tyrant.engine.GameRunner) treats like any other [agent failure](agent-resilience.md).

`build_prompt` also takes optional `notes`, rendered as a `## Your Notes` section between the state and the options. [`parse_notes`](../reference/llm.md#tyrant.llm.parse_notes) reads them back from the same JSON object as `parse_action`. See [Notes](#notes).

## How `LLMAgent` uses them

Each turn, `LLMAgent` sends `SYSTEM_PROMPT` as the system message and `build_prompt(...)` as the user message, and returns `parse_action(reply, valid_actions)`. When `parse_action` rejects a reply, the agent raises the error to `GameRunner` and, when it is next asked about the same state, adds the rejected reply and the reason to the conversation. A retry passes the same state, so it sees the feedback; any later decision has a different state, so an old rejection never leaks into it, even when the options are the same. When the provider call itself fails, for example with a network error, the agent raises [`AgentError`](../reference/exceptions.md#tyrant.exceptions.AgentError) with the original error as its cause. Timeouts, retries and the fallback action are left to `GameRunner`.

Each agent keeps running totals of `prompt_tokens`, `completion_tokens`, `cached_tokens` and `cost`, in US dollars from `litellm.completion_cost`. A model litellm has no price for adds nothing to `cost`, and the move still goes through.

## Inspecting exchanges

To see exactly what a model was sent and what it sent back, pass `on_exchange` to `LLMAgent`. It is called once for each provider call with a plain JSON dict: the agent's `uid`, the `messages` sent (including the rejected reply and feedback on a retry), the raw `reply` (`None` when the provider call failed), that call's `prompt_tokens`, `completion_tokens`, `cached_tokens` and `cost`, and the `error` that rejected the call as its `repr`, or `None` when the reply became a move. A timed-out call is cancelled before it returns, so it sends nothing; `GameRunner` still records the timeout as a fault.

```python
agent = LLMAgent(0, "anthropic/claude-haiku-5-5", on_exchange=lambda e: print(e["reply"]))
```

The callback runs inside `choose_action`, so keep it fast; to send exchanges over the network, put them on an `asyncio.Queue` and send them from another task. An exception it raises leaves the agent like any other: an `AgentError`, `InvalidMoveError` or `TimeoutError` counts as a fault and is retried, and anything else ends the game.

Replays hold neither prompts nor accepted replies, so `on_exchange` is the only way to see them. Used together with `GameRunner`'s [`on_update`](replays.md#live-games), each exchange arrives before the `fault` or `step` message it leads to, so a viewer can attach it to the next of those for the same `uid`. Exchanges from players asked at the same time, such as during a vote, can interleave.

## Personas

`LLMAgent` takes an optional `persona`, a short description of how that player plays:

```python
agent = LLMAgent(0, "anthropic/claude-haiku-5-5", persona="Cautious, rarely accuses without a contradiction.")
```

When `persona` is set, the system message is [`system_prompt(persona)`](../reference/llm.md#tyrant.llm.system_prompt): `SYSTEM_PROMPT` followed by a `## Your Personality` section holding the persona. Every player's system message still starts with the same `SYSTEM_PROMPT` text, so the provider can keep reusing its cached prefix. With no persona, the system message is exactly `SYSTEM_PROMPT`.

Describe a playing style, not a goal. "Cautious, rarely accuses without a contradiction" or "talkative, pushes hard on vote patterns" shape how a player argues without changing what they are trying to win. A persona that clashes with the role, such as "always tell the truth" for a Fascist, pulls the model against its own win condition and mostly adds noise when you're comparing models.

## Notes

An `LLMAgent` keeps private notes, one string that lasts for one game. Only that agent sees them: they are shown back to it under `## Your Notes` on each of its turns, so it can track suspicions, claims and plans between turns.

A reply may include `notes` in its final JSON object. When present, it replaces the previous notes entirely; when missing, the previous notes stay. Only replies that become accepted moves change the notes, so a rejected reply leaves them alone. Notes have their whitespace collapsed, the same as speeches, and are cut to [`MAX_NOTES_LENGTH`](../reference/llm.md#tyrant.llm.MAX_NOTES_LENGTH) (200) characters. They are rendered as an escaped quoted string, so they can't forge a prompt section. Read an agent's current notes from `agent.notes`. Notes are not recorded in replays.
