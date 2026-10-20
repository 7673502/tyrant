import math
from dataclasses import fields
from random import Random
from typing import Final

from frozendict import frozendict

from tyrant.engine.router import apply_action, get_legal_actions
from tyrant.ismcts.determinize import determinize
from tyrant.models.action import (
    AGENT_FILLED_FIELDS,
    Action,
    ChancellorEnactAction,
    ClaimChancellorEnactAction,
    ClaimInvestigationAction,
    ClaimPolicyPeekAction,
    ClaimPresidentEnactAction,
    PresidentDiscardAction,
    VoteAction,
)
from tyrant.models.enums import GamePhase, Party, PolicyTile, Role, Vote
from tyrant.models.game_state import GameState

CLAIM_PHASES: Final = frozenset(
    {
        GamePhase.CLAIM_POLICIES,
        GamePhase.CLAIM_INVESTIGATION,
        GamePhase.CLAIM_POLICY_PEEK,
    }
)
"""The phases in which the search declines to claim, since claims never change the game's mechanics."""


class _Node:
    """A node of the search tree, reached by a sequence of public observations.

    It is mutable scratch space that never leaves `search`.

    Attributes:
        children: Each child, keyed by the acting player's UID and the events their action added.
        edges: The visits, total reward and availability of each action, keyed by the actor's private view and the action.
    """

    __slots__ = ("children", "edges")

    def __init__(self):
        """Creates an empty node."""
        self.children: dict[tuple, _Node] = {}
        self.edges: dict[tuple, list] = {}


def search(
    state: GameState,
    viewer_uid: int,
    assignments: tuple[frozendict[int, Role], ...],
    weights: tuple[float, ...],
    iterations: int,
    exploration: float,
    rng: Random,
) -> Action:
    """Chooses the viewer's action by information set Monte Carlo tree search.

    Each iteration samples a role deal by weight, determinizes the state, descends the tree with UCB, expands one action and finishes the game with a biased random rollout. Each player's edges are keyed by that player's sampled role and hand, so opponents choose as the player they are in each determinization.

    Args:
        state: The game state, scrubbed for the viewer.
        viewer_uid: UID of the player choosing an action.
        assignments: The role deals that fit the viewer's knowledge.
        weights: The weight of each deal.
        iterations: How many iterations to run, at least 1.
        exploration: The UCB exploration constant.
        rng: Random generator for deals, determinizations and rollouts.

    Returns:
        The viewer's most visited action, one of `get_legal_actions(state, viewer_uid)`.
    """
    root = _Node()
    for _ in range(iterations):
        roles = rng.choices(assignments, weights)[0]
        determinized = determinize(state, viewer_uid, roles, rng)
        info = _info_key(determinized, viewer_uid)
        _iterate(root, determinized, viewer_uid, exploration, rng)

    options = _options(state, get_legal_actions(state, viewer_uid))
    best = max(options, key=lambda key: root.edges.get((info, key), (0,))[0])
    return options[best]


def _iterate(
    root: _Node, state: GameState, viewer_uid: int, exploration: float, rng: Random
) -> None:
    """Runs one iteration on a determinized state, from the viewer's decision to the end of the game."""
    node = root
    path = []
    uid, actions = viewer_uid, get_legal_actions(state, viewer_uid)
    expanded = False
    while state.phase != GamePhase.GAME_OVER and not expanded:
        if state.phase in CLAIM_PHASES:
            action = _decline(actions)
        else:
            info = _info_key(state, uid)
            options = _options(state, actions)
            untried = []
            for key in options:
                edge = node.edges.get((info, key))
                if edge is None:
                    untried.append(key)
                else:
                    edge[2] += 1
            if untried:
                key = rng.choice(untried)
                node.edges[(info, key)] = [0, 0.0, 1]
                expanded = True
            else:
                key = max(
                    options, key=lambda k: _ucb(node.edges[(info, k)], exploration)
                )
            path.append((node.edges[(info, key)], uid))
            action = options[key]

        event_count = len(state.events)
        state = apply_action(state, action, uid)
        child_key = (uid, state.events[event_count:])
        child = node.children.get(child_key)
        if child is None:
            child = node.children[child_key] = _Node()
        node = child
        if state.phase != GamePhase.GAME_OVER:
            uid, actions = _turn(state)

    state = _rollout(state, rng)
    parties = {p.uid: p.party for p in state.players}
    for edge, actor in path:
        edge[0] += 1
        edge[1] += parties[actor] is state.winner


