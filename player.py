from dataclasses import dataclass, field
from typing import List
from game_elements import Hero, Card

@dataclass
class Player:
    """代表一个玩家"""
    name: str
    hero: Hero
    hand: List[Card] = field(default_factory=list)
