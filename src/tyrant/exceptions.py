class TyrantError(Exception):
    """Base class for errors raised by Tyrant."""

    pass


class InvalidMoveError(TyrantError):
    """Raised when an action is not legal in the current state."""

    pass


class AgentError(TyrantError):
    """Raised when an agent fails to choose an action for a reason it expected, such as a provider or network error."""

    pass
