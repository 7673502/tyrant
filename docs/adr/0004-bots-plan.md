# Agent Protocol Implementation Plan

## Current Context

We need a unified interface for external actors (AI, heuristics, humans) to interact with the game engine. We are rejecting two common patterns:
1. **The "Kitchen Sink" Move Object:** A single `Move` dataclass with a dozen optional fields (e.g., `target_uid`, `vote`, `policy_index`). This creates bloated payloads and gives LLMs room to hallucinate illegal argument combinations.
2. **Phase-Specific Methods:** An interface with a specific method for every phase (e.g., `get_vote`, `nominate_chancellor`). This fractures the game loop and breaks standard RL/MCTS environment structures, which expect a generic action space.

---

## What the Agent Protocol Needs to Represent

The Agent Protocol must establish a discrete, generic action space where every possible legal move at a given game state is serialized into a simple, immutable string ID along with a human-readable description.

The architecture will rely on:
1. A frozen `Action` dataclass.
2. A generic `get_legal_actions` pure function.
3. A single-method `Agent` Protocol that includes a `player_uid`.
4. A router to parse string IDs back into `game_state` transitions.

---

## Proposed Architecture

### 1. The Action Object
A simple, frozen container for discrete moves.

```python
@dataclass(frozen=True)
class Action:
    id: str
    description: str
```

*Note on Targets:* For any action that targets a player (e.g., `"nominate_12345"`, `"investigate_98765"`), the integer used in the `id` corresponds directly to the target player's exact `player_uid`.

### 2. The Agent Protocol
The interface that all bots and external players must implement. It takes a state and a menu of valid actions, returning the chosen `id`. The agent instance tracks its own `player_uid`.

```python
class Agent(Protocol):
    player_uid: int

    def choose_action(self, state: GameState, valid_actions: tuple[Action, ...]) -> str:
        ...
```

---

## Proposed Free Functions (Step-by-Step Plan)

### Step 1: `get_legal_actions(state: GameState, player_uid: int) -> tuple[Action, ...]`

A pure function that calculates the exact menu of legal actions for a specific player based on the current `state.phase`. To keep logic clean and maintainable, this will delegate to phase-specific private helper functions:

- **`_get_legal_actions_nomination(state: GameState, player_uid: int) -> tuple[Action, ...]`**: Returns a dynamic list like `Action(id="nominate_12345", description="Nominate Player 12345")` for all eligible players, strictly respecting term limits. Returns empty if the player is not the active President.
- **`_get_legal_actions_voting(state: GameState, player_uid: int) -> tuple[Action, ...]`**: Returns `Action(id="vote_ja", description="Vote JA")` and `Action(id="vote_nein", description="Vote NEIN")` for all alive players.
- **`_get_legal_actions_president_discard(state: GameState, player_uid: int) -> tuple[Action, ...]`**: Returns `Action(id="discard_X", description="Discard [Policy]")` where X corresponds to the policy indices the President can discard.
- **`_get_legal_actions_chancellor_enact(state: GameState, player_uid: int) -> tuple[Action, ...]`**: Returns `Action(id="enact_X", description="Enact [Policy]")` for the policies given to the Chancellor. Also returns a veto action if the veto power is unlocked.
- **`_get_legal_actions_presidential_power(state: GameState, player_uid: int) -> tuple[Action, ...]`**: Handles the different presidential powers (Investigate, Special Election, Execution) and returns the corresponding legal targets.
- **`_get_legal_actions_policy_peek(state: GameState, player_uid: int) -> tuple[Action, ...]`**: Returns an acknowledgement action, e.g., `Action(id="acknowledge_peek", description="Finish peeking at policies")`.
- **`_get_legal_actions_president_veto_response(state: GameState, player_uid: int) -> tuple[Action, ...]`**: Returns `Action(id="veto_approve", description="Approve Veto")` and `Action(id="veto_deny", description="Deny Veto")`.

*Note: For phases like SETUP or GAME_OVER, the function will return an empty tuple.*

### Step 2: `apply_action(state: GameState, player_uid: int, action_id: str) -> GameState` (The Router)

A pure function acting as a central router. It receives the `action_id`, parses it (e.g., splitting `"nominate_12345"` into `"nominate"` and the UID `12345`), and routes it to the corresponding pure state transition function in `game_state.py`.

### Step 3: Implement `RandomBot`

Create the simplest possible implementation of the `Agent` protocol to serve as a baseline testing utility.
- Must implement `player_uid: int`.
- Receives the `valid_actions` tuple.
- Uses a provided `Random` instance to select one `Action` uniformly at random.
- Returns the chosen `Action.id`.

---

## Implementation Order

```
1. Action dataclass + Agent Protocol           → verify: strict typing, player_uid included
2. get_legal_actions and Phase Helpers         → verify: exact action menus per phase and role
3. apply_action (Router)                       → verify: correct routing, parsing, and execution
4. RandomBot implementation                    → verify: adheres to protocol
```

### Testing Strategy

Every new class and free function (including helpers) requires a corresponding test class following existing patterns.
- `get_legal_actions` and its helpers must be exhaustively tested against various states to ensure it respects term limits, unlocked powers, and valid targets for the specified `player_uid`.
- `apply_action` must be tested to ensure it correctly maps IDs to state transitions, raising `InvalidMoveError` if given an impossible `action_id` or an action not currently in `get_legal_actions`.
- Immutability checks (`self.assert_pure_transition` / `self.assert_state_immutable`) must be strictly maintained across all tests.
