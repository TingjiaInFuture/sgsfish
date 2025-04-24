import sqlite3
import json
from typing import Dict, Any, List, Tuple, Optional
import os
from collections import defaultdict # Import defaultdict

DB_PATH = 'sgs_data.db'

def get_db_connection():
    """建立数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row # 让查询结果可以通过列名访问
    return conn

def initialize_database():
    """初始化数据库表，支持 ActionEntity 的 scope 和 influence 的 required_scope"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 更新 entities 表，添加 scope 列 (存储 JSON 列表)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS entities (
        name TEXT PRIMARY KEY,
        attack REAL DEFAULT 0.0,
        defense REAL DEFAULT 0.0,
        support REAL DEFAULT 0.0,
        timing INTEGER,
        response_suit INTEGER,
        response_rank_start INTEGER,
        response_rank_end INTEGER,
        scope TEXT -- 新增: 可选作用域 (存储为 JSON 字符串, e.g., '[1, 2, 3]')
    )
    ''')

    # 更新 entity_influences 表，添加 required_scope 列
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS entity_influences (
        influence_id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_entity_name TEXT NOT NULL,
        target_entity_name TEXT NOT NULL,
        attack_modifier REAL DEFAULT 0.0,
        defense_modifier REAL DEFAULT 0.0,
        support_modifier REAL DEFAULT 0.0,
        required_scope INTEGER, -- 新增: 影响生效所需的作用域
        FOREIGN KEY (source_entity_name) REFERENCES entities (name)
    )
    ''')

    # heroes 表保持不变
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS heroes (
        name TEXT PRIMARY KEY,
        max_hp INTEGER NOT NULL
    )
    ''')

    conn.commit()
    conn.close()
    print("数据库表已初始化/更新。")

def populate_initial_data():
    """填充初始数据，包含 scope 和 required_scope"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # (name, attack, defense, support, timing, response_suit, response_rank_start, response_rank_end, scope_json)
    entities_data = [
        ('杀', 1.0, 0.0, 0.0, 0, None, None, None, None), # 无特定可选作用域
        ('过河拆桥', 0.0, 0.0, 1.0, 0, None, None, None, json.dumps([1, 2, 3])), # 可选手牌(1), 装备(2), 判定(3)
        ('顺手牵羊', 0.0, 0.0, 1.0, 0, None, None, None, json.dumps([1, 2])), # 可选手牌(1), 装备(2)
        ('闪电', 0.0, 0.0, 0.0, 2, 1, 2, 9, None), # 判定牌，无可选作用域
        ('闪', 0.0, 1.0, 0.0, None, None, None, None, None), # 响应牌
        ('桃', 0.0, 0.0, 1.0, 0, None, None, None, None), # 出牌阶段可用
    ]

    # (source, target, atk_mod, def_mod, sup_mod, required_scope)
    influences_data = [
        # 过拆作用于手牌(1)时，增加后续杀的攻击
        ('过河拆桥', '杀', 1.0, 0.0, 0.0, 1),
        # 过拆作用于装备区(2)时，增加后续顺手的辅助
        ('过河拆桥', '顺手牵羊', 0.0, 0.0, 1.0, 2),
        # 顺手作用于手牌(1)时，增加后续杀的攻击
        ('顺手牵羊', '杀', 1.0, 0.0, 0.0, 1),
    ]

    heroes_data = [
        ('白板1', 4),
        ('白板2', 4),
    ]

    try:
        print("Inserting entities...")
        cursor.executemany('INSERT OR IGNORE INTO entities (name, attack, defense, support, timing, response_suit, response_rank_start, response_rank_end, scope) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', entities_data)
        print("Entities inserted.")

        print("Inserting heroes...")
        cursor.executemany('INSERT OR IGNORE INTO heroes (name, max_hp) VALUES (?, ?)', heroes_data)
        print("Heroes inserted.")

        print("Inserting influences...")
        cursor.executemany('INSERT INTO entity_influences (source_entity_name, target_entity_name, attack_modifier, defense_modifier, support_modifier, required_scope) VALUES (?, ?, ?, ?, ?, ?)', influences_data)
        print("Influences inserted.")

        conn.commit()
        print("初始实体、英雄和影响数据已填充/更新。")
    except sqlite3.Error as e:
        print(f"填充数据时发生数据库错误: {e}")
        conn.rollback()
    except Exception as e:
        print(f"填充数据时发生未知错误: {e}")
        conn.rollback()
    finally:
        conn.close()

def load_entities_from_db() -> Dict[str, Any]:
    """从数据库加载所有实体及其影响 (包含 scope 和 required_scope)"""
    entities = {}
    conn = get_db_connection()
    cursor = conn.cursor()

    # 加载实体基础属性、状态和 scope
    cursor.execute('SELECT name, attack, defense, support, timing, response_suit, response_rank_start, response_rank_end, scope FROM entities')
    entity_rows = cursor.fetchall()
    for row in entity_rows:
        entities[row['name']] = {
            'attributes': {'attack': row['attack'], 'defense': row['defense'], 'support': row['support']},
            'influences': defaultdict(list), # 初始化影响字典 (使用 defaultdict)
            'timing': row['timing'],
            'response_suit': row['response_suit'],
            'response_rank_start': row['response_rank_start'],
            'response_rank_end': row['response_rank_end'],
            'scope': row['scope'] # Load scope as JSON string initially
        }

    # 加载影响，包含 required_scope
    cursor.execute('''
        SELECT source_entity_name, target_entity_name, attack_modifier, defense_modifier, support_modifier, required_scope
        FROM entity_influences
    ''')
    influence_rows = cursor.fetchall()
    for row in influence_rows:
        source_name = row['source_entity_name']
        target_name = row['target_entity_name']
        if source_name in entities:
            modifier_data = {
                'attack': row['attack_modifier'],
                'defense': row['defense_modifier'],
                'support': row['support_modifier']
            }
            required_scope = row['required_scope']
            # 将影响存储为包含 modifier 和 required_scope 的字典
            entities[source_name]['influences'][target_name].append({
                'modifier': modifier_data,
                'required_scope': required_scope
            })

    conn.close()
    print(f"从数据库加载了 {len(entities)} 种实体。")
    return entities

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

    print("正在初始化数据库...")
    initialize_database()
    print("正在填充初始数据...")
    populate_initial_data()

    # 测试加载
    print("\n--- 测试加载数据 ---")
    try:
        loaded_entities = load_entities_from_db()
        print("\n加载的实体数据示例:")
        import pprint
        pprint.pprint(loaded_entities)
        hero1_template = load_hero_template('白板1')
        print("\n加载的英雄模板示例:")
        pprint.pprint(hero1_template)
    except Exception as e:
        print(f"\n测试加载时出错: {e}")
    print("-" * 20)
