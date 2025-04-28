import itertools
from typing import List, Tuple, Dict, Optional, Union # Add Union
from collections import defaultdict
import torch # Need torch for tensor operations

# Use ge prefix for clarity and access to global weights/prototypes
import game_elements as ge
from game_elements import ActionEntity, AttributeSet, Player, Hero, TensorAttributeSet
# Import function to get learned modifiers from training module
from training import get_influence_modifier_tensor

# --- Probability Model and Deck (Keep as is) ---
INITIAL_DECK_COMPOSITION = {
    "杀": 15,
    "过河拆桥": 5,
    "顺手牵羊": 5,
    "闪": 10,
    "桃": 5,
    "闪电": 1,
}

def estimate_opponent_hand_probabilities(
    known_entities: List[str],
    opponent_hand_size: int,
    initial_deck: Dict[str, int] = INITIAL_DECK_COMPOSITION
) -> Dict[str, float]:
    """
    根据已知实体和对手手牌数，估计对手手牌中各种实体的概率
    """
    remaining_deck = initial_deck.copy()
    for entity_name in known_entities:
        if entity_name in remaining_deck and remaining_deck[entity_name] > 0:
            remaining_deck[entity_name] -= 1

    total_remaining_cards = sum(remaining_deck.values())
    probabilities = defaultdict(float)

    if total_remaining_cards <= 0 or opponent_hand_size <= 0:
        return dict(probabilities)

    for entity_name, count in remaining_deck.items():
        if count > 0:
            proportion = count / total_remaining_cards
            probabilities[entity_name] = proportion

    return dict(probabilities)


# --- Weight Calculation (Keep as is) ---
def calculate_weights(player_hp_ratio: float, opponent_hp_ratio: float) -> Dict[str, float]:
    """根据双方血量计算属性权重"""
    attack_weight = 1.0 + (1.0 - opponent_hp_ratio) # 敌方血少，攻击权重高
    defense_weight = 1.0 + (1.0 - player_hp_ratio)   # 己方血少，防御权重高
    support_weight = 1.0 # 辅助权重暂时固定
    return {"attack": attack_weight, "defense": defense_weight, "support": support_weight}

# --- Action Evaluation (Handles TensorAttributeSet from learned weights) ---
def evaluate_action(
    action: ActionEntity,
    weights: Dict[str, float],
    # Modifier might be TensorAttributeSet during runtime if derived from learned weights
    active_influence_modifier: Union[AttributeSet, TensorAttributeSet] = TensorAttributeSet(), # Default to empty Tensor set
    chosen_scope: Optional[int] = None # Keep chosen_scope, though not directly used in this func
) -> float:
    """
    评估单个行动的价值。
    如果 active_influence_modifier 是 TensorAttributeSet，则从中提取数值。
    """
    # Base attributes are always floats (AttributeSet)
    base_attrs = action.base_attributes

    # Add base attributes and the modifier. This works if modifier is AttributeSet or TensorAttributeSet
    # The result will be AttributeSet or TensorAttributeSet
    effective_attributes = base_attrs + active_influence_modifier

    # Extract float values for score calculation
    if isinstance(effective_attributes, TensorAttributeSet):
        # Detach tensor from graph and get Python float value
        atk = effective_attributes.attack.detach().item()
        dfs = effective_attributes.defense.detach().item()
        sup = effective_attributes.support.detach().item()
    elif isinstance(effective_attributes, AttributeSet):
         atk = effective_attributes.attack
         dfs = effective_attributes.defense
         sup = effective_attributes.support
    else:
        # Fallback, should not happen with current __add__ implementations
        atk, dfs, sup = 0.0, 0.0, 0.0
        print(f"Warning: Unexpected type for effective_attributes in evaluate_action: {type(effective_attributes)}")

    # Calculate score using float values
    score = (atk * weights.get("attack", 1.0) +
             dfs * weights.get("defense", 1.0) +
             sup * weights.get("support", 1.0))

    return score

