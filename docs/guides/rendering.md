# Rendering state

[`tyrant.engine.renderer`](../reference/engine.md) turns a [`GameState`](../reference/models.md#tyrant.models.GameState) into something an LLM can read. Both functions take the state and the viewer's uid, and scrub the state for that viewer before rendering, so the full state can be passed directly:

```python
from tyrant import render_dict, render_text

prompt = render_text(state, uid)
payload = render_dict(state, uid)
```

## `render_dict`

[`render_dict`](../reference/engine.md#tyrant.engine.render_dict) returns plain `dict`, `list`, `str`, `int`, `bool` and `None` values, so it can be passed straight to `json.dumps`. It has these sections:

| Key | Contents |
|---|---|
| `viewer` | The viewer's uid, role, party, whether they're alive, and their known teammates |
| `players` | Every player in seat order, with party, role and whether they're alive |
| `board` | Policies enacted and needed to win, the fascist track, the election tracker, the Hitler zone, veto, and the pile sizes |
| `government` | The president, the chancellor and the previous government |
| `turn` | The phase, who the game is waiting on, the active power, the viewer's hand, the winner and the discussion |
| `timeline` | Every public event |
| `knowledge` | The viewer's private knowledge |

## `render_text`

[`render_text`](../reference/engine.md#tyrant.engine.render_text) builds Markdown from the same dict, with sections for the viewer's role and known teammates, the players, the board and election tracker, the government, the current phase, who must act and the discussion topic and round, a numbered timeline of public events and discussion, and the viewer's private knowledge. Hidden values always render as `unknown`.

```markdown
# Secret Hitler: Player 0's view

## You
- Player 0
- Role: liberal
- Party: liberal
- Status: alive
- Known teammates: none

## Players
In seat order:
- Player 0 (you): party liberal, role liberal, alive
- Player 2: party unknown, role unknown, alive
...
```

To keep prompts small, `render_text` shows speeches from only the last two discussions; older ones collapse into one line each. `render_dict` keeps every speech.
