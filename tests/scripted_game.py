from tyrant.engine.router import apply_action, get_legal_actions
from tyrant.models.enums import GamePhase
from tyrant.models.game_state import GameState


def play_first_legal_actions(state: GameState) -> tuple[GameState, ...]:
    """Plays the first legal action of the first player able to act until the game ends."""
    states = [state]
    while state.phase != GamePhase.GAME_OVER:
        uid, action = next(
            (p.uid, get_legal_actions(state, p.uid)[0])
            for p in state.players
            if get_legal_actions(state, p.uid)
        )
        state = apply_action(state, action, uid)
        states.append(state)
    return tuple(states)
