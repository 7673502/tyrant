# Tyrant

Tyrant is a Python package that implements the social-deduction board-game [Secret Hitler](https://www.secrethitler.com/) primarily to allow LLMs to play against one another.


## Discussion

Players can talk to each other after public game events: a nomination, a failed election, policy claims, and presidential powers. Discussion is off by default. Turn it on with one flag:

```python
runner = GameRunner(agents, discussion_enabled=True)
```

During a `DISCUSSION` phase, alive players take turns in seat order, starting with the president. Before a presidential power, the order starts one seat after the president, so the president hears the table before acting. The table goes around 3 times by default. Set `discussion_rounds` to change that:

```python
runner = GameRunner(agents, discussion_enabled=True, discussion_rounds=1)
```

On their turn, a player's legal actions are a `SpeakAction` and a `PassAction`. To say something, fill in the message:

```python
from dataclasses import replace

return replace(speak_action, message="I'm a liberal, I swear.")
```

The full public transcript is kept in `GameState.messages`. Each `Message` is tagged with the `DiscussionContext` that triggered it, and a pass is recorded with `text=None`. See `examples/discussion.py`.

When policy claims unlock an investigation, special election, or execution, the discussion that follows is tagged `BEFORE_INVESTIGATION`, `BEFORE_SPECIAL_ELECTION`, or `BEFORE_EXECUTION` instead of `AFTER_POLICY_CLAIMS`, so the table can weigh in before the president acts. A policy peek involves no choice, so it keeps `AFTER_POLICY_CLAIMS`.

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

## Private knowledge

What each player learned in secret is kept in `GameState.knowledge`, so it survives after transient fields such as `drawn_policies` are cleared. Each entry is a frozen subclass of `Knowledge` with the `uid` of the player who learned it:

| Knowledge | Recorded when |
|---|---|
| `PresidentDrawKnowledge` | A president draws 3 policies after a passed election |
| `ChancellorReceiveKnowledge` | A chancellor receives 2 policies from the president |
| `PeekKnowledge` | A president peeks at the top 3 policies |
| `InvestigationKnowledge` | A president learns the party of an investigated player |

`scrub_state` keeps only the viewer's own entries, so an agent never sees what another player learned.

## Rendering state for prompts

`tyrant.engine.renderer` turns a scrubbed `GameState` into something an LLM can read. Both functions take the scrubbed state and the viewer's uid:

```python
from tyrant.engine.renderer import render_dict, render_text

scrubbed = scrub_state(state, uid)
prompt = render_text(scrubbed, uid)
payload = render_dict(scrubbed, uid)
```

`render_dict` returns plain `dict`, `list`, `str`, `int`, `bool` and `None` values, so it can be passed straight to `json.dumps`. `render_text` builds Markdown from the same dict, with sections for the viewer's role and known teammates, the players, the board and election tracker, the government, the current phase, who must act and the discussion round, a numbered timeline of public events and discussion, and the viewer's private knowledge. Hidden values always render as `unknown`.

## Agent Resilience

`GameRunner` only applies actions that were offered to the agent. An action matches an offered one when it has the same type and the same identifying fields; `description` and `SpeakAction.message` are ignored, since the agent may fill them in.

If an agent returns an action that was not offered, raises an exception, or takes longer than `timeout` seconds, the runner asks it again. After `max_retries` failed retries, it plays a random legal action on the agent's behalf. The fallback is drawn from a generator seeded with the runner's `seed`, so seeded games stay reproducible.

```python
runner = GameRunner(agents, max_retries=2, timeout=60.0)
```

By default `max_retries=2` and `timeout=None`, so a well-behaved agent is queried exactly once with no time limit. Every failed attempt is logged as a warning and recorded in `runner.faults` as an `AgentFault` with the player's `uid`, the `phase`, the `reason`, and whether it triggered the fallback (`fell_back`).
