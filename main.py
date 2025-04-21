from game_elements import Hero, Player, get_card_instance
from game_logic import find_best_sequence, estimate_opponent_hand_probabilities, INITIAL_DECK_COMPOSITION
import database # 确保 database.py 被执行以加载数据

def run_test_scenario():
    """运行一个简单的1v1测试场景"""

    # --- 初始化数据库 (如果尚未完成) ---
    # 通常在应用启动时执行一次
    try:
        # 尝试加载，如果失败说明可能需要初始化
        database.load_cards_from_db()
    except Exception:
        print("首次运行或数据库丢失，正在初始化数据库...")
        database.initialize_database()
        database.populate_initial_data()
        # 重新加载数据到 game_elements
        all_card_data = database.load_cards_from_db()
        from game_elements import load_card_prototypes
        load_card_prototypes(all_card_data)


    # --- 输入 ---
    # 己方信息 (白板武将)
    my_hero = Hero(name="白板1", max_hp=4, current_hp=4) # 假设满血
    # 从数据库获取卡牌实例
    my_hand_names = ["过河拆桥", "杀", "杀"]
    my_hand_cards = [get_card_instance(name) for name in my_hand_names]
    me = Player(name="玩家1", hero=my_hero, hand=my_hand_cards)

    # 敌方信息 (白板武将)
    opponent_hero = Hero(name="白板2", max_hp=4, current_hp=2) # 假设半血
    opponent_hand_count = 3 # 敌方手牌数
    opponent = Player(name="玩家2", hero=opponent_hero, hand=[]) # 手牌内容未知

    print("\n--- 场景信息 ---")
    print(f"己方: {me.name} ({me.hero.name} {me.hero.current_hp}/{me.hero.max_hp} HP)")
    print(f"  手牌: {[card.name for card in me.hand]}")
    print(f"敌方: {opponent.name} ({opponent.hero.name} {opponent.hero.current_hp}/{opponent.hero.max_hp} HP)")
    print(f"  手牌数: {opponent_hand_count}")
    print("-" * 17)

    # --- 计算最佳顺序 ---
    best_sequence, best_score = find_best_sequence(me, opponent)

    # --- 计算对手手牌概率 ---
    # 已知牌 = 己方手牌 (假设是刚摸到的，还没打出)
    known_cards = [card.name for card in me.hand]
    opponent_probs = estimate_opponent_hand_probabilities(known_cards, opponent_hand_count)


    # --- 输出 ---
    print("--- 推荐行动顺序 ---")
    if best_sequence:
        sequence_names = [action.name for action in best_sequence]
        print(f"序列: {' -> '.join(sequence_names)}")
        print(f"预期总得分: {best_score:.2f}")
    else:
        print("无推荐行动")
    print("-" * 20)

    print("--- 敌方手牌概率估计 (基于简化模型) ---")
    if opponent_probs:
        # 按概率降序排序
        sorted_probs = sorted(opponent_probs.items(), key=lambda item: item[1], reverse=True)
        for card_name, prob in sorted_probs:
            print(f"  {card_name}: {prob:.2%}")
    else:
        print("无法估计概率 (牌堆不足或对手无手牌)")
    print("-" * 38)

if __name__ == "__main__":
    run_test_scenario()