def _ucb(edge: list, exploration: float) -> float:
    """Returns an edge's mean reward plus its exploration bonus, counting only the visits in which it was available."""
    visits, reward, available = edge
    return reward / visits + exploration * math.sqrt(math.log(available) / visits)


def _turn(state: GameState) -> tuple[int, tuple[Action, ...]]:
    """Returns the first living player in seat order who has legal actions, and those actions."""
    return next(
        (p.uid, actions)
        for p in state.players
        if (actions := get_legal_actions(state, p.uid))
    )


def _info_key(state: GameState, uid: int) -> tuple:
    """Returns what the player knows privately when choosing: their role, and their sorted hand when they hold one."""
    role = next(p.role for p in state.players if p.uid == uid)
    president_uid = state.players[state.president_index].uid
    holds_hand = (
        state.phase in (GamePhase.PRESIDENT_DISCARD, GamePhase.PRESIDENT_VETO_RESPONSE)
        and uid == president_uid
    ) or (state.phase == GamePhase.CHANCELLOR_ENACT and uid == state.chancellor)
    return role, tuple(sorted(state.drawn_policies)) if holds_hand else ()


def _options(state: GameState, actions: tuple[Action, ...]) -> dict[tuple, Action]:
    """Maps each distinct action key to the first action with that key."""
    options: dict[tuple, Action] = {}
    for action in actions:
        options.setdefault(_action_key(state, action), action)
    return options


def _action_key(state: GameState, action: Action) -> tuple:
    """Returns what an action does: the policy for a discard or an enactment, otherwise its type and field values without the agent-filled fields."""
    match action:
        case PresidentDiscardAction(target_index=index):
            return "discard", state.drawn_policies[index]
        case ChancellorEnactAction(target_index=index):
            return "enact", state.drawn_policies[index]
    return (type(action),) + tuple(
        getattr(action, f.name)
        for f in fields(action)
        if f.name not in AGENT_FILLED_FIELDS
    )


def _decline(actions: tuple[Action, ...]) -> Action:
    """Returns the offered claim that declines to share."""
    return next(a for a in actions if _is_decline(a))


def _is_decline(action: Action) -> bool:
    """Returns whether the action is a claim that declines to share."""
    match action:
        case (
            ClaimPresidentEnactAction(claim_policies=None)
            | ClaimChancellorEnactAction(claim_policies=None)
            | ClaimPolicyPeekAction(claim_policies=None)
            | ClaimInvestigationAction(claim_party=None)
        ):
            return True
    return False


def _rollout(state: GameState, rng: Random) -> GameState:
    """Plays the game to the end with every player favoring their own party as `BiasedRandomAgent` does and declining every claim."""
    while state.phase != GamePhase.GAME_OVER:
        uid, actions = _turn(state)
        state = apply_action(state, _rollout_action(state, uid, actions, rng), uid)
    return state


def _rollout_action(
    state: GameState, uid: int, actions: tuple[Action, ...], rng: Random
) -> Action:
    """Returns the rollout policy's action: discard the other party's policy, enact your own, vote ja, decline claims, and otherwise choose at random."""
    if state.phase in CLAIM_PHASES:
        return _decline(actions)
    party = next(p.party for p in state.players if p.uid == uid)
    own = PolicyTile.LIBERAL if party is Party.LIBERAL else PolicyTile.FASCIST
    for action in actions:
        match action:
            case PresidentDiscardAction(target_index=index):
                if state.drawn_policies[index] != own:
                    return action
            case ChancellorEnactAction(target_index=index):
                if state.drawn_policies[index] == own:
                    return action
            case VoteAction(vote=Vote.JA):
                return action
    return rng.choice(actions)
