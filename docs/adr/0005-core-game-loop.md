# ADR 5: Core Game Loop

## Context
We need an execution runner to drive the state machine forward. Secret Hitler has alternating phases: some are purely sequential (the President nominating), while others require simultaneous, hidden participation from all players at once (Voting).

## Decision
1. **Bouncer-Driven Polling**: Instead of tracking "whose turn it is" via complex pointers, the game loop uses an aggressive polling pattern. On each iteration, the loop iterates through all active players and queries `get_legal_actions(state, player_uid)`. If a player receives actions, they are prompted.
2. **State-Buffered Concurrency**: Simultaneous phases (like voting) are handled cleanly by the state mutators, not the loop. Votes are dropped into a hidden ballot box within the state, and the bouncer locks out players who have already voted. The loop continues to spin until the mutator detects the box is full and automatically advances the `GamePhase`.
3. **Pure Async Pipeline**: The entire game loop runner will be asynchronous (`asyncio`). Local bots (Random/Heuristic) will resolve instantly, while LLM bots will naturally await network API calls, allowing concurrent phases like voting to resolve efficiently.

## Implementation Details

### 1. Agent Protocol
Since the loop will be purely asynchronous, the agents must expose an `async` method for choosing actions. This provides a unified interface for both fast local bots and slow network-bound LLMs.

```python
from typing import Protocol
from tyrant.models.game_state import GameState
from tyrant.models.action import Action

class Agent(Protocol):
    @property
    def uid(self) -> int:
        ...
        
    async def choose_action(
        self, state: GameState, valid_actions: tuple[Action, ...]
    ) -> Action:
        ...
```

### 2. GameRunner Class
A class responsible for holding the current state, the agents, and driving the `asyncio` event loop.

```python
from tyrant.models.enums import GamePhase
from tyrant.models.game_state import GameState

class GameRunner:
    def __init__(self, initial_state: GameState, agents: list[Agent]):
        self.state = initial_state
        self.agents = {agent.uid: agent for agent in agents}

    async def run(self) -> GameState:
        """
        Runs the game loop until the game reaches the GAME_OVER phase.
        Returns the final GameState.
        """
        while self.state.phase != GamePhase.GAME_OVER:
            self.state = await self._run_iteration()
        return self.state
```

### 3. Iteration & Polling Logic
On each iteration, the loop polls every player using the router's `get_legal_actions`. It spawns asynchronous tasks for all players with valid actions. The first action to resolve is applied to the state, generating a new state, and the next iteration begins (which handles discarding any unapplied parallel tasks).

```python
    import asyncio
    from tyrant.exceptions import TyrantError
    from tyrant.engine.router import get_legal_actions, apply_action

    async def _run_iteration(self) -> GameState:
        pending_tasks = []
        
        for agent in self.agents.values():
            valid_actions = get_legal_actions(self.state, agent.uid)
            if valid_actions:
                pending_tasks.append(
                    self._query_agent(agent, self.state, valid_actions)
                )
        
        if not pending_tasks:
            raise TyrantError("Stalemate: No players have legal actions.")
            
        # Wait for EVERY valid actor to finish their thought
        results = await asyncio.gather(*pending_tasks)
        
        # Apply their chosen actions sequentially to the state
        for agent_uid, chosen_action in results:
            self.state = apply_action(self.state, chosen_action, agent_uid)
            
        return self.state
        
    async def _query_agent(
        self, agent: Agent, state: GameState, valid_actions: tuple[Action, ...]
    ) -> tuple[int, Action]:
        action = await agent.choose_action(state, valid_actions)
        return agent.uid, action
```

### 4. Execution Requirements
To implement this, the following steps are required:
1. **`src/tyrant/engine/agent.py`**: Define the `Agent` protocol interface.
2. **`src/tyrant/engine/game_runner.py`**: Implement the `GameRunner` class with the `run` and `_run_iteration` methods.
3. **Tests in `tests/engine/test_game_runner.py`**:
   - Create mock agents that resolve synchronously.
   - Create mock agents that use `asyncio.sleep` to simulate network delays. This will explicitly test concurrency (e.g. simulating concurrent voters).
   - Test that `apply_action` generates a new state on the first resolved vote, and the subsequent loop picks up the remaining voters correctly (as they will still have legal actions if the ballot box isn't full).
