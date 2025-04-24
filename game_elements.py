from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
import json # Import json for scope handling
from collections import defaultdict # Import defaultdict here

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

# 合并 Card 和 Skill 为 ActionEntity
@dataclass
class ActionEntity:
    """代表一个可执行的动作实体（卡牌或技能），包含状态信息"""
    name: str
    base_attributes: AttributeSet
    # 影响逻辑：此实体发动后可能对后续特定实体产生的属性修正
    # Key: target_entity_name, Value: List of tuples (AttributeSet modifier, required_scope)
    influences: Dict[str, List[Tuple[AttributeSet, Optional[int]]]] = field(default_factory=lambda: defaultdict(list)) # Changed value type
    # 新增状态属性
    timing: Optional[int] = None # 发动时机 (例如: 0=出牌阶段, 1=弃牌阶段, 2=判定阶段)
    response_suit: Optional[int] = None # 响应花色 (例如: 1=黑桃, 2=红桃, 3=梅花, 4=方块)
    response_rank_range: Optional[Tuple[int, int]] = None # 响应数字范围 (例如: (2, 9) 表示 2-9)
    scope: Optional[List[int]] = None # 新增: 可选作用域 (例如: [1, 2, 3] for 手牌, 装备, 判定)

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
    hand: List[ActionEntity] = field(default_factory=list) # 手牌现在是 ActionEntity 列表

# --- 实体定义加载器 ---
# 这个字典将存储从数据库加载的实体原型
ACTION_ENTITY_PROTOTYPES: Dict[str, ActionEntity] = {}

def load_action_entity_prototypes(entity_data_from_db: Dict[str, Any]):
    """使用从数据库加载的数据填充 ACTION_ENTITY_PROTOTYPES"""
    global ACTION_ENTITY_PROTOTYPES
    ACTION_ENTITY_PROTOTYPES = {} # 清空旧数据

    for name, data in entity_data_from_db.items():
        base_attrs = AttributeSet(**data['attributes'])

        # Rebuild influences structure: Dict[str, List[Tuple[AttributeSet, Optional[int]]]]
        influences_dict = defaultdict(list)
        for target_name, influence_list in data['influences'].items():
            for influence_data in influence_list:
                modifier = AttributeSet(**influence_data['modifier'])
                required_scope = influence_data.get('required_scope')
                influences_dict[target_name].append((modifier, required_scope))

        timing = data.get('timing')
        response_suit = data.get('response_suit')
        response_rank_start = data.get('response_rank_start')
        response_rank_end = data.get('response_rank_end')
        response_rank_range = None
        if response_rank_start is not None and response_rank_end is not None:
            response_rank_range = (response_rank_start, response_rank_end)

        # Load and parse scope from JSON string or keep as None
        scope_json = data.get('scope')
        scope = None
        if scope_json:
            try:
                scope = json.loads(scope_json)
                if not isinstance(scope, list):
                    print(f"Warning: Scope for '{name}' is not a list after JSON parsing: {scope}. Setting to None.")
                    scope = None
            except json.JSONDecodeError:
                print(f"Warning: Could not decode scope JSON for '{name}': {scope_json}. Setting to None.")
                scope = None

        ACTION_ENTITY_PROTOTYPES[name] = ActionEntity(
            name=name,
            base_attributes=base_attrs,
            influences=influences_dict,
            timing=timing,
            response_suit=response_suit,
            response_rank_range=response_rank_range,
            scope=scope # Assign loaded scope
        )
    print(f"已创建 {len(ACTION_ENTITY_PROTOTYPES)} 个动作实体原型。")

def get_action_entity_instance(name: str) -> ActionEntity:
    """获取指定名称动作实体的一个实例 (浅拷贝)"""
    prototype = ACTION_ENTITY_PROTOTYPES.get(name)
    if prototype:
        return prototype # MVP中直接返回原型
    else:
        raise ValueError(f"未找到名为 '{name}' 的动作实体原型")

# 在 game_logic 或 main 中调用 load_action_entity_prototypes
