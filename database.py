import sqlite3
import json
from typing import Dict, Any, List, Tuple, Optional
import os # 导入 os 模块

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
        ('顺手牵羊', 0.0, 0.0, 1.0),
    ]

    influences_data = [
        ('过河拆桥', '杀', 1.0, 0.0, 0.0),
        ('过河拆桥', '顺手牵羊', 0.0, 0.0, 1.0),
        ('顺手牵羊', '杀', 1.0, 0.0, 0.0),
    ]

    heroes_data = [
        ('白板1', 4),
        ('白板2', 4),
    ]

    try:
        print("Inserting cards...")
        cursor.executemany('INSERT OR IGNORE INTO cards (name, attack, defense, support) VALUES (?, ?, ?, ?)', cards_data)
        print("Cards inserted.")

        print("Inserting heroes...")
        cursor.executemany('INSERT OR IGNORE INTO heroes (name, max_hp) VALUES (?, ?)', heroes_data)
        print("Heroes inserted.")

        print("Inserting influences...")
        # Ensure the target columns exactly match the number of values in the tuples
        cursor.executemany('INSERT INTO card_influences (source_card_name, target_card_name, attack_modifier, defense_modifier, support_modifier) VALUES (?, ?, ?, ?, ?)', influences_data)
        print("Influences inserted.")

        conn.commit()
        print("初始卡牌、英雄和影响数据已填充/更新。")
    except sqlite3.Error as e: # Catch specific SQLite errors
        print(f"填充数据时发生数据库错误: {e}") # Print the specific error
        conn.rollback() # Rollback on error
    except Exception as e: # Catch any other unexpected errors
        print(f"填充数据时发生未知错误: {e}")
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
    # --- 确保测试/初始化时的干净状态 ---
    if os.path.exists(DB_PATH):
        print(f"删除旧数据库文件: {DB_PATH}")
        try:
            os.remove(DB_PATH)
            print("旧数据库文件已删除。")
        except OSError as e:
            print(f"错误：无法删除数据库文件 {DB_PATH}: {e}")
            # 根据需要决定是否继续
            # return
    # --- 结束干净状态 ---

    # 作为脚本运行时，初始化并填充数据库
    print("正在初始化数据库...")
    initialize_database() # 这会创建新表
    print("正在填充初始数据...")
    populate_initial_data() # 这会向新表中插入数据

    # 测试加载
    print("\n--- 测试加载数据 ---")
    try:
        loaded_cards = load_cards_from_db()
        print("\n加载的卡牌数据示例:")
        import pprint
        pprint.pprint(loaded_cards)
        hero1_template = load_hero_template('白板1')
        print("\n加载的英雄模板示例:")
        pprint.pprint(hero1_template)
    except Exception as e:
        print(f"\n测试加载时出错: {e}")
    print("-" * 20)
