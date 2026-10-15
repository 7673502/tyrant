# Event log

Every public game event is appended to `GameState.events`, in order. Each entry is a frozen subclass of [`Event`](../reference/models.md#tyrant.models.Event):

| Event | Recorded when |
|---|---|
| [`NominationEvent`](../reference/models.md#tyrant.models.NominationEvent) | The president nominates a chancellor |
| [`ElectionEvent`](../reference/models.md#tyrant.models.ElectionEvent) | An election resolves, with every player's vote and the result |
| [`PolicyEnactedEvent`](../reference/models.md#tyrant.models.PolicyEnactedEvent) | A policy is enacted, with its president and chancellor, or with both set to `None` for a top-deck |
| [`VetoEvent`](../reference/models.md#tyrant.models.VetoEvent) | The president approves or denies a chancellor's veto |
| [`ClaimEvent`](../reference/models.md#tyrant.models.ClaimEvent) | A player makes a claim, linked to its government or power, and to its target for an investigation |
| [`InvestigationEvent`](../reference/models.md#tyrant.models.InvestigationEvent), [`SpecialElectionEvent`](../reference/models.md#tyrant.models.SpecialElectionEvent), [`ExecutionEvent`](../reference/models.md#tyrant.models.ExecutionEvent) | A presidential power is used, with the president and target |
| [`SpeechEvent`](../reference/models.md#tyrant.models.SpeechEvent) | A player speaks or passes during [discussion](discussion.md) |
| [`GameOverEvent`](../reference/models.md#tyrant.models.GameOverEvent) | The game ends, with the winner and the [`WinCondition`](../reference/models.md#tyrant.models.WinCondition) |

The log is fully public, so [`scrub_state`](../reference/models.md#tyrant.models.scrub_state) passes it through unchanged. Match on the event type to read it:

```python
from tyrant.models import ElectionEvent

for event in state.events:
    match event:
        case ElectionEvent(votes=votes, result=result):
            ...
```

What players learn in secret is kept separately. See [Private knowledge](knowledge.md).
