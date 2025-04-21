from dataclasses import dataclass, field
from typing import List, Dict, Any

@dataclass
class AttributeSet:
    """存储基础属性，并支持加法用于应用影响"""
    attack: float = 0.0
    defense: float = 0.0
    support: float = 0.0

    def __add__(self, other):
        if isinstance(other, AttributeSet):
            return AttributeSet(
                attack=self.attack + other.attack,
                defense=self.defense + other.defense,
                support=self.support + other.support
            )
        return NotImplemented

@dataclass
class Card:
    """代表一张卡牌，属性和影响从外部加载"""
    name: str
    base_attributes: AttributeSet
    # 影响逻辑：此牌打出后可能对后续特定牌产生的属性修正
    # key: target_card_name, value: AttributeSet modifier
    influences: Dict[str, AttributeSet] = field(default_factory=dict)

# 技能类暂时保留结构，但本次不用
@dataclass
class Skill:
    """代表一个技能 (MVP中未使用)"""
    name: str
    attributes: AttributeSet
    is_active: bool = True
    influences: Dict[str, AttributeSet] = field(default_factory=dict)

@dataclass
class Hero:
    """代表一个武将 (简化版，无技能)"""
    name: str
    max_hp: int
    current_hp: int
    # skills: List[Skill] = field(default_factory=list) # 暂无技能

    def get_hp_ratio(self) -> float:
        """计算当前血量百分比"""
        return self.current_hp / self.max_hp if self.max_hp > 0 else 0

@dataclass
class Player:
    """代表一个玩家"""
    name: str
    hero: Hero
    hand: List[Card] = field(default_factory=list)

# --- 卡牌定义加载器 ---
# 这个字典将存储从数据库加载的卡牌原型
CARD_PROTOTYPES: Dict[str, Card] = {}

def load_card_prototypes(card_data_from_db: Dict[str, Any]):
    """使用从数据库加载的数据填充 CARD_PROTOTYPES"""
    global CARD_PROTOTYPES
    CARD_PROTOTYPES = {} # 清空旧数据
    for name, data in card_data_from_db.items():
        base_attrs = AttributeSet(**data['attributes'])
        influences_dict = {
            target_name: AttributeSet(**modifier)
            for target_name, modifier in data['influences'].items()
        }
        CARD_PROTOTYPES[name] = Card(
            name=name,
            base_attributes=base_attrs,
            influences=influences_dict
        )
    print(f"已创建 {len(CARD_PROTOTYPES)} 个卡牌原型。")

def get_card_instance(name: str) -> Card:
    """获取指定名称卡牌的一个实例 (浅拷贝)"""
    prototype = CARD_PROTOTYPES.get(name)
    if prototype:
        # 返回一个新的实例或原型本身，取决于是否需要修改实例状态
        # 对于MVP，直接返回原型可能足够，因为我们不在实例上修改状态
        return prototype
        # 或者 return dataclasses.replace(prototype) # 创建浅拷贝
    else:
        raise ValueError(f"未找到名为 '{name}' 的卡牌原型")

# 在 game_logic 或 main 中调用 load_card_prototypes
