import itertools
from typing import List, Tuple, Union, Dict
from game_elements import Card, Skill, AttributeSet
from player import Player

def calculate_weights(player_hp_ratio: float, opponent_hp_ratio: float) -> Dict[str, float]:
    """
    根据双方血量计算属性权重
    敌方血量越低，攻击权重越高
    己方血量越低，防御权重越高
    """
    attack_weight = 1.0 + (1.0 - opponent_hp_ratio) # 对方血越少，攻击权重越高 (基础1 + 补偿)
    defense_weight = 1.0 + (1.0 - player_hp_ratio)   # 自己血越少，防御权重越高 (基础1 + 补偿)
    support_weight = 1.0 # 辅助权重暂时固定

    return {"attack": attack_weight, "defense": defense_weight, "support": support_weight}

def evaluate_action(action: Union[Card, Skill], weights: Dict[str, float]) -> float:
    """评估单个行动（卡牌或技能）的价值"""
    if isinstance(action, (Card, Skill)):
        attrs = action.attributes
        score = (attrs.attack * weights.get("attack", 1.0) +
                 attrs.defense * weights.get("defense", 1.0) +
                 attrs.support * weights.get("support", 1.0))
        return score
    return 0.0

def find_best_sequence(player: Player, opponent: Player) -> List[Union[Card, Skill]]:
    """
    查找当前玩家的最佳行动顺序
    """
    possible_actions: List[Union[Card, Skill]] = []

    # 1. 添加手牌到可能行动列表
    possible_actions.extend(player.hand)

    # 2. 添加可用的主动技能到可能行动列表
    for skill in player.hero.skills:
        if skill.is_active:
            # MVP简化：假设主动技能每回合只能用一次
            possible_actions.append(skill)

    # 3. 计算当前权重
    weights = calculate_weights(player.hero.get_hp_ratio(), opponent.hero.get_hp_ratio())

    best_sequence = []
    max_score = -float('inf')

    # 4. 遍历所有可能的行动排列组合 (考虑所有子集及其排列)
    #    例如，如果有行动 A, B, C，可能的序列有 [], [A], [B], [C], [A, B], [B, A], [A, C], [C, A], [B, C], [C, B], [A, B, C], ...
    for k in range(len(possible_actions) + 1): # 从 0 个行动到所有行动
        for sequence_tuple in itertools.permutations(possible_actions, k):
            current_sequence = list(sequence_tuple)
            current_score = 0
            # 5. 评估每个序列的总价值
            #    MVP简化：直接累加每个行动的价值
            for action in current_sequence:
                current_score += evaluate_action(action, weights)

            # 6. 更新最佳序列
            if current_score > max_score:
                max_score = current_score
                best_sequence = current_sequence

    # MVP 简化：暂时不考虑概率模型和对敌方的影响评估
    # 排序方式：首先己方所有牌和技能的防御属性和攻击属性最大... (已通过权重和评分体现)
    # 其次比较敌方所有牌（由概率模型给出）和技能的防御属性和攻击属性最小 (MVP未实现)

    return best_sequence
