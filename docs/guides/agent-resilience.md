# Agent resilience

[`GameRunner`](../reference/engine.md#tyrant.engine.GameRunner) keeps a game going when an agent misbehaves.

## Offered actions only

`GameRunner` only applies actions that were offered to the agent. An action matches an offered one when it has the same type and the same identifying fields; `description` and [`SpeakAction.message`](../reference/models.md#tyrant.models.SpeakAction) are ignored, since the agent may fill them in.

## Retries and fallback

If an agent returns an action that was not offered, raises [`InvalidMoveError`](../reference/exceptions.md#tyrant.exceptions.InvalidMoveError) or [`AgentError`](../reference/exceptions.md#tyrant.exceptions.AgentError), or takes longer than `timeout` seconds, the runner asks it again. After `max_retries` failed retries, it plays a random legal action on the agent's behalf. The fallback is drawn from a generator seeded with the runner's `seed`, so seeded games stay reproducible.

```python
runner = GameRunner(agents, max_retries=2, timeout=60.0)
```

Any other exception is treated as a bug and ends the game: a `KeyError` in an agent's own code is raised from `runner.run()` instead of being hidden behind a random move. An agent that calls an outside service should wrap the failures it expects, such as network or provider errors, in `AgentError`. [`LLMAgent`](../reference/llm.md#tyrant.llm.agent.LLMAgent) does this for every error from its provider call.

By default `max_retries=2` and `timeout=120.0`, so a well-behaved agent is queried exactly once and a hung call is abandoned after two minutes. Pass `timeout=None` to disable the limit, for example when a human is playing.

## Faults

Every failed attempt is logged as a warning and recorded in `runner.faults` as an [`AgentFault`](../reference/models.md#tyrant.models.AgentFault) with the player's `uid`, the `phase`, the `reason`, and whether it triggered the fallback (`fell_back`). The [replay](replays.md) marks each fallback step with `fallback: true`.

```python
for fault in runner.faults:
    print(f"Player {fault.uid} in {fault.phase}: {fault.reason}")
```
