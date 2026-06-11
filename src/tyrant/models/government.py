from dataclasses import dataclass

@dataclass
class Government:
    chancellor_uid: int
    president_uid: int
    elected: bool = False

