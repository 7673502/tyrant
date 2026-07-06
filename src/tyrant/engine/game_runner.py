import asyncio
from collections.abc import Awaitable, Sequence

from tyrant.engine.router import apply_action, get_legal_actions
from tyrant.exceptions import TyrantError
from tyrant.models.action import Action
from tyrant.models.agent import Agent
from tyrant.models.enums import GamePhase
from tyrant.models.game_state import GameState, create_game, scrub_state


class GameRunner:
    def __init__(
        self,
        agents: Sequence[Agent],
        initial_state: GameState | None = None,
        seed: int | None = None,
    ):
        if initial_state is None:
            initial_state = create_game(
                uids=tuple(agent.uid for agent in agents), seed=seed
            )
        self.state = initial_state
        self.agents = {agent.uid: agent for agent in agents}

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
        action = await agent.choose_action(scrubbed_state, valid_actions)
        return agent.uid, action
