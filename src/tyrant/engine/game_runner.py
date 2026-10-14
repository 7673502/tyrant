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
    return tuple(
        getattr(action, f.name)
        for f in fields(action)
        if f.name not in AGENT_FILLED_FIELDS
    )


def _is_offered(action: Action, valid_actions: tuple[Action, ...]) -> bool:
    return any(
        type(action) is type(offered) and _identity(action) == _identity(offered)
        for offered in valid_actions
    )


class GameRunner:
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
        while self.state.phase != GamePhase.GAME_OVER:
            await self._run_iteration()
        return self.state

    async def _run_iteration(self) -> GameState:
        pending_tasks: list[Awaitable[tuple[int, Action]]] = []

        for agent in self.agents.values():
            valid_actions = get_legal_actions(self.state, agent.uid)
            if valid_actions:
                pending_tasks.append(self._query_agent(agent, valid_actions))

        if not pending_tasks:
            raise TyrantError(
                f"Stalemate: No players have legal actions in phase {self.state.phase}."
            )

        results: list[tuple[int, Action]] = await asyncio.gather(*pending_tasks)

        for agent_uid, chosen_action in results:
            self.state = apply_action(self.state, chosen_action, agent_uid)
            self.replay = record_step(self.replay, agent_uid, chosen_action)

        return self.state

    async def _query_agent(
        self, agent: Agent, valid_actions: tuple[Action, ...]
    ) -> tuple[int, Action]:
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
        action = await asyncio.wait_for(
            agent.choose_action(state, valid_actions), self.timeout
        )
        if not _is_offered(action, valid_actions):
            raise InvalidMoveError(
                f"Player {agent.uid} chose an action that was not offered: {action}"
            )
        return action
