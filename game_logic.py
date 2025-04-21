import itertools
from typing import List, Tuple, Union, Dict, DefaultDict, Optional
from collections import defaultdict
from game_elements import Card, Skill, AttributeSet, Player, Hero, load_card_prototypes, get_card_instance
from database import load_cards_from_db

# --- 全局卡牌定义 (从数据库加载) ---
# 在模块加载时或初始化时加载卡牌数据
try:
    print("正在从数据库加载卡牌数据...")
    all_card_data = load_cards_from_db()
    load_card_prototypes(all_card_data)
except Exception as e:
    print(f"错误：无法从数据库加载卡牌数据！请确保数据库已初始化。错误：{e}")
    # 可以选择退出或使用默认值
    # exit()

# --- 初始牌堆定义 (用于概率模型) ---
# 假设一个标准的小型牌堆
INITIAL_DECK_COMPOSITION = {
    "杀": 15,
    "过河拆桥": 5,
    # 可以添加其他牌用于更真实的概率计算，即使它们不在当前手牌中
    "闪": 10,
    "桃": 5,
}

# --- 概率模型 ---
def estimate_opponent_hand_probabilities(
    known_cards: List[str], # 包括己方手牌、已打出、已弃置的牌
    opponent_hand_size: int,
    initial_deck: Dict[str, int] = INITIAL_DECK_COMPOSITION
) -> Dict[str, float]:
    """
    根据已知牌和对手手牌数，估计对手手牌中各种牌的概率
    """
    remaining_deck = initial_deck.copy()
    # 移除已知牌
    for card_name in known_cards:
        if card_name in remaining_deck and remaining_deck[card_name] > 0:
            remaining_deck[card_name] -= 1

    total_remaining_cards = sum(remaining_deck.values())
    probabilities = defaultdict(float)

    if total_remaining_cards <= 0 or opponent_hand_size <= 0:
        return dict(probabilities)

    # 计算剩余牌堆中每张牌的比例
    for card_name, count in remaining_deck.items():
        if count > 0:
            proportion = count / total_remaining_cards
            # 简化估计：直接使用比例作为概率代表
            probabilities[card_name] = proportion

    return dict(probabilities)

# --- 权重计算 ---
def calculate_weights(player_hp_ratio: float, opponent_hp_ratio: float) -> Dict[str, float]:
    """根据双方血量计算属性权重"""
    attack_weight = 1.0 + (1.0 - opponent_hp_ratio) # 敌方血少，攻击权重高
    defense_weight = 1.0 + (1.0 - player_hp_ratio)   # 己方血少，防御权重高
    support_weight = 1.0 # 辅助权重暂时固定
    return {"attack": attack_weight, "defense": defense_weight, "support": support_weight}

# --- 行动评估 (考虑影响) ---
def evaluate_action(
    action: Union[Card, Skill], # MVP中只有Card
    weights: Dict[str, float],
    active_influence_modifier: AttributeSet = AttributeSet() # 从序列中传递过来的影响修改
) -> float:
    """评估单个行动的价值，应用传入的影响修改"""
    if isinstance(action, Card): # 简化：只处理卡牌
        # 应用来自序列中先前行动的影响
        effective_attributes = action.base_attributes + active_influence_modifier

        score = (effective_attributes.attack * weights.get("attack", 1.0) +
                 effective_attributes.defense * weights.get("defense", 1.0) +
                 effective_attributes.support * weights.get("support", 1.0))
        return score
    # elif isinstance(action, Skill): ... # 将来可以添加技能评估
    return 0.0

# --- 最佳序列查找 (实现影响逻辑) ---
def find_best_sequence(
    player: Player,
    opponent: Player
) -> Tuple[List[Card], float]: # 返回最佳序列和其得分
    """
    查找当前玩家的最佳出牌顺序，考虑牌之间的影响
    """
    possible_actions: List[Card] = player.hand # MVP中只有手牌

    weights = calculate_weights(player.hero.get_hp_ratio(), opponent.hero.get_hp_ratio())

    best_sequence: List[Card] = []
    max_score = -float('inf')

    # 遍历所有可能的出牌排列组合 (包括不同长度的子序列)
    for k in range(len(possible_actions) + 1):
        for sequence_tuple in itertools.permutations(possible_actions, k):
            current_sequence = list(sequence_tuple)
            current_total_score = 0.0
            # 存储当前序列中，每个位置生效的影响修改器
            # key: index in sequence, value: AttributeSet modifier for that action
            influences_in_sequence: Dict[int, AttributeSet] = defaultdict(AttributeSet)

            # 第一遍：计算每个动作会对其后动作施加的影响
            for i, action_i in enumerate(current_sequence):
                # 检查 action_i 是否有影响
                if isinstance(action_i, Card) and action_i.influences:
                    # 遍历 action_i 能影响的目标
                    for target_card_name, modifier in action_i.influences.items():
                        # 查找序列中 action_i 之后出现的第一个 target_card_name
                        for j in range(i + 1, len(current_sequence)):
                            action_j = current_sequence[j]
                            if isinstance(action_j, Card) and action_j.name == target_card_name:
                                # 将影响累加到 action_j 的位置上
                                influences_in_sequence[j] += modifier
                                # 假设一个影响只作用于后续第一个匹配的牌 (简化)
                                break # 找到第一个就停止对这个 target_card_name 的查找

            # 第二遍：评估序列的总分，应用计算出的影响
            for i, action in enumerate(current_sequence):
                modifier_for_this_action = influences_in_sequence[i]
                action_score = evaluate_action(action, weights, modifier_for_this_action)
                current_total_score += action_score
                # print(f"  Eval: {action.name} (Mod: {modifier_for_this_action}) -> Score: {action_score:.2f}") # Debug

            # print(f"Seq: {[a.name for a in current_sequence]} -> Total Score: {current_total_score:.2f}") # Debug

            # 更新最佳序列
            if current_total_score > max_score:
                max_score = current_total_score
                best_sequence = current_sequence

    # MVP 简化：排序只基于己方收益最大化，暂不考虑最小化敌方（需要概率模型集成）
    return best_sequence, max_score
