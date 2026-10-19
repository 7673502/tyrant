# Writing an agent

An agent is any object that satisfies the [`Agent`](../reference/models.md#tyrant.models.Agent) protocol: a `uid` attribute and an async `choose_action` method. This tutorial writes one, then steps the engine by hand the way a search agent would.

## The protocol

```python
class Agent(Protocol):
    uid: int

    async def choose_action(
        self, state: GameState, valid_actions: tuple[Action, ...]
    ) -> Action: ...
```

[`GameRunner`](../reference/engine.md#tyrant.engine.GameRunner) calls `choose_action` whenever the player has something to do. It passes two things:

- `state` is already scrubbed with [`scrub_state`](../reference/models.md#tyrant.models.scrub_state), so it only holds what this player is allowed to know. Hidden values are the [`HIDDEN`](../reference/models.md#tyrant.models.HIDDEN) sentinel.
- `valid_actions` is a tuple of the legal [`Action`](../reference/models.md#tyrant.models.Action)s, each with a human-readable `description`.

Return one of the offered actions. You don't need to inherit from anything.

An agent can also have a `profile`, a mapping of strings such as a model name. [Replays](../guides/replays.md) show the profile for the player.

## A trusting agent

This agent nominates players it knows are on its team and votes for governments with a chancellor it trusts. Fascists know their teammates, so the agent plays well for them; liberals only know themselves and anyone they investigated. Everything else is random.

```python
import random
from dataclasses import replace

from tyrant import HIDDEN, Vote
from tyrant.models import NominateAction, SpeakAction, VoteAction


class TrustingAgent:
    def __init__(self, uid: int):
        self.uid = uid

    async def choose_action(self, state, valid_actions):
        me = next(p for p in state.players if p.uid == self.uid)
        known = {p.uid: p.party for p in state.players if p.party is not HIDDEN}

        for action in valid_actions:
            match action:
                case NominateAction(target_uid=uid) if known.get(uid) == me.party:
                    return action
                case VoteAction(vote=vote) if state.chancellor in known:
                    trusted = known[state.chancellor] == me.party
                    if (vote is Vote.JA) == trusted:
                        return action

        action = random.choice(valid_actions)
        if isinstance(action, SpeakAction):
            return replace(action, message=f"Player {self.uid} has nothing to hide.")
        return action
```

Notes on the code:

- Actions are frozen dataclasses, so `match` with class patterns is the easiest way to read them. The [models reference](../reference/models.md) lists every action type.
- When discussion is on, a [`SpeakAction`](../reference/models.md#tyrant.models.SpeakAction) is offered with an empty `message`. Fill it in with `dataclasses.replace`. The runner ignores changes to `message` and `description` when it checks that an action was offered.
- If `choose_action` raises `InvalidMoveError` or `AgentError`, times out, or returns an action that wasn't offered, the runner asks again and eventually plays a fallback for the agent: a pass during discussion, otherwise a random legal action. Any other exception ends the game, so bugs in your agent surface right away. See [Agent resilience](../guides/agent-resilience.md).

Mix it with random players and run a game with discussion:

```python
import asyncio

from tyrant import GameRunner, RandomAgent


async def main():
    agents = [TrustingAgent(0), TrustingAgent(1)]
    agents += [RandomAgent(uid) for uid in range(2, 7)]
    runner = GameRunner(agents, seed=3, discussion_enabled=True)
    final_state = await runner.run()
    print(final_state.winner, len(runner.faults), "faults")


asyncio.run(main())
```

## Stepping the engine yourself

`GameRunner` is a thin loop over three pure functions. A search agent such as MCTS can call them directly:

- [`create_game`](../reference/models.md#tyrant.models.create_game) returns the starting `GameState`.
- [`get_legal_actions`](../reference/engine.md#tyrant.engine.get_legal_actions) lists what a player may do now, or returns an empty tuple if it's not their turn.
- [`apply_action`](../reference/engine.md#tyrant.engine.apply_action) returns a new state and leaves the old one untouched.

This loop plays a whole game without any agents:

```python
import random

from tyrant import GamePhase, apply_action, create_game, get_legal_actions

rng = random.Random(0)
state = create_game(uids=(0, 1, 2, 3, 4), seed=1)

while state.phase is not GamePhase.GAME_OVER:
    for player in state.players:
        actions = get_legal_actions(state, player.uid)
        if actions:
            state = apply_action(state, rng.choice(actions), player.uid)
            break

print(state.winner)
```

Because `apply_action` never mutates its input, expanding a search node is just a comprehension:

```python
president = state.players[state.president_index].uid
children = [
    apply_action(state, action, president)
    for action in get_legal_actions(state, president)
]
```

The states from `create_game` and `apply_action` hold every secret. Before an agent reasons about one, scrub it for that agent's seat, as `GameRunner` does:

```python
from tyrant import scrub_state

view = scrub_state(state, 0)
print([(p.uid, p.role) for p in view.players])
```

```text
[(0, <Role.LIBERAL: 'liberal'>), (2, HIDDEN), (1, HIDDEN), (4, HIDDEN), (3, HIDDEN)]
```

Don't simulate forward from a scrubbed state. The deck, the shuffle state and other players' roles are `HIDDEN`, so `apply_action` gives wrong results or fails once it needs them. A search agent has to fill in the hidden values with guesses first. See [Private knowledge](../guides/knowledge.md) for what each player keeps.

## Debugging with `render_text`

[`render_text`](../reference/engine.md#tyrant.engine.render_text) prints a player's view as Markdown. It scrubs the state for you, so it's a quick way to check what your agent could see:

```python
from tyrant import render_text

print(render_text(state, 0))
```

Next, [run a game with LLM agents](llm-game.md).
