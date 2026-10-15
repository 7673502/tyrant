# Prompting LLM agents

[`tyrant.llm`](../reference/llm.md) holds the pieces every LLM agent needs, with no provider calls, so it works without the `llm` extra. [`LLMAgent`](../reference/llm.md#tyrant.llm.agent.LLMAgent) is built from these pieces; use them directly to write an agent for another client library.

## Building prompts

[`SYSTEM_PROMPT`](../reference/llm.md#tyrant.llm.SYSTEM_PROMPT) explains the rules and asks the model to end its reply with `{"action": N, "message": "...", "notes": "..."}`. It is the same for every game, so send it first to benefit from prompt caching. [`build_prompt`](../reference/llm.md#tyrant.llm.build_prompt) renders the viewer's state followed by their numbered options, and [`parse_action`](../reference/llm.md#tyrant.llm.parse_action) turns the reply back into one of the offered actions:

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

Each turn, `LLMAgent` sends `SYSTEM_PROMPT` as the system message and `build_prompt(...)` as the user message, and returns `parse_action(reply, valid_actions)`. When `parse_action` rejects a reply, the agent raises the error to `GameRunner` and, on its next call, adds the rejected reply and the reason to the conversation. Timeouts, retries and the random fallback are left to `GameRunner`.

Each agent keeps running totals of `prompt_tokens`, `completion_tokens`, `cached_tokens` and `cost`, in US dollars from `litellm.completion_cost`. A model litellm has no price for adds nothing to `cost`, and the move still goes through.

## Notes

An `LLMAgent` keeps private notes, one string that lasts for one game. Only that agent sees them: they are shown back to it under `## Your Notes` on each of its turns, so it can track suspicions, claims and plans between turns.

A reply may include `notes` in its final JSON object. When present, it replaces the previous notes entirely; when missing, the previous notes stay. Only replies that become accepted moves change the notes, so a rejected reply leaves them alone. Notes have their whitespace collapsed, the same as speeches, and are cut to [`MAX_NOTES_LENGTH`](../reference/llm.md#tyrant.llm.MAX_NOTES_LENGTH) (200) characters. They are rendered as an escaped quoted string, so they can't forge a prompt section. Read an agent's current notes from `agent.notes`. Notes are not recorded in replays.
