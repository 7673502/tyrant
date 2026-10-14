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
