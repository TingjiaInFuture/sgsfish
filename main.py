from game_elements import Hero, Player, get_card_instance, load_card_prototypes # 确保 load_card_prototypes 被导入
from game_logic import find_best_sequence, estimate_opponent_hand_probabilities, INITIAL_DECK_COMPOSITION
import database # 确保 database.py 被执行以加载数据

def run_test_scenario():
    """运行一个简单的1v1测试场景"""

    # --- 初始化数据库 (如果尚未完成) ---
    try:
        # 尝试加载卡牌数据，如果失败则初始化
        all_card_data = database.load_cards_from_db()
        if not all_card_data: # 检查是否成功加载了数据
             raise ValueError("未能从数据库加载卡牌数据")
        load_card_prototypes(all_card_data)
        # 尝试加载英雄数据以确认表存在
        if not database.load_hero_template('白板1'):
             raise ValueError("未能从数据库加载英雄模板")
    except Exception as e:
        print(f"初始化检查失败或数据不完整 ({e})，正在重新初始化数据库...")
        database.initialize_database()
        database.populate_initial_data() # 这会填充卡牌和英雄
        # 重新加载数据
        all_card_data = database.load_cards_from_db()
        load_card_prototypes(all_card_data)
        # 验证英雄数据是否已加载
        if not database.load_hero_template('白板1'):
            print("错误：数据库初始化后仍无法加载英雄模板！")
            return # 无法继续


    # --- 输入 ---
    # 从数据库加载英雄模板
    my_hero_template = database.load_hero_template("白板1")
    opponent_hero_template = database.load_hero_template("白板2")

    if not my_hero_template or not opponent_hero_template:
        print("错误：无法从数据库加载所需的英雄模板。")
        return

    # 使用模板创建英雄实例，并设置当前状态 (血量)
    # 己方信息
    my_current_hp = 4 # 场景设定：己方当前血量
    my_hero = Hero(name=my_hero_template['name'],
                   max_hp=my_hero_template['max_hp'],
                   current_hp=my_current_hp)

    # 从数据库获取卡牌实例 (手牌内容作为场景输入)
    my_hand_names = ["过河拆桥", "过河拆桥","杀", "顺手牵羊"] # 添加顺手牵羊到手牌
    my_hand_cards = [get_card_instance(name) for name in my_hand_names]
    me = Player(name="玩家1", hero=my_hero, hand=my_hand_cards)

    # 敌方信息
    opponent_current_hp = 2 # 场景设定：敌方当前血量
    opponent_hero = Hero(name=opponent_hero_template['name'],
                         max_hp=opponent_hero_template['max_hp'],
                         current_hp=opponent_current_hp)
    opponent_hand_count = 3 # 场景设定：敌方手牌数
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
