import itertools
from typing import List, Tuple, Union, Dict, DefaultDict, Optional
from collections import defaultdict
from game_elements import ActionEntity, AttributeSet, Player, Hero, load_action_entity_prototypes, get_action_entity_instance
from database import load_entities_from_db

# --- 全局实体定义 (从数据库加载) ---
try:
    print("正在从数据库加载实体数据...")
    all_entity_data = load_entities_from_db()
    load_action_entity_prototypes(all_entity_data)
except Exception as e:
    print(f"错误：无法从数据库加载实体数据！请确保数据库已初始化。错误：{e}")
    # exit()

# --- 初始牌堆定义 (用于概率模型) ---
INITIAL_DECK_COMPOSITION = {
    "杀": 15,
    "过河拆桥": 5,
    "顺手牵羊": 5,
    "闪": 10,
    "桃": 5,
    "闪电": 1, # 添加闪电到概率模型
}

# --- 概率模型 ---
def estimate_opponent_hand_probabilities(
    known_entities: List[str], # 更新参数名
    opponent_hand_size: int,
    initial_deck: Dict[str, int] = INITIAL_DECK_COMPOSITION
) -> Dict[str, float]:
    """
    根据已知实体和对手手牌数，估计对手手牌中各种实体的概率
    """
    remaining_deck = initial_deck.copy()
    for entity_name in known_entities: # 更新变量名
        if entity_name in remaining_deck and remaining_deck[entity_name] > 0:
            remaining_deck[entity_name] -= 1

    total_remaining_cards = sum(remaining_deck.values())
    probabilities = defaultdict(float)

    if total_remaining_cards <= 0 or opponent_hand_size <= 0:
        return dict(probabilities)

    for entity_name, count in remaining_deck.items(): # 更新变量名
        if count > 0:
            proportion = count / total_remaining_cards
            probabilities[entity_name] = proportion

    return dict(probabilities)

# --- 权重计算 ---
def calculate_weights(player_hp_ratio: float, opponent_hp_ratio: float) -> Dict[str, float]:
    """根据双方血量计算属性权重"""
    attack_weight = 1.0 + (1.0 - opponent_hp_ratio) # 敌方血少，攻击权重高
    defense_weight = 1.0 + (1.0 - player_hp_ratio)   # 己方血少，防御权重高
    support_weight = 1.0 # 辅助权重暂时固定
    return {"attack": attack_weight, "defense": defense_weight, "support": support_weight}

# --- 行动评估 (考虑影响) ---
# 更新签名以包含 chosen_scope (即使当前未使用)
def evaluate_action(
    action: ActionEntity,
    weights: Dict[str, float],
    active_influence_modifier: AttributeSet = AttributeSet(),
    chosen_scope: Optional[int] = None # 新增参数
) -> float:
    """评估单个行动的价值，应用传入的影响修改"""
    # 注意：当前评估逻辑不直接使用 action.scope 或 chosen_scope
    # Scope 主要影响 find_best_sequence 中的影响应用
    effective_attributes = action.base_attributes + active_influence_modifier
    score = (effective_attributes.attack * weights.get("attack", 1.0) +
             effective_attributes.defense * weights.get("defense", 1.0) +
             effective_attributes.support * weights.get("support", 1.0))
    return score

# --- 最佳序列查找 (评估不同作用域) ---
def find_best_sequence(
    player: Player,
    opponent: Player
) -> Tuple[List[Tuple[ActionEntity, Optional[int]]], float]: # 返回值变为 (动作选择列表, 分数)
    """
    查找当前玩家的最佳行动顺序，考虑实体之间的影响及其作用域要求。
    会评估具有不同可选作用域的动作的各种选择。
    注意：这会显著增加计算复杂度。
    """
    weights = calculate_weights(player.hero.get_hp_ratio(), opponent.hero.get_hp_ratio())

    # 1. 生成所有可能的 "动作选择" (实体, 选定作用域)
    possible_action_choices: List[Tuple[ActionEntity, Optional[int]]] = []
    for entity in player.hand:
        if entity.scope:
            for scope_option in entity.scope:
                possible_action_choices.append((entity, scope_option))
        else:
            # 没有可选作用域的动作
            possible_action_choices.append((entity, None))

    best_sequence_choices: List[Tuple[ActionEntity, Optional[int]]] = []
    max_score = -float('inf')

    # 2. 对 "动作选择" 进行排列组合
    # 遍历所有可能的序列长度 k
    for k in range(len(possible_action_choices) + 1):
        # 遍历长度为 k 的所有排列
        for sequence_tuple in itertools.permutations(possible_action_choices, k):
            current_sequence_choices = list(sequence_tuple)
            current_total_score = 0.0
            # 存储每个位置生效的影响修改器
            influences_in_sequence: Dict[int, AttributeSet] = defaultdict(AttributeSet)

            # 第一遍：计算影响 (基于选定的作用域)
            for i, (action_i, chosen_scope_i) in enumerate(current_sequence_choices):
                if action_i.influences:
                    # 遍历 action_i 能影响的目标实体名称
                    for target_entity_name, influence_rules in action_i.influences.items():
                        # 遍历该目标实体的所有影响规则 (modifier, required_scope)
                        for modifier, required_scope in influence_rules:
                            # 检查影响是否适用于当前动作选择的作用域
                            if required_scope is None or required_scope == chosen_scope_i:
                                # 查找序列中 action_i 之后出现的第一个 target_entity_name
                                for j in range(i + 1, len(current_sequence_choices)):
                                    action_j, _ = current_sequence_choices[j] # 获取下一个动作的实体
                                    if action_j.name == target_entity_name:
                                        # 将影响累加到 action_j 的位置上
                                        influences_in_sequence[j] += modifier
                                        # 假设一个影响规则只作用于后续第一个匹配的牌 (简化)
                                        break # 处理完这个 target_entity_name 的这个规则，继续下一个规则或目标

            # 第二遍：评估序列的总分，应用计算出的影响
            for i, (action, chosen_scope) in enumerate(current_sequence_choices):
                modifier_for_this_action = influences_in_sequence[i]
                # 将 chosen_scope 传递给评估函数
                action_score = evaluate_action(action, weights, modifier_for_this_action, chosen_scope)
                current_total_score += action_score

            # 更新最佳序列
            if current_total_score > max_score:
                max_score = current_total_score
                best_sequence_choices = current_sequence_choices

    return best_sequence_choices, max_score
