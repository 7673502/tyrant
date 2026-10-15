# Replays

[`GameRunner`](../reference/engine.md#tyrant.engine.GameRunner) records every action it applies, including random fallback actions, and every failed agent attempt in `runner.replay`, a [`Replay`](../reference/models.md#tyrant.models.Replay). Write it to a gzipped JSON file that a viewer can read without the Python engine:

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
  "version": 3,
  "settings": {"player_count": 7, "discussion_enabled": false,
               "discussion_rounds": 2, "fascist_track": ["none", "investigate_loyalty", ...]},
  "players": [{"uid": 3, "seat": 0, "role": "hitler", "party": "fascist"}, ...],
  "initial": { <snapshot> },
  "steps": [
    {"index": 0, "uid": 3,
     "action": {"type": "nominate", "target_uid": 5},
     "fallback": false,
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

Each step lists the events and private knowledge its action produced. `fallback` is `true` when the agent failed every attempt and the runner played a random legal action for it, so a step with `fallback: false` was the agent's own choice. Version 1 files have no `fallback` field and can't tell the two apart. Version 2 files have no `president_discard` knowledge, so they don't show which policy a president discarded. Actions leave out `description` and `message`; speech text is in the step's `speech` event. `result` is `null` if the game has not ended.

## Faults

`faults` lists every failed attempt, in order, from [`AgentFault`](../reference/models.md#tyrant.models.AgentFault). A fault happens before the step it belongs to exists, so `step` is the index of the step the agent's action became: the agent's own choice after a recovered fault, or the random fallback when `fell_back` is `true`. `reason` is the `repr` of the exception. `reply` is the agent's raw reply when the attempt was rejected with an [`InvalidMoveError`](../reference/exceptions.md#tyrant.exceptions.InvalidMoveError) that carried one, as [`LLMAgent`](../reference/llm.md#tyrant.llm.agent.LLMAgent) does, so bad JSON, an option number that wasn't offered and an empty speech can be told apart. It is `null` for timeouts, provider errors and agents that don't fill it in.

## Older versions

[`read_replay`](../reference/engine.md#tyrant.engine.read_replay) returns the file as stored, so older files still load; check `version` before reading newer fields. Version 2 files have no `faults`. Version 1 files have no `faults` and no step `fallback` field.

## Snapshots

Each `state` is a complete board snapshot: `phase`, `president`, `chancellor`, `previous_president`, `previous_chancellor`, `alive`, `liberal_policies`, `fascist_policies`, `election_tracker`, `draw_pile` and `discard_pile` (counts), `hand`, `votes`, `active_power`, and `discussion` (`null` or `{context, round, rounds, speaker}`). A viewer can jump straight to any step without replaying the rules.
