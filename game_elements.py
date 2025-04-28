from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple, Union # Add Union
import json
from collections import defaultdict
import torch # Import torch

# --- Global variable to hold learnable weights ---
# Structure will be defined and populated in training.py
# Example: Dict[source_name, Dict[target_name, Dict[scope_key, Dict[attr_name, tensor]]]]
influence_weights: Optional[torch.nn.ParameterDict] = None # Placeholder

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
        # Allow adding a tensor-based AttributeSet (for gradients)
        elif isinstance(other, TensorAttributeSet):
             # Convert self to tensor before adding
             return TensorAttributeSet(
                 attack=torch.tensor(self.attack, dtype=torch.float32) + other.attack,
                 defense=torch.tensor(self.defense, dtype=torch.float32) + other.defense,
                 support=torch.tensor(self.support, dtype=torch.float32) + other.support,
             )
        return NotImplemented

    # Ensure addition works the other way around too
    def __radd__(self, other):
        # If other is 0 (like in sum()), return self
        if other == 0:
            return self
        else:
            return self.__add__(other)


@dataclass
class TensorAttributeSet:
    """AttributeSet using PyTorch tensors for gradient tracking."""
    attack: torch.Tensor = field(default_factory=lambda: torch.tensor(0.0, dtype=torch.float32))
    defense: torch.Tensor = field(default_factory=lambda: torch.tensor(0.0, dtype=torch.float32))
    support: torch.Tensor = field(default_factory=lambda: torch.tensor(0.0, dtype=torch.float32))

    def __add__(self, other):
         # Add another TensorAttributeSet
        if isinstance(other, TensorAttributeSet):
            return TensorAttributeSet(
                attack=self.attack + other.attack,
                defense=self.defense + other.defense,
                support=self.support + other.support
            )
        # Add a regular AttributeSet (convert it to tensor)
        elif isinstance(other, AttributeSet):
             return TensorAttributeSet(
                attack=self.attack + torch.tensor(other.attack, dtype=torch.float32),
                defense=self.defense + torch.tensor(other.defense, dtype=torch.float32),
                support=self.support + torch.tensor(other.support, dtype=torch.float32),
            )
        return NotImplemented

    # Ensure addition works the other way around too
    def __radd__(self, other):
         if other == 0: # Handle sum() starting with 0
             return self
         else:
             # Rely on the __add__ method of the other object if it's not TensorAttributeSet or AttributeSet
             # Or implement specific handling if needed
             return self.__add__(other)


# ActionEntity now describes potential influences, not their learned values
@dataclass
class ActionEntity:
    """代表一个可执行的动作实体（卡牌或技能），包含状态信息和潜在影响关系"""
    name: str
    base_attributes: AttributeSet
    # 潜在影响: 指明此实体 *可能* 影响哪些目标实体，以及所需的作用域
    # Key: target_entity_name, Value: List of required_scopes (int or None)
    # Example: {'杀': [1], '顺手牵羊': [2]} for '过河拆桥'
    potential_influences: Dict[str, List[Optional[int]]] = field(default_factory=lambda: defaultdict(list))
    timing: Optional[int] = None
    response_suit: Optional[int] = None
    response_rank_range: Optional[Tuple[int, int]] = None
    scope: Optional[List[int]] = None # 可选作用域

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
ACTION_ENTITY_PROTOTYPES: Dict[str, ActionEntity] = {}

def load_action_entity_prototypes(entity_data_from_db: Dict[str, Any]):
    """使用从数据库加载的数据填充 ACTION_ENTITY_PROTOTYPES，构建潜在影响关系"""
    global ACTION_ENTITY_PROTOTYPES
    ACTION_ENTITY_PROTOTYPES = {} # 清空旧数据

    for name, data in entity_data_from_db.items():
        base_attrs = AttributeSet(**data['attributes'])

        # Build potential influences dict directly from loaded data
        # The loaded data structure from modified database.py matches this
        potential_influences_dict = data.get('potential_influences', defaultdict(list))

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
            potential_influences=potential_influences_dict, # Assign the loaded relationships
            timing=timing,
            response_suit=response_suit,
            response_rank_range=response_rank_range,
            scope=scope # Assign loaded scope
        )
    print(f"已创建 {len(ACTION_ENTITY_PROTOTYPES)} 个动作实体原型 (含潜在影响关系)。")

def get_action_entity_instance(name: str) -> ActionEntity:
    """获取指定名称动作实体的一个实例 (当前直接返回原型)"""
    prototype = ACTION_ENTITY_PROTOTYPES.get(name)
    if prototype:
        # For now, return prototype directly. If ActionEntity instances needed state,
        # a copy mechanism (e.g., copy.deepcopy) might be required here.
        return prototype
    else:
        raise ValueError(f"未找到名为 '{name}' 的动作实体原型")

# No need to load prototypes here; main.py will handle initialization
