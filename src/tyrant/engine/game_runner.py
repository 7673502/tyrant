import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import fields
from random import Random

from frozendict import frozendict

from tyrant.engine.replay import fault_dict, replay_dict, result_dict, step_dict
from tyrant.engine.router import apply_action, get_legal_actions
from tyrant.exceptions import AgentError, InvalidMoveError, TyrantError
from tyrant.models.action import (
    AGENT_FILLED_FIELDS,
    Action,
    ClaimChancellorEnactAction,
    ClaimInvestigationAction,
    ClaimPolicyPeekAction,
    ClaimPresidentEnactAction,
    PassAction,
)
from tyrant.models.agent import Agent
from tyrant.models.agent_fault import AgentFault
from tyrant.models.enums import GamePhase, Role
from tyrant.models.game_state import GameState, create_game, scrub_state
from tyrant.models.replay import Replay, record_fault, record_step

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


def _profile(agent: Agent) -> frozendict[str, str]:
    """Returns the agent's class name as `type`, plus its `profile` if it has one."""
    return frozendict(type=type(agent).__name__, **getattr(agent, "profile", {}))


class GameRunner:
    """Plays a game by asking agents for actions until it ends.

    Each iteration, every agent with legal actions is asked at the same time, with the state scrubbed for that agent. An attempt that raises `InvalidMoveError`, `TimeoutError` or `AgentError` is retried, and after `max_retries` failed retries the runner plays a fallback action for the agent: a pass or a declined claim when one is offered, otherwise a random legal action. Any other exception ends the game.

    Attributes:
        state: The current, unscrubbed game state.
        replay: Every action applied so far, and every failed attempt.
        agents: Each agent, keyed by UID.
        max_retries: Retries allowed after an agent's first failed attempt.
        timeout: Seconds allowed for each attempt, or `None` for no limit.
        rng: Random generator that picks fallback actions when no pass is offered.
        faults: Every failed attempt, in order.
        on_update: Called with each live update message, or `None` for no updates.
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
        on_update: Callable[[dict], None] | None = None,
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
            on_update: Called with each live update message, or `None` for no updates. A `start` message holds the empty replay, each `step` and `fault` message holds one entry of the replay's `steps` or `faults`, and an `end` message holds the result.

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
        self.replay = Replay(
            initial_state=initial_state,
            agents=frozendict({agent.uid: _profile(agent) for agent in agents}),
        )
        self.agents = {agent.uid: agent for agent in agents}
        self.max_retries = max_retries
        self.timeout = timeout
        self.rng = Random(seed)
        self.faults: tuple[AgentFault, ...] = ()
        self.on_update = on_update

    async def run(self) -> GameState:
        """Plays the game until it ends.

        Returns:
            The final, unscrubbed game state.

        Raises:
            TyrantError: If no player has a legal action.
            Exception: Any exception an agent raises other than `InvalidMoveError`, `TimeoutError` or `AgentError`.
        """
        if self.on_update is not None:
            self.on_update({"type": "start", "replay": replay_dict(self.replay)})
        while self.state.phase != GamePhase.GAME_OVER:
            await self._run_iteration()
        if self.on_update is not None:
            self.on_update({"type": "end", "result": result_dict(self.state)})
        return self.state

    async def _run_iteration(self) -> GameState:
        """Asks every agent with legal actions at once and applies their choices in order."""
        pending_tasks: list[Awaitable[tuple[int, Action]]] = []

        for agent in self.agents.values():
            valid_actions = get_legal_actions(self.state, agent.uid)
            if valid_actions:
                step = len(self.replay.steps) + len(pending_tasks)
                pending_tasks.append(self._query_agent(agent, valid_actions, step))

        if not pending_tasks:
            raise TyrantError(
                f"Stalemate: No players have legal actions in phase {self.state.phase}."
            )

        fault_count = len(self.faults)
        results: list[tuple[int, Action]] = await asyncio.gather(*pending_tasks)
        fell_back = {f.uid for f in self.faults[fault_count:] if f.fell_back}

        for agent_uid, chosen_action in results:
            state = self.state
            self.state = apply_action(state, chosen_action, agent_uid)
            self.replay = record_step(
                self.replay,
                agent_uid,
                chosen_action,
                agent_uid in fell_back,
                getattr(self.agents[agent_uid], "notes", None),
            )
            if self.on_update is not None:
                index = len(self.replay.steps) - 1
                step = step_dict(index, self.replay.steps[index], state, self.state)
                self.on_update({"type": "step", "step": step})

        return self.state

    async def _query_agent(
        self, agent: Agent, valid_actions: tuple[Action, ...], step: int
    ) -> tuple[int, Action]:
        """Asks an agent for an action, retrying on failure and then falling back; faults are recorded against `step`."""
        scrubbed_state = scrub_state(self.state, agent.uid)
        attempts = self.max_retries + 1
        for attempt in range(attempts):
            try:
                action = await self._attempt(agent, scrubbed_state, valid_actions)
                return agent.uid, action
            except (InvalidMoveError, TimeoutError, AgentError) as e:
                self._record_fault(
                    agent.uid,
                    repr(e),
                    attempt == attempts - 1,
                    step,
                    e.reply if isinstance(e, InvalidMoveError) else None,
                )
        return agent.uid, self._fallback(valid_actions)

    def _fallback(self, valid_actions: tuple[Action, ...]) -> Action:
        """Returns the offered pass or declined claim, or a random legal action when neither is offered."""
        for action in valid_actions:
            match action:
                case (
                    PassAction()
                    | ClaimPresidentEnactAction(claim_policies=None)
                    | ClaimChancellorEnactAction(claim_policies=None)
                    | ClaimPolicyPeekAction(claim_policies=None)
                    | ClaimInvestigationAction(claim_party=None)
                ):
                    return action
        return self.rng.choice(valid_actions)

    def _record_fault(
        self, uid: int, reason: str, fell_back: bool, step: int, reply: str | None
    ) -> None:
        """Records a failed attempt in `faults` and the replay, and logs it."""
        fault = AgentFault(
            uid=uid,
            phase=self.state.phase,
            reason=reason,
            fell_back=fell_back,
            step=step,
            reply=reply,
        )
        self.faults = self.faults + (fault,)
        self.replay = record_fault(self.replay, fault)
        if self.on_update is not None:
            self.on_update({"type": "fault", "fault": fault_dict(fault)})
        logger.warning(
            "Player %s failed in phase %s: %s%s",
            uid,
            fault.phase,
            reason,
            " (falling back to a pass, a declined claim or a random legal action)"
            if fell_back
            else "",
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
