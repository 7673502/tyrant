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
3. A single-method `Agent` Protocol.
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

### 2. The Agent Protocol
The interface that all bots and external players must implement. It takes a state and a menu of valid actions, returning the chosen `id`.

```python
class Agent(Protocol):
    def choose_action(self, state: GameState, valid_actions: tuple[Action, ...]) -> str:
        ...
```

---

## Proposed Free Functions (Step-by-Step Plan)

### Step 1: `get_legal_actions(state: GameState) -> tuple[Action, ...]`

A pure function that evaluates the current `state.phase` and calculates the exact menu of legal actions. 
- **Voting:** Returns `Action(id="vote_ja", description="Vote JA")` and `Action(id="vote_nein", description="Vote NEIN")`.
- **Nomination:** Returns a dynamic list like `Action(id="nominate_2", description="Nominate Player 2")` for all eligible players, strictly respecting term limits.

### Step 2: `apply_action(state: GameState, action_id: str) -> GameState` (The Router)

A pure function acting as a central router. It receives the `action_id`, parses it (e.g., splitting `"nominate_2"` into `"nominate"` and `2`), and routes it to the corresponding pure state transition function in `game_state.py` (e.g., `nominate_chancellor(state, 2)`).

### Step 3: Implement `RandomBot`

Create the simplest possible implementation of the `Agent` protocol to serve as a baseline testing utility.
- Receives the `valid_actions` tuple.
- Uses a provided `Random` instance to select one `Action` uniformly at random.
- Returns the chosen `Action.id`.

---

## Implementation Order

```
1. Action dataclass + Agent Protocol           → verify: strict typing
2. get_legal_actions                           → verify: correct action menus per phase
3. apply_action (Router)                       → verify: correct routing and parsing
4. RandomBot implementation                    → verify: adheres to protocol
```

### Testing Strategy

Every new class and free function requires a corresponding test class following existing patterns.
- `get_legal_actions` must be exhaustively tested against various states to ensure it respects term limits, unlocked powers, and valid targets.
- `apply_action` must be tested to ensure it correctly maps IDs to state transitions, raising `InvalidMoveError` if given an impossible `action_id` or an action not currently in `get_legal_actions`.
- Immutability checks (`self.assert_pure_transition` / `self.assert_state_immutable`) must be strictly maintained across all tests.
