from dataclasses import dataclass
from typing import Final

FAILURES_UNTIL_TOP_DECK: Final = 3


@dataclass(frozen=True)
class ElectionTracker:
    """Counts consecutive failed elections.

    Attributes:
        failed_elections: Failed elections since the tracker last reset.
    """

    failed_elections: int = 0


def increment_election_tracker(
    tracker: ElectionTracker,
) -> tuple[ElectionTracker, bool]:
    """Records a failed election.

    Args:
        tracker: The current tracker.

    Returns:
        The new tracker and whether this failure triggers a top-deck. The count resets to 0 when it does.
    """
    new_failed_elections = (tracker.failed_elections + 1) % FAILURES_UNTIL_TOP_DECK
    return ElectionTracker(
        failed_elections=new_failed_elections
    ), new_failed_elections == 0
