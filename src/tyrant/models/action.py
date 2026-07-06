from dataclasses import dataclass


@dataclass(frozen=True)
class Action:
    id: str
    description: str
