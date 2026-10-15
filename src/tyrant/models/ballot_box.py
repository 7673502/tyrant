from dataclasses import dataclass

from frozendict import frozendict
from tyrant.models.enums import Vote, HIDDEN


@dataclass(frozen=True)
class BallotBox:
    """The votes cast in the current election.

    Attributes:
        votes: Each voter's UID mapped to their vote, or to `HIDDEN` in a scrubbed state.
    """

    votes: frozendict[int, Vote | HIDDEN] = frozendict()

    @property
    def vote_count(self) -> int:
        """The number of votes cast so far."""
        return len(self.votes)

    @property
    def result(self) -> Vote:
        """`Vote.JA` if a strict majority of the votes cast are ja, otherwise `Vote.NEIN`."""
        ja_count = sum(1 for vote in self.votes.values() if vote == Vote.JA)
        return Vote.JA if ja_count > len(self.votes.values()) // 2 else Vote.NEIN


def submit_vote(box: BallotBox, uid: int, vote: Vote) -> BallotBox:
    """Records a player's vote.

    Args:
        box: The current ballot box.
        uid: UID of the voter.
        vote: The vote cast.

    Returns:
        A new ballot box that includes the vote.
    """
    return BallotBox(votes=box.votes | {uid: vote})