# --- Best Sequence Finder (Uses LEARNED weights) ---
def find_best_sequence(
    player: Player,
    opponent: Player
) -> Tuple[List[Tuple[ActionEntity, Optional[int]]], float]:
    """
    查找当前玩家的最佳行动顺序，使用从全局 ge.influence_weights 获取的影响修正值。
    """
    # Check if weights are loaded/initialized. This should be handled by main.py ideally.
    if ge.influence_weights is None:
        print("Warning: ge.influence_weights is None in find_best_sequence. Influence modifiers will be zero.")
        # As a safety measure, maybe initialize here? Or rely on main.py's init.
        # For now, proceed assuming zero influence if not loaded.

    context_weights = calculate_weights(player.hero.get_hp_ratio(), opponent.hero.get_hp_ratio())

    # 1. Generate all possible "action choices" (entity, chosen_scope) from hand
    possible_action_choices: List[Tuple[ActionEntity, Optional[int]]] = []
    for entity in player.hand:
        if entity.scope:
            # If scopable, create choices for each scope option
            for scope_option in entity.scope:
                possible_action_choices.append((entity, scope_option))
            # Optional: Also consider using the scopable card without a specific scope?
            # If the game allows using '过河拆桥' without specifying target type initially.
            # possible_action_choices.append((entity, None)) # Add this if applicable
        else:
            # If not scopable, the only choice is the entity itself with None scope
            possible_action_choices.append((entity, None))

    best_sequence_choices: List[Tuple[ActionEntity, Optional[int]]] = []
    max_score = -float('inf')

    # 2. Iterate through permutations of possible action choices
    # Consider permutations up to the number of choices available
    max_k = len(possible_action_choices)
    for k in range(max_k + 1): # Check sequences of length 0 to max_k
        # Use itertools.permutations to get sequences of length k
        for sequence_tuple in itertools.permutations(possible_action_choices, k):
            current_sequence_choices = list(sequence_tuple)
            current_total_score = 0.0
            # Use TensorAttributeSet to accumulate modifiers, even if weights aren't loaded (defaults to 0 tensor)
            influences_in_sequence: Dict[int, TensorAttributeSet] = defaultdict(TensorAttributeSet)

            # --- First pass: Calculate influence using LEARNED weights ---
            if ge.influence_weights is not None: # Only calculate if weights are available
                for i, (action_i, chosen_scope_i) in enumerate(current_sequence_choices):
                    # Check potential influences defined for action_i in prototypes
                    for target_entity_name, possible_scopes in action_i.potential_influences.items():
                         # Check each scope rule defined for this source-target pair
                         for required_scope in possible_scopes:
                              # Does the rule's required scope match the scope chosen for action_i?
                              if required_scope is None or required_scope == chosen_scope_i:
                                  # --- Get modifier tensor from LEARNED WEIGHTS ---
                                  modifier_tensor = get_influence_modifier_tensor(
                                      action_i.name, target_entity_name, required_scope
                                  )
                                  # --- End of learned weight usage ---

                                  if modifier_tensor is not None:
                                      # Find the first subsequent action matching the target name
                                      for j in range(i + 1, len(current_sequence_choices)):
                                          action_j, _ = current_sequence_choices[j]
                                          if action_j.name == target_entity_name:
                                              # Accumulate the tensor modifier
                                              influences_in_sequence[j] += modifier_tensor
                                              # Assumption: influence applies only to the first match
                                              break # Move to the next rule/target

            # --- Second pass: Evaluate sequence score using accumulated modifiers ---
            for i, (action, chosen_scope) in enumerate(current_sequence_choices):
                # Get the accumulated modifier (TensorAttributeSet, possibly all zeros)
                modifier_for_this_action = influences_in_sequence[i]
                # evaluate_action handles TensorAttributeSet modifier and returns float score
                action_score = evaluate_action(action, context_weights, modifier_for_this_action, chosen_scope)
                current_total_score += action_score

            # Update best sequence found so far
            if current_total_score > max_score:
                max_score = current_total_score
                best_sequence_choices = current_sequence_choices

    return best_sequence_choices, max_score

# --- Remove prototype loading from here; it's handled in main.py ---
# try:
#     print("Game Logic: Loading entity data for prototypes...")
#     import database # Local import for this block if needed, avoid top-level if circular
#     all_entity_data = database.load_entities_from_db()
#     ge.load_action_entity_prototypes(all_entity_data)
# except Exception as e:
#     print(f"Game Logic Error: Failed to load entity data on import: {e}")
