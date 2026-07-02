# Custom Exceptions Implementation Plan

## Context
Currently, `src/tyrant/models/game_state.py` raises generic `ValueError`s for invalid state transitions. To properly support LLM agents as outlined in Phase 3 of the roadmap, we need a catchable exception hierarchy.

## Proposed Hierarchy
Adhering strictly to the "Simplicity First" project guideline, we will only create the exceptions explicitly required to handle the most distinct game rules, avoiding over-engineering a separate class for every edge case. 

```python
class TyrantError(Exception):
    """Base exception for the Tyrant package."""
    pass

class InvalidMoveError(TyrantError):
    """Raised when an action is generally invalid (e.g. bad target, dead player)."""
    pass

class WrongPhaseError(InvalidMoveError):
    """Raised when an action is attempted in the wrong GamePhase."""
    pass

class SelfTargetingError(InvalidMoveError):
    """Raised when a player illegally targets themselves."""
    pass

class TermLimitError(InvalidMoveError):
    """Raised when a chancellor nomination violates term limits."""
    pass
```

*Note: All other validation errors (e.g., invalid indices, targeting a dead player, powers not being unlocked) will simply raise the base `InvalidMoveError` with an appropriate message, rather than having bespoke classes.*

## Implementation Steps

1. **Create Exceptions:** Define the 5 exceptions listed above in a new file: `src/tyrant/models/exceptions.py`.
2. **Refactor State Logic:** Replace the `ValueError`s in `src/tyrant/models/game_state.py` with the appropriate exception from this simplified list.
3. **Update Tests:** Update `tests/test_game_state.py` to assert these specific errors (e.g., asserting `TermLimitError` instead of `ValueError` for the term limit tests).
