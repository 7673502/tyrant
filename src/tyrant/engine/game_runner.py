import asyncio
from collections.abc import Awaitable, Mapping, Sequence
from dataclasses import fields
from random import Random
from typing import Final

from tyrant.engine.router import apply_action, get_legal_actions
from tyrant.exceptions import InvalidMoveError, TyrantError
from tyrant.models.action import Action
from tyrant.models.agent import Agent
from tyrant.models.enums import GamePhase, Role
from tyrant.models.game_state import GameState, create_game, scrub_state

AGENT_FILLED_FIELDS: Final = frozenset({"description", "message"})


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
        max_retries: int = 2,
        timeout: float | None = None,
    ):
        if initial_state is None:
            initial_state = create_game(
                uids=tuple(agent.uid for agent in agents),
                seed=seed,
                roles=roles,
                shuffle_players=shuffle_players,
                discussion_enabled=discussion_enabled,
            )
        self.state = initial_state
        self.agents = {agent.uid: agent for agent in agents}
        self.max_retries = max_retries
        self.timeout = timeout
        self.rng = Random(seed)

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

        return self.state

    async def _query_agent(
        self, agent: Agent, valid_actions: tuple[Action, ...]
    ) -> tuple[int, Action]:
        scrubbed_state = scrub_state(self.state, agent.uid)
        for _ in range(self.max_retries + 1):
            try:
                action = await self._attempt(agent, scrubbed_state, valid_actions)
                return agent.uid, action
            except Exception:
                pass
        return agent.uid, self.rng.choice(valid_actions)

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
