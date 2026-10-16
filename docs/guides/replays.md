# Replays

[`GameRunner`](../reference/engine.md#tyrant.engine.GameRunner) records every action it applies, including fallback actions, and every failed agent attempt in `runner.replay`, a [`Replay`](../reference/models.md#tyrant.models.Replay). Write it to a gzipped JSON file that a viewer can read without the Python engine:

```python
from tyrant import read_replay, write_replay

await runner.run()
write_replay(runner.replay, "game.json.gz")
data = read_replay("game.json.gz")
```

[`replay_dict`](../reference/engine.md#tyrant.engine.replay_dict) returns the same data without writing a file.

## File format

The file holds the setup with every hidden role, then one entry per applied action and one per agent fault:

```json
{
  "version": 5,
  "tyrant_version": "0.3.0",
  "settings": {"player_count": 7, "discussion_enabled": false,
               "discussion_rounds": 1, "discussion_contexts": ["after_execution", ...],
               "fascist_track": ["none", "investigate_loyalty", ...]},
  "players": [{"uid": 3, "seat": 0, "role": "hitler", "party": "fascist",
               "agent": {"type": "LLMAgent", "model": "anthropic/claude-haiku-5-5",
                         "persona": "Cautious."}}, ...],
  "initial": { <snapshot> },
  "steps": [
    {"index": 0, "uid": 3,
     "action": {"type": "nominate", "target_uid": 5},
     "fallback": false,
     "notes": "Player 5 claimed liberal; watch their votes.",
     "events": [{"type": "nomination", "president_uid": 3, "chancellor_uid": 5}],
     "knowledge": [],
     "state": { <snapshot> }}
  ],
  "faults": [
    {"step": 12, "uid": 3, "phase": "voting",
     "reason": "InvalidMoveError('Action must be between 1 and 2, got 3')",
     "reply": "I'll vote nein. {\"action\": 3}", "fell_back": false}
  ],
  "result": {"winner": "liberal", "condition": "liberal_policies"}
}
```

`version` is the file format, which a viewer checks before reading the file. `tyrant_version` is the package version that wrote it, which tells you which rules and options produced the game; it can change without the format changing.

`agent` describes what plays each player: the agent's class name as `type`, plus its `profile` if it has one. [`LLMAgent`](../reference/llm.md#tyrant.llm.agent.LLMAgent)'s profile holds its `model` and `persona`. `agent` is `null` for a `Replay` built without agents. Each step's `notes` holds the acting agent's private notes after the step, or `null` for agents that keep none.

Each step lists the events and private knowledge its action produced. `fallback` is `true` when the agent failed every attempt and the runner played an action for it (a pass during discussion, a declined claim when one is offered, otherwise a random legal action), so a step with `fallback: false` was the agent's own choice. Version 1 files have no `fallback` field and can't tell the two apart. Version 2 files have no `president_discard` knowledge and no `discarded` field in `president_enact` claims. Actions leave out `description` and `message`; speech text is in the step's `speech` event. `result` is `null` if the game has not ended.

## Faults

`faults` lists every failed attempt, in order, from [`AgentFault`](../reference/models.md#tyrant.models.AgentFault). A fault happens before the step it belongs to exists, so `step` is the index of the step the agent's action became: the agent's own choice after a recovered fault, or the runner's fallback when `fell_back` is `true`. `reason` is the `repr` of the exception. `reply` is the agent's raw reply when the attempt was rejected with an [`InvalidMoveError`](../reference/exceptions.md#tyrant.exceptions.InvalidMoveError) that carried one, as [`LLMAgent`](../reference/llm.md#tyrant.llm.agent.LLMAgent) does, so bad JSON, an option number that wasn't offered and an empty speech can be told apart. It is `null` for timeouts, provider errors and agents that don't fill it in.

## Older versions

[`read_replay`](../reference/engine.md#tyrant.engine.read_replay) returns the file as stored, so older files still load; check `version` before reading newer fields. Version 4 files have no `correction` field on `claim` events and no `correct_claim` actions. Version 3 files have no `tyrant_version`, player `agent` or step `notes`. Version 2 files have no `faults`. Version 1 files have no `faults` and no step `fallback` field.

## Live games

Pass `on_update` to `GameRunner` to follow a game as it is played, for example to stream it to a web page. The runner calls it with one JSON-serializable message at a time:

- `{"type": "start", "replay": ...}` when `run` starts, holding the replay so far in the file format, with no steps.
- `{"type": "step", "step": ...}` after each action, holding the same entry as in `steps`.
- `{"type": "fault", "fault": ...}` after each failed attempt, holding the same entry as in `faults`. It arrives before the step it points at.
- `{"type": "end", "result": ...}` when the game ends.

Appending each `step` and `fault` to the `start` replay and setting `result` gives the same data as `replay_dict`, so a viewer can use one code path for files and live games. If an agent or the callback itself raises an unexpected exception, the game ends without an `end` message.

```python
import json

runner = GameRunner(agents, on_update=lambda message: print(json.dumps(message)))
await runner.run()
```

The callback runs inside the game loop, so keep it fast; to send messages over the network, put them on an `asyncio.Queue` and send them from another task. Like a replay file, the messages show every role, hand and note, so a public audience sees everything as it happens. Neither the messages nor a replay file hold the prompts sent to an `LLMAgent` or its accepted replies; pass [`on_exchange`](prompting.md#inspecting-exchanges) to the agent for those.

## Snapshots

Each `state` is a complete board snapshot: `phase`, `president`, `chancellor`, `previous_president`, `previous_chancellor`, `alive`, `liberal_policies`, `fascist_policies`, `election_tracker`, `draw_pile` and `discard_pile` (counts), `hand`, `votes`, `active_power`, and `discussion` (`null` or `{context, round, rounds, speaker}`). A viewer can jump straight to any step without replaying the rules.
