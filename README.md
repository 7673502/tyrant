# Tyrant

Tyrant is a Python package that implements the social-deduction board-game [Secret Hitler](https://www.secrethitler.com/) primarily to allow LLMs to play against one another.


## Discussion

Players can talk to each other after public game events: a nomination, a failed election, policy claims, and presidential powers. Discussion is off by default. Turn it on with one flag:

```python
runner = GameRunner(agents, discussion_enabled=True)
```

During a `DISCUSSION` phase, each alive player gets one turn in seat order, starting with the president. On their turn, a player's legal actions are a `SpeakAction` and a `PassAction`. To say something, fill in the message:

```python
from dataclasses import replace

return replace(speak_action, message="I'm a liberal, I swear.")
```

The full public transcript is kept in `GameState.messages`. Each `Message` is tagged with the `DiscussionContext` that triggered it, and a pass is recorded with `text=None`. See `examples/discussion.py`.

## Event log

Every public game event is appended to `GameState.events`, in order. Each entry is a frozen subclass of `Event`:

| Event | Recorded when |
|---|---|
| `NominationEvent` | The president nominates a chancellor |
| `ElectionEvent` | An election resolves, with every player's vote and the result |
| `PolicyEnactedEvent` | A policy is enacted, with its president and chancellor, or with both set to `None` for a top-deck |
| `VetoEvent` | The president approves or denies a chancellor's veto |
| `ClaimEvent` | A player makes a claim, linked to its government or power, and to its target for an investigation |
| `InvestigationEvent`, `SpecialElectionEvent`, `ExecutionEvent` | A presidential power is used, with the president and target |
| `SpeechEvent` | A player speaks or passes during discussion |
| `GameOverEvent` | The game ends, with the winner and the `WinCondition` |

The log is fully public, so `scrub_state` passes it through unchanged. Match on the event type to read it:

```python
for event in state.events:
    match event:
        case ElectionEvent(votes=votes, result=result):
            ...
```

## Agent Resilience

`GameRunner` only applies actions that were offered to the agent. An action matches an offered one when it has the same type and the same identifying fields; `description` and `SpeakAction.message` are ignored, since the agent may fill them in.

If an agent returns an action that was not offered, raises an exception, or takes longer than `timeout` seconds, the runner asks it again. After `max_retries` failed retries, it plays a random legal action on the agent's behalf. The fallback is drawn from a generator seeded with the runner's `seed`, so seeded games stay reproducible.

```python
runner = GameRunner(agents, max_retries=2, timeout=60.0)
```

By default `max_retries=2` and `timeout=None`, so a well-behaved agent is queried exactly once with no time limit. Every failed attempt is logged as a warning and recorded in `runner.faults` as an `AgentFault` with the player's `uid`, the `phase`, the `reason`, and whether it triggered the fallback (`fell_back`).
