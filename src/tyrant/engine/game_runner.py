import asyncio
import logging
from collections.abc import Awaitable, Mapping, Sequence
from dataclasses import fields
from random import Random
from typing import Final

from tyrant.engine.router import apply_action, get_legal_actions
from tyrant.exceptions import InvalidMoveError, TyrantError
from tyrant.models.action import Action
from tyrant.models.agent import Agent
from tyrant.models.agent_fault import AgentFault
from tyrant.models.enums import GamePhase, Role
from tyrant.models.game_state import GameState, create_game, scrub_state
from tyrant.models.replay import Replay, record_step

AGENT_FILLED_FIELDS: Final = frozenset({"description", "message"})

logger = logging.getLogger(__name__)


def _identity(action: Action) -> tuple:
    """Returns the action's field values, leaving out the fields an agent may fill in."""
    return tuple(
        getattr(action, f.name)
        for f in fields(action)
        if f.name not in AGENT_FILLED_FIELDS
    )


def _is_offered(action: Action, valid_actions: tuple[Action, ...]) -> bool:
    """Returns whether the action matches an offered action, ignoring agent-filled fields."""
    return any(
        type(action) is type(offered) and _identity(action) == _identity(offered)
        for offered in valid_actions
    )


class GameRunner:
    """Plays a game by asking agents for actions until it ends.

    Each iteration, every agent with legal actions is asked at the same time, with the state scrubbed for that agent. A failed attempt is retried, and after `max_retries` failed retries the runner plays a random legal action for the agent.

    Attributes:
        state: The current, unscrubbed game state.
        replay: Every action applied so far.
        agents: Each agent, keyed by UID.
        max_retries: Retries allowed after an agent's first failed attempt.
        timeout: Seconds allowed for each attempt, or `None` for no limit.
        rng: Random generator that picks fallback actions.
        faults: Every failed attempt, in order.
    """

    def __init__(
        self,
        agents: Sequence[Agent],
        initial_state: GameState | None = None,
        seed: int | None = None,
        roles: Mapping[int, Role] | None = None,
        shuffle_players: bool = True,
        discussion_enabled: bool = False,
        discussion_rounds: int = 2,
        max_retries: int = 2,
        timeout: float | None = 120.0,
    ):
        """Sets up the runner and, unless `initial_state` is given, a new game.

        Args:
            agents: The players. Each agent's `uid` becomes a player UID.
            initial_state: A state to start from instead of a new game.
            seed: Seed for the new game and for fallback actions, or `None` for random.
            roles: Fixed role for each UID, or `None` to deal roles at random.
            shuffle_players: Whether to shuffle the seating order.
            discussion_enabled: Whether to hold discussions.
            discussion_rounds: How many times the table goes around in each discussion.
            max_retries: Retries allowed after an agent's first failed attempt.
            timeout: Seconds allowed for each attempt, or `None` for no limit.

        Raises:
            TyrantError: If the settings are not valid for a new game.
        """
        if initial_state is None:
            initial_state = create_game(
                uids=tuple(agent.uid for agent in agents),
                seed=seed,
                roles=roles,
                shuffle_players=shuffle_players,
                discussion_enabled=discussion_enabled,
                discussion_rounds=discussion_rounds,
            )
        self.state = initial_state
        self.replay = Replay(initial_state=initial_state)
        self.agents = {agent.uid: agent for agent in agents}
        self.max_retries = max_retries
        self.timeout = timeout
        self.rng = Random(seed)
        self.faults: tuple[AgentFault, ...] = ()

    async def run(self) -> GameState:
        """Plays the game until it ends.

        Returns:
            The final, unscrubbed game state.

        Raises:
            TyrantError: If no player has a legal action.
        """
        while self.state.phase != GamePhase.GAME_OVER:
            await self._run_iteration()
        return self.state

    async def _run_iteration(self) -> GameState:
        """Asks every agent with legal actions at once and applies their choices in order."""
        pending_tasks: list[Awaitable[tuple[int, Action]]] = []

        for agent in self.agents.values():
            valid_actions = get_legal_actions(self.state, agent.uid)
            if valid_actions:
                pending_tasks.append(self._query_agent(agent, valid_actions))

        if not pending_tasks:
            raise TyrantError(
                f"Stalemate: No players have legal actions in phase {self.state.phase}."
            )

        fault_count = len(self.faults)
        results: list[tuple[int, Action]] = await asyncio.gather(*pending_tasks)
        fell_back = {f.uid for f in self.faults[fault_count:] if f.fell_back}

        for agent_uid, chosen_action in results:
            self.state = apply_action(self.state, chosen_action, agent_uid)
            self.replay = record_step(
                self.replay, agent_uid, chosen_action, agent_uid in fell_back
            )

        return self.state

    async def _query_agent(
        self, agent: Agent, valid_actions: tuple[Action, ...]
    ) -> tuple[int, Action]:
        """Asks an agent for an action, retrying on failure and falling back to a random legal action."""
        scrubbed_state = scrub_state(self.state, agent.uid)
        attempts = self.max_retries + 1
        for attempt in range(attempts):
            try:
                action = await self._attempt(agent, scrubbed_state, valid_actions)
                return agent.uid, action
            except Exception as e:
                self._record_fault(agent.uid, repr(e), attempt == attempts - 1)
        return agent.uid, self.rng.choice(valid_actions)

    def _record_fault(self, uid: int, reason: str, fell_back: bool) -> None:
        """Records and logs a failed attempt."""
        fault = AgentFault(
            uid=uid, phase=self.state.phase, reason=reason, fell_back=fell_back
        )
        self.faults = self.faults + (fault,)
        logger.warning(
            "Player %s failed in phase %s: %s%s",
            uid,
            fault.phase,
            reason,
            " (falling back to a random legal action)" if fell_back else "",
        )

    async def _attempt(
        self, agent: Agent, state: GameState, valid_actions: tuple[Action, ...]
    ) -> Action:
        """Makes one timed request to an agent and rejects an action that was not offered."""
        action = await asyncio.wait_for(
            agent.choose_action(state, valid_actions), self.timeout
        )
        if not _is_offered(action, valid_actions):
            raise InvalidMoveError(
                f"Player {agent.uid} chose an action that was not offered: {action}"
            )
        return action
