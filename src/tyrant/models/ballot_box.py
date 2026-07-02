from dataclasses import dataclass
from tyrant.models.enums import Vote, HIDDEN


@dataclass(frozen=True)
class BallotBox:
    votes: frozendict[int, Vote | HIDDEN] = frozendict()

    @property
    def vote_count(self) -> int:
        return len(self.votes)

    @property
    def result(self) -> Vote:
        ja_count = sum(1 for vote in self.votes.values() if vote == Vote.JA)
        return Vote.JA if ja_count > len(self.votes.values()) // 2 else Vote.NEIN


def submit_vote(box: BallotBox, uid: int, vote: Vote) -> BallotBox:
    return BallotBox(votes=box.votes | {uid: vote})
