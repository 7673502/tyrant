# API reference

The common names can be imported straight from `tyrant`: `GameRunner`, `Agent`, `GameState`, `Action`, the enums, the engine functions, the bundled agents and the exceptions.

```python
from tyrant import GameRunner, Party, RandomAgent
```

Each subpackage exports its full vocabulary:

| Package | Exports |
|---|---|
| [`tyrant.models`](models.md) | Every model, action, event, claim, knowledge and enum type, plus `create_game` and `scrub_state` |
| [`tyrant.engine`](engine.md) | `GameRunner`, `get_legal_actions`, `apply_action`, the renderer and the replay functions |
| [`tyrant.agents`](agents.md) | `RandomAgent` and `BiasedRandomAgent` |
| [`tyrant.llm`](llm.md) | `SYSTEM_PROMPT`, `system_prompt`, `build_prompt`, `parse_action`, `parse_notes` and `MAX_NOTES_LENGTH` |
| [`tyrant.llm.agent`](llm.md#tyrant.llm.agent) | `LLMAgent`, which needs the `llm` extra |
| [`tyrant.exceptions`](exceptions.md) | `TyrantError`, `InvalidMoveError` and `AgentError` |

Anything not listed in a package's `__all__` is internal and may change.
