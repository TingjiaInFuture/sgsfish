import sqlite3
import json
from typing import Dict, Any, List, Tuple, Optional

DB_PATH = 'sgs_data.db'

def get_db_connection():
    """建立数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row # 让查询结果可以通过列名访问
    return conn

def initialize_database():
    """初始化数据库表"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 创建 cards 表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS cards (
        name TEXT PRIMARY KEY,
        attack REAL DEFAULT 0.0,
        defense REAL DEFAULT 0.0,
        support REAL DEFAULT 0.0
    )
    ''')

    # 创建 card_influences 表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS card_influences (
        influence_id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_card_name TEXT NOT NULL,
        target_card_name TEXT NOT NULL,
        attack_modifier REAL DEFAULT 0.0,
        defense_modifier REAL DEFAULT 0.0,
        support_modifier REAL DEFAULT 0.0,
        FOREIGN KEY (source_card_name) REFERENCES cards (name)
    )
    ''')

    # 创建 heroes 表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS heroes (
        name TEXT PRIMARY KEY,
        max_hp INTEGER NOT NULL
        -- 可以添加其他英雄基础属性，如势力、初始技能等
    )
    ''')

    conn.commit()
    conn.close()
    print("数据库表已初始化。")

def populate_initial_data():
    """填充初始卡牌、影响和英雄数据"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cards_data = [
        ('杀', 1.0, 0.0, 0.0),
        ('过河拆桥', 0.0, 0.0, 1.0),
    ]

    influences_data = [
        # 过河拆桥影响杀：攻击+1
        ('过河拆桥', '杀', 1.0, 0.0, 0.0),
    ]

    heroes_data = [
        ('白板1', 4),
        ('白板2', 4),
    ]

    try:
        cursor.executemany('INSERT OR IGNORE INTO cards (name, attack, defense, support) VALUES (?, ?, ?, ?)', cards_data)
        cursor.executemany('INSERT OR IGNORE INTO heroes (name, max_hp) VALUES (?, ?)', heroes_data) # 使用 IGNORE 避免重复插入
        # 注意：影响数据通常不应该用 IGNORE，除非确定不会有重复且重要的影响
        cursor.executemany('INSERT INTO card_influences (source_card_name, target_card_name, attack_modifier, defense_modifier, support_modifier) VALUES (?, ?, ?, ?, ?)', influences_data)

        conn.commit()
        print("初始卡牌、英雄和影响数据已填充。")
    except sqlite3.IntegrityError as e:
        # 如果是因为 IGNORE 跳过了，这里可能不会触发，但保留以防其他约束
        print(f"填充数据时出错 (可能部分数据已存在): {e}")
    except sqlite3.Error as e:
        print(f"填充数据时发生数据库错误: {e}")
        conn.rollback()
    finally:
        conn.close()


def load_cards_from_db() -> Dict[str, Any]:
    """从数据库加载所有卡牌及其影响"""
    cards = {}
    conn = get_db_connection()
    cursor = conn.cursor()

    # 加载卡牌基础属性
    cursor.execute('SELECT name, attack, defense, support FROM cards')
    card_rows = cursor.fetchall()
    for row in card_rows:
        cards[row['name']] = {
            'attributes': {'attack': row['attack'], 'defense': row['defense'], 'support': row['support']},
            'influences': {} # 初始化影响字典
        }

    # 加载影响
    cursor.execute('''
        SELECT source_card_name, target_card_name, attack_modifier, defense_modifier, support_modifier
        FROM card_influences
    ''')
    influence_rows = cursor.fetchall()
    for row in influence_rows:
        source_name = row['source_card_name']
        target_name = row['target_card_name']
        if source_name in cards:
            modifier = {
                'attack': row['attack_modifier'],
                'defense': row['defense_modifier'],
                'support': row['support_modifier']
            }
            # 将影响存储在源卡牌的 'influences' 字典中
            cards[source_name]['influences'][target_name] = modifier

    conn.close()
    print(f"从数据库加载了 {len(cards)} 种卡牌。")
    return cards

def load_hero_template(name: str) -> Optional[Dict[str, Any]]:
    """从数据库加载指定名称的英雄模板数据"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT name, max_hp FROM heroes WHERE name = ?', (name,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

if __name__ == '__main__':
    # 作为脚本运行时，初始化并填充数据库
    initialize_database()
    populate_initial_data()
    # 测试加载
    loaded_cards = load_cards_from_db()
    print("\n加载的卡牌数据示例:")
    import pprint
    pprint.pprint(loaded_cards)
    hero1_template = load_hero_template('白板1')
    print("\n加载的英雄模板示例:")
    pprint.pprint(hero1_template)
