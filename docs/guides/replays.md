# Replays

[`GameRunner`](../reference/engine.md#tyrant.engine.GameRunner) records every action it applies, including random fallback actions, in `runner.replay`, a [`Replay`](../reference/models.md#tyrant.models.Replay). Write it to a gzipped JSON file that a viewer can read without the Python engine:

```python
from tyrant import read_replay, write_replay

await runner.run()
write_replay(runner.replay, "game.json.gz")
data = read_replay("game.json.gz")
```

[`replay_dict`](../reference/engine.md#tyrant.engine.replay_dict) returns the same data without writing a file.

## File format

The file holds the setup with every hidden role, then one entry per applied action:

```json
{
  "version": 2,
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
  "result": {"winner": "liberal", "condition": "liberal_policies"}
}
```

Each step lists the events and private knowledge its action produced. `fallback` is `true` when the agent failed every attempt and the runner played a random legal action for it, so a step with `fallback: false` was the agent's own choice. Version 1 files have no `fallback` field and can't tell the two apart. Actions leave out `description` and `message`; speech text is in the step's `speech` event. `result` is `null` if the game has not ended.

## Snapshots

Each `state` is a complete board snapshot: `phase`, `president`, `chancellor`, `previous_president`, `previous_chancellor`, `alive`, `liberal_policies`, `fascist_policies`, `election_tracker`, `draw_pile` and `discard_pile` (counts), `hand`, `votes`, `active_power`, and `discussion` (`null` or `{context, round, rounds, speaker}`). A viewer can jump straight to any step without replaying the rules.
