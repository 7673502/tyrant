# Your first game

This tutorial runs a game between five [`RandomAgent`](../reference/agents.md#tyrant.agents.RandomAgent)s, reads what happened, and then runs many games to get win rates.

## Run one game

[`GameRunner`](../reference/engine.md#tyrant.engine.GameRunner) deals roles, asks each agent for an action when it's their turn, and applies the actions until someone wins. Agents are asynchronous, so the runner is too:

```python
import asyncio

from tyrant import GameRunner, RandomAgent


async def main():
    agents = [RandomAgent(uid) for uid in range(5)]
    runner = GameRunner(agents, seed=7)
    final_state = await runner.run()
    print(final_state.winner)


asyncio.run(main())
```

Each agent's `uid` becomes its player ID. A game needs 5 to 10 players. Passing `seed` makes the deal, the seating and the deck repeatable. `RandomAgent` itself uses Python's global `random` module, so for fully repeatable games also call `random.seed(...)`.

`run()` returns the final [`GameState`](../reference/models.md#tyrant.models.GameState). Every model in Tyrant is a frozen dataclass, so you can keep this state around and read it safely.

## See how it ended

Every public event is recorded in order in `GameState.events`. The last one is always a [`GameOverEvent`](../reference/models.md#tyrant.models.GameOverEvent) with the winner and the [`WinCondition`](../reference/models.md#tyrant.models.WinCondition):

```python
from tyrant.models import GameOverEvent

game_over = final_state.events[-1]
assert isinstance(game_over, GameOverEvent)
print(f"{game_over.winner} wins by {game_over.condition}")
```

```text
fascist wins by fascist_policies
```

Print the first few events to follow the game:

```python
for event in final_state.events[:3]:
    print(event)
```

```text
NominationEvent(president_uid=2, chancellor_uid=4)
ElectionEvent(president_uid=2, chancellor_uid=4, votes=frozendict.frozendict({0: <Vote.JA: 'ja'>, ...}), result=<Vote.NEIN: 'nein'>)
NominationEvent(president_uid=3, chancellor_uid=0)
```

The [event log guide](../guides/events.md) lists every event type.

## See what a player saw

The final state holds every hidden role. [`render_text`](../reference/engine.md#tyrant.engine.render_text) shows the game from one player's seat, with everything else hidden:

```python
from tyrant import render_text

print(render_text(final_state, 0))
```

```markdown
# Secret Hitler: Player 0's view

## You
- Player 0
- Role: liberal
- Party: liberal
- Status: dead
- Known teammates: none

## Players
In seat order:
- Player 2: party unknown, role unknown, dead
...
```

This is the same text an LLM agent receives. See [Rendering state](../guides/rendering.md).

## Run many games

Random play is a useful baseline. `examples/basic_usage.py` plays 1,000 ten-player games and counts the wins:

```python
--8<-- "examples/basic_usage.py"
```

```sh
uv run python examples/basic_usage.py
```

Next, [write your own agent](custom-agent.md).
