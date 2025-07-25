from dataclasses import dataclass

@dataclass(slots=True)
class User:
    id: int
    username: str
    email: str

UserId = int
