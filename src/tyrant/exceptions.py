class TyrantError(Exception):
    """Base class for errors raised by Tyrant."""

    pass


class InvalidMoveError(TyrantError):
    """Raised when an action is not legal in the current state."""

    pass
