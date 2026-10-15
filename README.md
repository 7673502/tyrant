# Tyrant

Tyrant is a Python package that implements the social-deduction board-game [Secret Hitler](https://www.secrethitler.com/) primarily to allow LLMs to play against one another.

## Public API

Import the common names straight from `tyrant`: `GameRunner`, `Agent`, `GameState`, `Action`, the enums, the engine functions, the bundled agents and the exceptions.

```python
from tyrant import GameRunner, Party, RandomAgent
```

Each subpackage exports its full vocabulary:

| Package | Exports |
|---|---|
| `tyrant.models` | Every model, action, event, claim, knowledge and enum type, plus `create_game` and `scrub_state` |
| `tyrant.engine` | `GameRunner`, `get_legal_actions`, `apply_action`, the renderer and the replay functions |
| `tyrant.agents` | `RandomAgent` and `BiasedRandomAgent` |
| `tyrant.llm` | `SYSTEM_PROMPT`, `build_prompt`, `parse_action`, `parse_notes` and `MAX_NOTES_LENGTH` |
| `tyrant.llm.agent` | `LLMAgent`, which needs the `llm` extra |

Anything not listed in a package's `__all__` is internal and may change.


## Discussion

Players can talk to each other after public game events: a nomination, a failed election, policy claims, and presidential powers. Discussion is off by default. Turn it on with one flag:

```python
runner = GameRunner(agents, discussion_enabled=True)
```

During a `DISCUSSION` phase, alive players take turns in seat order, starting with the president. Before a presidential power, the order starts one seat after the president, so the president hears the table before acting. The table goes around twice by default. Set `discussion_rounds` to change that:

```python
runner = GameRunner(agents, discussion_enabled=True, discussion_rounds=1)
```

To keep prompts small, `render_text` shows speeches from only the last two discussions; older ones collapse into one line each. `render_dict` keeps every speech.

On their turn, a player's legal actions are a `SpeakAction` and a `PassAction`. To say something, fill in the message:

```python
from dataclasses import replace

return replace(speak_action, message="I'm a liberal, I swear.")
```

The full public transcript is kept as `SpeechEvent`s in `GameState.events`. Each one is tagged with the `DiscussionContext` that triggered it, and a pass is recorded with `text=None`. See `examples/discussion.py`.

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

## Replays

`GameRunner` records every action it applies, including random fallback actions, in `runner.replay`. Write it to a gzipped JSON file that a viewer can read without the Python engine:

```python
from tyrant import read_replay, write_replay

await runner.run()
write_replay(runner.replay, "game.json.gz")
data = read_replay("game.json.gz")
```

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

Each `state` is a complete board snapshot: `phase`, `president`, `chancellor`, `previous_president`, `previous_chancellor`, `alive`, `liberal_policies`, `fascist_policies`, `election_tracker`, `draw_pile` and `discard_pile` (counts), `hand`, `votes`, `active_power`, and `discussion` (`null` or `{context, round, rounds, speaker}`). A viewer can jump straight to any step without replaying the rules.

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

`tyrant.engine.renderer` turns a `GameState` into something an LLM can read. Both functions take the state and the viewer's uid, and scrub the state for that viewer before rendering, so the full state can be passed directly:

```python
from tyrant import render_dict, render_text

prompt = render_text(state, uid)
payload = render_dict(state, uid)
```

`render_dict` returns plain `dict`, `list`, `str`, `int`, `bool` and `None` values, so it can be passed straight to `json.dumps`. `render_text` builds Markdown from the same dict, with sections for the viewer's role and known teammates, the players, the board and election tracker, the government, the current phase, who must act and the discussion topic and round, a numbered timeline of public events and discussion, and the viewer's private knowledge. Hidden values always render as `unknown`.

## Prompting LLM agents

LLM support is optional. Install it with the `llm` extra, which adds `litellm`:

```sh
pip install "tyrant[llm]"
```

`tyrant.llm` holds the pieces every LLM agent needs, with no provider calls. `SYSTEM_PROMPT` explains the rules and asks the model to end its reply with `{"action": N, "message": "...", "notes": "..."}`; it is the same for every game, so send it first to benefit from prompt caching. `build_prompt` renders the viewer's state followed by their numbered options, and `parse_action` turns the reply back into one of the offered actions:

```python
from tyrant.llm import SYSTEM_PROMPT, build_prompt, parse_action

async def choose_action(self, state, valid_actions):
    prompt = build_prompt(state, self.uid, valid_actions)
    reply = await call_llm(system=SYSTEM_PROMPT, user=prompt)
    return parse_action(reply, valid_actions)
```

`parse_action` reads the last JSON object in the reply, so the model may reason before it. It raises `InvalidMoveError` when the reply has no usable choice, which `GameRunner` treats like any other agent failure.

`build_prompt` also takes optional `notes`, rendered as a `## Your Notes` section between the state and the options. `parse_notes` reads them back from the same JSON object as `parse_action`. See [Notes](#notes).

## Running an LLM game

`LLMAgent` plays through [litellm](https://docs.litellm.ai/), so it works with any model litellm supports. It needs the `llm` extra, and importing `tyrant.llm.agent` without it raises an `ImportError` that says so:

```python
from tyrant import GameRunner
from tyrant.llm.agent import LLMAgent

agents = [LLMAgent(uid, "anthropic/claude-haiku-5-5") for uid in range(5)]
runner = GameRunner(agents, discussion_enabled=True)
await runner.run()
```

The model is any litellm model string. litellm reads provider API keys from its usual environment variables, such as `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` or `GEMINI_API_KEY`, so set the one for your provider before you start. Anything else for `litellm.acompletion`, such as `temperature` or `api_base`, goes in `completion_kwargs`:

```python
from frozendict import frozendict

agent = LLMAgent(0, "openai/gpt-5", completion_kwargs=frozendict(temperature=0.7))
```

Each turn, the agent sends `SYSTEM_PROMPT` as the system message and `build_prompt(...)` as the user message, and returns `parse_action(reply, valid_actions)`. When `parse_action` rejects a reply, the agent raises the error to `GameRunner` and, on its next call, adds the rejected reply and the reason to the conversation. Timeouts, retries and the random fallback are left to `GameRunner`.

Each agent keeps running totals of `prompt_tokens`, `completion_tokens`, `cached_tokens` and `cost`, in US dollars from `litellm.completion_cost`. A model litellm has no price for adds nothing to `cost`, and the move still goes through.

`examples/llm_game.py` plays a 5-player game with discussion and prints the winner, the faults, the token totals, the cost and each agent's final notes:

```sh
export ANTHROPIC_API_KEY=...
TYRANT_MODEL=anthropic/claude-haiku-5-5 uv run --extra llm python examples/llm_game.py
```

### Notes

An `LLMAgent` keeps private notes, one string that lasts for one game. Only that agent sees them: they are shown back to it under `## Your Notes` on each of its turns, so it can track suspicions, claims and plans between turns.

A reply may include `notes` in its final JSON object. When present, it replaces the previous notes entirely; when missing, the previous notes stay. Only replies that become accepted moves change the notes, so a rejected reply leaves them alone. Notes have their whitespace collapsed, the same as speeches, and are cut to `MAX_NOTES_LENGTH` (1000) characters. They are rendered as an escaped quoted string, so they can't forge a prompt section. Read an agent's current notes from `agent.notes`. Notes are not recorded in replays.

## Agent Resilience

`GameRunner` only applies actions that were offered to the agent. An action matches an offered one when it has the same type and the same identifying fields; `description` and `SpeakAction.message` are ignored, since the agent may fill them in.

If an agent returns an action that was not offered, raises an exception, or takes longer than `timeout` seconds, the runner asks it again. After `max_retries` failed retries, it plays a random legal action on the agent's behalf. The fallback is drawn from a generator seeded with the runner's `seed`, so seeded games stay reproducible.

```python
runner = GameRunner(agents, max_retries=2, timeout=60.0)
```

By default `max_retries=2` and `timeout=120.0`, so a well-behaved agent is queried exactly once and a hung call is abandoned after two minutes. Pass `timeout=None` to disable the limit, for example when a human is playing. Every failed attempt is logged as a warning and recorded in `runner.faults` as an `AgentFault` with the player's `uid`, the `phase`, the `reason`, and whether it triggered the fallback (`fell_back`). The replay marks each fallback step with `fallback: true`.
