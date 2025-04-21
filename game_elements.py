from dataclasses import dataclass, field
from typing import List

@dataclass
class AttributeSet:
    """存储基础属性"""
    attack: float = 0.0
    defense: float = 0.0
    support: float = 0.0
    # MVP 简化：暂时不包含影响列表和权值
    # influence_list: List[str] = field(default_factory=list)
    # influence_weight: float = 0.0

@dataclass
class Card:
    """代表一张卡牌"""
    name: str
    attributes: AttributeSet

@dataclass
class Skill:
    """代表一个技能"""
    name: str
    attributes: AttributeSet
    is_active: bool = True # 默认是主动技能，可使用
    # MVP 简化：暂时不包含影响列表和权值

@dataclass
class Hero:
    """代表一个武将"""
    name: str
    max_hp: int
    current_hp: int
    skills: List[Skill] = field(default_factory=list)

    def get_hp_ratio(self) -> float:
        """计算当前血量百分比"""
        return self.current_hp / self.max_hp if self.max_hp > 0 else 0

# --- 示例卡牌和技能定义 ---
CARD_SHA = Card("杀", AttributeSet(attack=1.0))
CARD_SHAN = Card("闪", AttributeSet(defense=1.0))
CARD_TAO = Card("桃", AttributeSet(support=1.0)) # 假设桃的价值体现在support上

SKILL_DEFAULT_ACTIVE = Skill("默认主动技能", AttributeSet(attack=0.5), is_active=True)
SKILL_DEFAULT_PASSIVE = Skill("默认被动技能", AttributeSet(defense=0.2), is_active=False)
