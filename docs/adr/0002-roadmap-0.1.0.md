# Tyrant 0.1.0 Release Roadmap

This document outlines the complete roadmap for the `0.1.0` release of Tyrant: a Python package that implements the social-deduction game Secret Hitler with a focus on LLM compatibility and immutable state management.

---

## Phase 1: Core Domain Models
Establish the basic building blocks of the game using strictly immutable `@dataclass(frozen=True)` architectures.

- **Enums:** Define `Party`, `Role`, `PolicyTile`, `PresidentialPower`, `GamePhase`, and `Vote`.
- **Deck:** Draw pile, discard pile, and pure-functional shuffling logic utilizing a seedable `Random` instance.
- **Board:** Track enacted policies and determine active presidential powers.
- **BallotBox & ElectionTracker:** Immutable vote accumulation and failed election tracking.
- **Player:** UID, role, party, and alive status.

## Phase 2: GameState & Core Engine
Compose the core models into a single top-level state container and implement the pure-functional state transition engine.

- **GameState Dataclass:** A single container for the entire state of the game, including phase tracking, term limits, and `rng_state`.
- **State Transitions:** Pure-functional helpers that accept a `GameState` and return a new `GameState` (e.g., `nominate_chancellor`, `cast_vote`, `execute_player`).
- **Just-In-Time Shuffling:** Safely shuffle the deck only exactly when necessary to maintain deterministic reproducibility.
- **View Localization (`scrub_state`):** Redact hidden information from the state based on the requesting player's role, using a unified Python 3.15 `sentinel("HIDDEN")` type.
- **Immutability Testing:** Base test classes that enforce zero-mutation state transitions across all test cases.

## Phase 3: Custom Exception Hierarchy
Improve the developer and LLM experience by replacing generic `ValueError` exceptions with a rigid, catchable exception tree.

- **Base Error:** Create `TyrantError`.
- **Specific Error:** Create `InvalidMoveError`
- **Refactoring:** Update all state transition functions to raise these specific errors.

## Phase 4: Agent Protocol & Baseline Bots
Create the interface that all external players (AI or human) must implement to plug into the engine.

- **Agent Protocol:** Define a Python `Protocol` outlining required decision methods (e.g., `get_vote(state)`, `get_nomination(state)`).
- **RandomAgent:** Implement a bot that selects valid moves completely at random to serve as a baseline testing utility.

## Phase 5: Core Game Loop (`GameRunner`)
Build the orchestrator that sits on top of the state transitions and manages a live game between agents.

- **The Loop:** Initialize a state, check the phase, call `scrub_state` for the active player, request an action from their `Agent`, and apply the transition.
- **Error Recovery:** Catch specific `TyrantError`s if an agent makes an illegal move, allowing the engine to safely re-prompt the agent rather than crashing.
- **Game Over:** Detect win conditions and halt the loop.

## Phase 6: Advanced/Intelligent Agents
Validate the engine's localization by proving an agent can use the scrubbed state to deduce roles and formulate strategy.

- **Heuristic Bot:** A simple bot that follows basic Secret Hitler logic (e.g., Fascists always vote yes on Fascist chancellors).
- **MCTS Agent:** A Monte Carlo Tree Search agent to rigorously test game balance and engine speed.

## Phase 7: MCP Server Integration (0.1.0 Capstone)
Expose the finished engine, allowing external LLM clients to play over MCP.

- **FastMCP Implementation:** Create a server that exposes tool endpoints mapping to our transition functions.
- **Session Management:** Allow external clients to create games, join lobbies, and query their `scrubbed_state`.
- **LLM Instructions:** Provide system prompts/resources so external LLMs understand the game rules and how to invoke the tools.

