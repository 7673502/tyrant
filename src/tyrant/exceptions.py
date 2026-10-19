class TyrantError(Exception):
    """Base class for errors raised by Tyrant."""

    pass


class InvalidMoveError(TyrantError):
    """Raised when an action is not legal in the current state.

    Attributes:
        reply: The agent's raw reply that was rejected, or `None` if there was none.
    """

    def __init__(self, message: str, reply: str | None = None):
        """Creates the error.

        Args:
            message: Why the action was rejected.
            reply: The agent's raw reply that was rejected, if any.
        """
        super().__init__(message)
        self.reply = reply


class AgentError(TyrantError):
    """Raised when an agent fails to choose an action for a reason it expected, such as a provider or network error."""

    pass


class UnsupportedReplayError(TyrantError):
    """Raised when a replay file uses a format this version of Tyrant does not read."""

    pass
