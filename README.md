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


## Agent Resilience

`GameRunner` only applies actions that were offered to the agent. An action matches an offered one when it has the same type and the same identifying fields; `description` and `SpeakAction.message` are ignored, since the agent may fill them in.

If an agent returns an action that was not offered, raises an exception, or takes longer than `timeout` seconds, the runner asks it again. After `max_retries` failed retries, it plays a random legal action on the agent's behalf. The fallback is drawn from a generator seeded with the runner's `seed`, so seeded games stay reproducible.

```python
runner = GameRunner(agents, max_retries=2, timeout=60.0)
```

By default `max_retries=2` and `timeout=None`, so a well-behaved agent is queried exactly once with no time limit. Every failed attempt is logged as a warning and recorded in `runner.faults` as an `AgentFault` with the player's `uid`, the `phase`, the `reason`, and whether it triggered the fallback (`fell_back`).
