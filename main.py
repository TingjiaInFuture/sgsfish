from game_elements import Hero, Player, get_action_entity_instance, load_action_entity_prototypes
from game_logic import find_best_sequence, estimate_opponent_hand_probabilities, INITIAL_DECK_COMPOSITION
import database

def run_test_scenario():
    """运行一个简单的1v1测试场景"""

    # --- 初始化数据库 (如果尚未完成) ---
    try:
        # 尝试加载实体数据，如果失败则初始化
        all_entity_data = database.load_entities_from_db() # 更新函数调用
        if not all_entity_data:
             raise ValueError("未能从数据库加载实体数据")
        load_action_entity_prototypes(all_entity_data) # 更新函数调用
        # 尝试加载英雄数据以确认表存在
        if not database.load_hero_template('白板1'):
             raise ValueError("未能从数据库加载英雄模板")
    except Exception as e:
        print(f"初始化检查失败或数据不完整 ({e})，正在重新初始化数据库...")
        database.initialize_database()
        database.populate_initial_data()
        # 重新加载数据
        all_entity_data = database.load_entities_from_db() # 更新函数调用
        load_action_entity_prototypes(all_entity_data) # 更新函数调用
        if not database.load_hero_template('白板1'):
            print("错误：数据库初始化后仍无法加载英雄模板！")
            return

    # --- 输入 ---
    my_hero_template = database.load_hero_template("白板1")
    opponent_hero_template = database.load_hero_template("白板2")

    if not my_hero_template or not opponent_hero_template:
        print("错误：无法从数据库加载所需的英雄模板。")
        return

    my_current_hp = 4
    my_hero = Hero(name=my_hero_template['name'],
                   max_hp=my_hero_template['max_hp'],
                   current_hp=my_current_hp)

    my_hand_names = ["过河拆桥", "杀", "顺手牵羊"]
    my_hand_entities = [get_action_entity_instance(name) for name in my_hand_names]
    me = Player(name="玩家1", hero=my_hero, hand=my_hand_entities)

    opponent_current_hp = 2
    opponent_hero = Hero(name=opponent_hero_template['name'],
                         max_hp=opponent_hero_template['max_hp'],
                         current_hp=opponent_current_hp)
    opponent_hand_count = 3
    opponent = Player(name="玩家2", hero=opponent_hero, hand=[])

    print("\n--- 场景信息 ---")
    print(f"己方: {me.name} ({me.hero.name} {me.hero.current_hp}/{me.hero.max_hp} HP)")
    print(f"  手牌: {[entity.name for entity in me.hand]}") # 更新变量名
    print(f"敌方: {opponent.name} ({opponent.hero.name} {opponent.hero.current_hp}/{opponent.hero.max_hp} HP)")
    print(f"  手牌数: {opponent_hand_count}")
    print("-" * 17)

    # --- 计算最佳顺序 ---
    # 返回值类型已更改
    best_sequence_choices, best_score = find_best_sequence(me, opponent)

    # --- 计算对手手牌概率 ---
    known_entities = [entity.name for entity in me.hand] # 更新变量名
    opponent_probs = estimate_opponent_hand_probabilities(known_entities, opponent_hand_count) # 更新参数名

    # --- 输出 ---
    print("--- 推荐行动顺序 ---")
    if best_sequence_choices:
        # 调整输出格式以显示实体名称和选择的作用域
        sequence_repr = []
        for entity, scope in best_sequence_choices:
            scope_str = f"(作用域:{scope})" if scope is not None else ""
            sequence_repr.append(f"{entity.name}{scope_str}")
        print(f"序列: {' -> '.join(sequence_repr)}")
        print(f"预期总得分: {best_score:.2f}")
    else:
        print("无推荐行动")
    print("-" * 20)

    print("--- 敌方手牌概率估计 (基于简化模型) ---")
    if opponent_probs:
        sorted_probs = sorted(opponent_probs.items(), key=lambda item: item[1], reverse=True)
        for entity_name, prob in sorted_probs: # 更新变量名
            print(f"  {entity_name}: {prob:.2%}")
    else:
        print("无法估计概率 (牌堆不足或对手无手牌)")
    print("-" * 38)

if __name__ == "__main__":
    run_test_scenario()
