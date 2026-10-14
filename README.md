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
