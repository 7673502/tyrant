import asyncio
from random import Random

from tyrant.ismcts.beliefs import role_assignments, role_weights
from tyrant.ismcts.claims import claim_action
from tyrant.ismcts.search import CLAIM_PHASES, search
from tyrant.models.action import Action, PassAction
from tyrant.models.enums import GamePhase
from tyrant.models.game_state import GameState


class ISMCTSAgent:
    """An agent that chooses by information set Monte Carlo tree search over sampled role deals.

    It weighs role deals by how well they explain the public events, searches its decisions in a worker thread, makes claims with a simple heuristic and always passes in discussions.

    This agent is experimental: it beats `BiasedRandomAgent` but is not a strong player, and its belief model and likelihoods may change. Measure changes with `benchmarks.ismcts_win_rate`.

    Attributes:
        uid: The player's unique ID.
        iterations: Search iterations per decision.
        exploration: The UCB exploration constant.
        rng: Random generator for the search.
        profile: The iteration count, shown in replays.
    """

    def __init__(
        self,
        uid: int,
        iterations: int = 1000,
        exploration: float = 0.7,
        seed: int | None = None,
    ):
        """Creates the agent.

        Args:
            uid: The player's unique ID.
            iterations: Search iterations per decision, at least 1.
            exploration: The UCB exploration constant.
            seed: Seed for the search, or `None` for random play.
        """
        self.uid = uid
        self.iterations = iterations
        self.exploration = exploration
        self.rng = Random(seed)
        self.profile = {"iterations": str(iterations)}

    async def choose_action(
        self, state: GameState, valid_actions: tuple[Action, ...]
    ) -> Action:
        """Returns the only offered action, a pass, a heuristic claim or the search's choice.

        Args:
            state: The game state, scrubbed for this agent.
            valid_actions: The actions this agent may take now.

        Returns:
            One of `valid_actions`.
        """
        if len(valid_actions) == 1:
            return valid_actions[0]
        if state.phase == GamePhase.DISCUSSION:
            return next(a for a in valid_actions if isinstance(a, PassAction))
        if state.phase in CLAIM_PHASES:
            return claim_action(state, self.uid, valid_actions)

        return await asyncio.to_thread(self._search, state)

    def _search(self, state: GameState) -> Action:
        """Weighs the role deals that fit the state and searches for the agent's action."""
        assignments = role_assignments(state, self.uid)
        return search(
            state,
            self.uid,
            assignments,
            role_weights(state, assignments),
            self.iterations,
            self.exploration,
            self.rng,
        )
