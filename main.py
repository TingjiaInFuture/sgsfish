from game_elements import Hero, Card, Skill, AttributeSet
from game_elements import CARD_SHA, CARD_SHAN, CARD_TAO, SKILL_DEFAULT_ACTIVE
from player import Player
from game_logic import find_best_sequence

def run_test_scenario():
    """运行一个简单的1v1测试场景"""

    # --- 输入 ---
    # 己方信息
    my_hero = Hero(name="关羽", max_hp=4, current_hp=2, skills=[SKILL_DEFAULT_ACTIVE])
    my_hand = [CARD_SHA, CARD_SHA, CARD_SHAN, CARD_TAO]
    me = Player(name="玩家1", hero=my_hero, hand=my_hand)

    # 敌方信息 (MVP简化：只需要血量和技能用于权重计算，手牌数暂时不用)
    opponent_hero = Hero(name="曹操", max_hp=4, current_hp=3, skills=[]) # 假设敌方无可用主动技能
    opponent_hand_count = 2 # 敌方手牌数 (MVP中未使用)
    opponent = Player(name="玩家2", hero=opponent_hero)

    print("--- 场景信息 ---")
    print(f"己方: {me.name} ({me.hero.name} {me.hero.current_hp}/{me.hero.max_hp} HP)")
    print(f"  手牌: {[card.name for card in me.hand]}")
    print(f"  技能: {[skill.name for skill in me.hero.skills if skill.is_active]}")
    print(f"敌方: {opponent.name} ({opponent.hero.name} {opponent.hero.current_hp}/{opponent.hero.max_hp} HP)")
    print(f"  手牌数: {opponent_hand_count}")
    print("-" * 17)

    # --- 计算最佳顺序 ---
    best_sequence = find_best_sequence(me, opponent)

    # --- 输出 ---
    print("--- 推荐行动顺序 ---")
    if best_sequence:
        print(" -> ".join([action.name for action in best_sequence]))
    else:
        print("无推荐行动")
    print("-" * 20)

if __name__ == "__main__":
    run_test_scenario()
