# Design

Tyrant is a functional engine: game state is an immutable value, and every move produces a new one. This makes it easy to share states between agents, store them, and branch from them in a search.

## Immutable models

Every model is a `@dataclass(frozen=True)`. Collections inside models are `tuple`s and [`frozendict`](https://pypi.org/project/frozendict/)s, never `list`s or `dict`s, so nothing inside a state can be changed after it's made:

```python
state.phase = GamePhase.GAME_OVER
```

```text
dataclasses.FrozenInstanceError: cannot assign to field 'phase'
```

To change a field, make a copy with `dataclasses.replace`, as the engine does.

## Pure transitions

The engine is a set of functions from state to state:

- [`create_game`](reference/models.md#tyrant.models.create_game) builds the starting [`GameState`](reference/models.md#tyrant.models.GameState).
- [`get_legal_actions`](reference/engine.md#tyrant.engine.get_legal_actions) lists what a player may do in a state.
- [`apply_action`](reference/engine.md#tyrant.engine.apply_action) returns the next state and leaves its input untouched.
- [`scrub_state`](reference/models.md#tyrant.models.scrub_state) returns a copy with everything one player may not see replaced by [`HIDDEN`](reference/models.md#tyrant.models.HIDDEN).

```python
next_state = apply_action(state, action, uid)
assert next_state is not state
```

Randomness is part of the state too. The deck is shuffled from `GameState.rng_state`, so the same state and action always give the same result.

## The runner

[`GameRunner`](reference/engine.md#tyrant.engine.GameRunner) is the only stateful piece. It holds the current state, asks [agents](reference/models.md#tyrant.models.Agent) for actions with a scrubbed copy, applies them, and records a [replay](guides/replays.md). Agents never receive the full state, so they can't cheat by reading it.

## Layers

| Package | Role | Depends on |
|---|---|---|
| `tyrant.models` | Data types and state transitions | `frozendict` |
| `tyrant.engine` | Action routing, the runner, rendering, replays | `tyrant.models` |
| `tyrant.agents` | Simple bundled agents and a human player | `tyrant.models` |
| `tyrant.llm` | Prompts and reply parsing | `tyrant.engine` |
| `tyrant.llm.agent` | `LLMAgent` | `tyrant.llm`, `litellm` |

The core game logic never imports anything LLM-related, so the `llm` extra stays optional.
