class ElectionTracker:
    def __init__(self):
        self.failed_elections = 0

    def increment(self) -> bool:
        self.failed_elections = (self.failed_elections + 1) % 3
        return self.failed_elections == 0

