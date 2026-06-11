from tyrant.models.enums import Vote

class BallotBox:
    def __init__(self):
        self.votes = {}

    def submit_vote(self, uid: int, vote: Vote):
        self.votes[uid] = vote

    def vote_count(self) -> int:
        return len(self.votes)
    
    def get_result(self) -> Vote:
        ja_count = list(self.votes.values()).count(Vote.JA)

        return Vote.JA if ja_count > len(self.votes.values()) // 2 else Vote.NEIN

