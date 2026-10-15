# Discussion

Players can talk to each other after public game events: a nomination, a failed election, policy claims, and presidential powers. Discussion is off by default. Turn it on with one flag:

```python
runner = GameRunner(agents, discussion_enabled=True)
```

## Speaking order

During a [`DISCUSSION`](../reference/models.md#tyrant.models.GamePhase) phase, alive players take turns in seat order, starting with the president. Before a presidential power, the order starts one seat after the president, so the president hears the table before acting. The table goes around twice by default. Set `discussion_rounds` to change that:

```python
runner = GameRunner(agents, discussion_enabled=True, discussion_rounds=1)
```

The discussion in progress is in `GameState.discussion`, a [`Discussion`](../reference/models.md#tyrant.models.Discussion) with the context, the speaker order, and the current speaker and round.

## Speaking

On their turn, a player's legal actions are a [`SpeakAction`](../reference/models.md#tyrant.models.SpeakAction) and a [`PassAction`](../reference/models.md#tyrant.models.PassAction). To say something, fill in the message:

```python
from dataclasses import replace

return replace(speak_action, message="I'm a liberal, I swear.")
```

Whitespace in a message is collapsed, and the message is cut to [`MAX_SPEECH_LENGTH`](../reference/models.md#tyrant.models.MAX_SPEECH_LENGTH) (500) characters. An empty message counts as a pass.

## The transcript

The full public transcript is kept as [`SpeechEvent`](../reference/models.md#tyrant.models.SpeechEvent)s in `GameState.events`. Each one is tagged with the [`DiscussionContext`](../reference/models.md#tyrant.models.DiscussionContext) that triggered it, and a pass is recorded with `text=None`. See `examples/discussion.py`.

To keep prompts small, [`render_text`](../reference/engine.md#tyrant.engine.render_text) shows speeches from only the last two discussions; older ones collapse into one line each. [`render_dict`](../reference/engine.md#tyrant.engine.render_dict) keeps every speech.

## Discussion before a power

When policy claims unlock an investigation, special election, or execution, the discussion that follows is tagged `BEFORE_INVESTIGATION`, `BEFORE_SPECIAL_ELECTION`, or `BEFORE_EXECUTION` instead of `AFTER_POLICY_CLAIMS`, so the table can weigh in before the president acts. A policy peek involves no choice, so it keeps `AFTER_POLICY_CLAIMS`.
