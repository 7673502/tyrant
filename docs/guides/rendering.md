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
| `government` | The president, the chancellor, the previous government, and the players term-limited from being nominated chancellor |
| `turn` | The phase, who the game is waiting on, the active power, the viewer's hand, the winner and the discussion |
| `timeline` | Every public event, each with the `government` number it belongs to |
| `knowledge` | The viewer's private knowledge, each with the `government` number it belongs to, or `None` for a peek or an investigation |

## `render_text`

[`render_text`](../reference/engine.md#tyrant.engine.render_text) builds Markdown from the same dict, with sections for the viewer's role and known teammates, the players, the board and election tracker, the government, the current phase, who must act and the discussion topic and round, a timeline of public events and discussion, and the viewer's private knowledge. Hidden values always render as `unknown`.

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

A [claim correction](discussion.md#correcting-a-claim) renders as "President Player 1 corrected their claim: drew fascist, fascist, liberal, discarded fascist, so passed fascist, liberal.", and the claim it replaced gains "(corrected later in this government)".

The Government section lists who can't be nominated chancellor next because of term limits:

```markdown
- Can't be nominated chancellor next: Player 2 (previous chancellor), Player 0 (previous president)
```

Each time the discard pile is shuffled back into the draw pile, the timeline shows "The discard pile was shuffled into the draw pile (now 14 policies)." under the current government.

## Governments

Every nomination starts a new government, numbered from 1, including nominations whose election fails. Its label names the president and the nominee, such as `Gov 3 (P2→P4)`. The timeline has no line numbers. Instead, each government's events sit under a `### Gov 3 (P2→P4)` heading, from its nomination up to the next one, including any discussion, presidential power or execution that follows. Events before the first nomination come before any heading. Because labels count nominations, they never change as the game goes on, so players can cite them:

```markdown
## Timeline

### Gov 1 (P1→P2)
- President Player 1 nominated Player 2 for chancellor.
- Election of President Player 1 and Chancellor Player 2 failed (ja: Player 1; nein: Player 2, Player 3).

### Gov 2 (P2→P3)
- President Player 2 nominated Player 3 for chancellor.
- Election of President Player 2 and Chancellor Player 3 passed (ja: Player 1, Player 2, Player 3; nein: none).
- President Player 2 and Chancellor Player 3 enacted a fascist policy.
```

Private knowledge from a legislative session names its government too, such as "In Gov 2 (P2→P3) you drew fascist, fascist, liberal, discarded liberal, passed fascist, fascist." Knowledge has no timestamp, so the viewer's k-th draw or discard maps to the k-th passed election in which they were president, and their k-th receive to the k-th passed election in which they were chancellor.
