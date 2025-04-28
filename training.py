import torch
import torch.optim as optim
from torch.nn import Parameter, ParameterDict
from typing import List, Tuple, Dict, Optional, Any
from collections import defaultdict
import random
import os
import game_elements as ge # Import ge to access global weights and prototypes
# Import specific classes needed for type hinting and instantiation
from game_elements import Player, Hero, AttributeSet, TensorAttributeSet, ActionEntity, get_action_entity_instance
# Import necessary functions from game_logic
from game_logic import calculate_weights

WEIGHTS_FILE = "influence_weights.pth"
SCOPE_KEY_NONE = "NoneScope" # Use a distinct string key for None scope

def get_scope_key(scope: Optional[int]) -> str:
    """Converts scope (int or None) to a string key suitable for ParameterDict."""
    return str(scope) if scope is not None else SCOPE_KEY_NONE

def initialize_influence_weights(prototypes: Dict[str, ActionEntity]) -> ParameterDict:
    """
    Initializes the ParameterDict for learnable influence weights
    based on the potential influences defined in prototypes.
    Initializes weights to small random values.
    """
    weights = ParameterDict()
    print("Initializing influence weights structure...")
    for source_name, proto in prototypes.items():
        if proto.potential_influences:
            source_weights = ParameterDict()
            # Group by target_name first
            for target_name, required_scopes in proto.potential_influences.items():
                 # Check if target entity actually exists in prototypes
                 if target_name not in prototypes:
                     print(f"Warning: Target entity '{target_name}' for influence from '{source_name}' not found in prototypes. Skipping this target.")
                     continue

                 target_weights = ParameterDict()
                 # Use unique scopes for this source-target pair
                 unique_scopes = set(required_scopes)
                 for scope in unique_scopes:
                     scope_key = get_scope_key(scope)
                     # Each influence modifier (atk, def, sup) is a learnable parameter
                     attr_weights = ParameterDict({
                         # Initialize with small random values, requires_grad=True by default for Parameter
                         "attack": Parameter(torch.randn(1) * 0.01),
                         "defense": Parameter(torch.randn(1) * 0.01),
                         "support": Parameter(torch.randn(1) * 0.01)
                     })
                     target_weights[scope_key] = attr_weights

                 # Only add target if it had valid scopes defined
                 if target_weights:
                    source_weights[target_name] = target_weights

            # Only add source if it had valid targets
            if source_weights:
                weights[source_name] = source_weights

    print(f"Influence weights structure initialized with {len(weights)} sources.")
    # Set the global variable in game_elements AFTER initialization
    ge.influence_weights = weights
    return weights

def get_influence_modifier_tensor(source_name: str, target_name: str, scope: Optional[int]) -> Optional[TensorAttributeSet]:
    """
    Retrieves the learnable influence modifier as a TensorAttributeSet
    from the global influence_weights. Returns None if no such influence exists.
    Handles ParameterDict structure.
    """
    if ge.influence_weights is None:
        # This shouldn't happen if initialization is done correctly
        print("Error: Influence weights accessed before initialization!")
        return None

    scope_key = get_scope_key(scope)

    try:
        # Safely navigate the ParameterDict structure using .get()
        source_params = ge.influence_weights.get(source_name)
        if source_params is None: return None

        target_params = source_params.get(target_name)
        if target_params is None: return None

        scope_params = target_params.get(scope_key)
        if scope_params is None: return None

        # We found the parameters, return them as TensorAttributeSet
        # .squeeze() removes the extra dimension from Parameter(torch.randn(1))
        return TensorAttributeSet(
            attack=scope_params["attack"].squeeze(),
            defense=scope_params["defense"].squeeze(),
            support=scope_params["support"].squeeze()
        )
    except KeyError as e:
         # Should be less likely with .get(), but good practice
         print(f"Internal KeyError looking up influence: {e}. Path: {source_name} -> {target_name} -> {scope_key}")
         return None
    except AttributeError:
         # Catch errors if the structure is not as expected (e.g., not a ParameterDict)
         print(f"AttributeError: Problem accessing weights structure for {source_name} -> {target_name} -> {scope_key}")
         return None


def save_weights(weights: ParameterDict, filename: str = WEIGHTS_FILE):
    """Saves the learnable weights' state_dict to a file."""
    if not weights:
        print("Warning: Attempted to save empty weights dictionary.")
        return
    try:
        torch.save(weights.state_dict(), filename)
        print(f"Influence weights saved to {filename}")
    except Exception as e:
        print(f"Error saving weights to {filename}: {e}")

def load_weights(prototypes: Dict[str, ActionEntity], filename: str = WEIGHTS_FILE) -> ParameterDict:
    """
    Loads learnable weights from a file. If the file doesn't exist or fails
    to load, it initializes new weights based on the provided prototypes.
    Sets the global ge.influence_weights.
    """
    weights = initialize_influence_weights(prototypes) # Initialize structure first
    if os.path.exists(filename):
        try:
            state_dict = torch.load(filename)
            # Load state_dict, ignoring missing/unexpected keys
            missing_keys, unexpected_keys = weights.load_state_dict(state_dict, strict=False)
            if missing_keys:
                print(f"Warning: Missing keys when loading weights (initialized randomly): {missing_keys}")
            if unexpected_keys:
                 print(f"Warning: Unexpected keys found in saved weights file (ignored): {unexpected_keys}")
            print(f"Influence weights loaded from {filename}")
        except Exception as e:
            print(f"Error loading weights from {filename}: {e}. Using newly initialized weights.")
            # Keep the newly initialized weights from initialize_influence_weights()
    else:
        print(f"Weights file {filename} not found. Using newly initialized weights.")
        # Keep the newly initialized weights from initialize_influence_weights()

    # Ensure the global variable is set in either case (load success, load fail, file not found)
    ge.influence_weights = weights
    return weights

# --- Score Calculation (Differentiable version for Training) ---

def evaluate_action_tensor(
    action: ActionEntity,
    context_weights: Dict[str, float],
    active_influence_modifier: TensorAttributeSet # Expect tensor modifiers
) -> torch.Tensor:
    """Evaluates a single action using tensors for differentiability."""
    # Base attributes are floats, convert to TensorAttributeSet
    base_tensor_attrs = TensorAttributeSet(
         attack=torch.tensor(action.base_attributes.attack, dtype=torch.float32),
         defense=torch.tensor(action.base_attributes.defense, dtype=torch.float32),
         support=torch.tensor(action.base_attributes.support, dtype=torch.float32)
    )

    # Add base attributes (now tensors) and the influence modifier (already tensor)
    effective_attributes = base_tensor_attrs + active_influence_modifier

    # Context weights (from calculate_weights) are constants w.r.t influence weights
    # Ensure context_weights values are floats
    attack_w = float(context_weights.get("attack", 1.0))
    defense_w = float(context_weights.get("defense", 1.0))
    support_w = float(context_weights.get("support", 1.0))

    score = (effective_attributes.attack * attack_w +
             effective_attributes.defense * defense_w +
             effective_attributes.support * support_w)
    return score


def calculate_sequence_score_with_weights(
    sequence_choices: List[Tuple[ActionEntity, Optional[int]]],
    player_hp_ratio: float,
    opponent_hp_ratio: float
) -> torch.Tensor:
    """
    Calculates the total score of a GIVEN sequence using the CURRENT learnable
    influence weights. Returns a tensor for backpropagation.
    """
    if not sequence_choices:
        # Return a zero tensor that requires grad if weights exist, otherwise simple tensor
        if ge.influence_weights and list(ge.influence_weights.parameters()):
             # Find any parameter to ensure the device and requires_grad status are consistent
             a_param = next(iter(ge.influence_weights.parameters()))
             return torch.tensor(0.0, requires_grad=True, device=a_param.device)
        else:
             return torch.tensor(0.0)


    context_weights = calculate_weights(player_hp_ratio, opponent_hp_ratio)
    # Initialize accumulated score tensor. Ensure it requires grad if weights do.
    initial_score = torch.tensor(0.0, requires_grad=True)
    influences_in_sequence: Dict[int, TensorAttributeSet] = defaultdict(TensorAttributeSet)

    # --- First pass: Calculate accumulated influence modifiers (using learnable weights) ---
    for i, (action_i, chosen_scope_i) in enumerate(sequence_choices):
        # Check potential influences originating from action_i
        for target_entity_name, possible_scopes in action_i.potential_influences.items():
            # Iterate through scopes defined for this source-target pair in prototypes
            for required_scope in possible_scopes:
                 # Check if the scope matches the one chosen for action_i in this sequence
                if required_scope is None or required_scope == chosen_scope_i:
                     # Retrieve the learnable modifier tensor for this specific influence path
                    modifier_tensor = get_influence_modifier_tensor(
                        action_i.name, target_entity_name, required_scope
                    )

                    if modifier_tensor is not None:
                         # Find the first occurrence of target_entity_name after action_i
                        for j in range(i + 1, len(sequence_choices)):
                             action_j, _ = sequence_choices[j]
                             if action_j.name == target_entity_name:
                                 # Add the modifier tensor to the influences for action_j
                                 # TensorAttributeSet.__add__ handles the tensor addition
                                 influences_in_sequence[j] += modifier_tensor
                                 # Assumption: influence applies only to the first match
                                 break # Stop searching for this target_name for this rule

    # --- Second pass: Evaluate actions with accumulated modifiers ---
    current_total_score = initial_score # Start with the initial zero tensor
    for i, (action, chosen_scope) in enumerate(sequence_choices):
        modifier_for_this_action = influences_in_sequence[i]
        # Pass context_weights and tensor modifier to evaluation
        action_score = evaluate_action_tensor(action, context_weights, modifier_for_this_action)
        current_total_score = current_total_score + action_score # Accumulate scores (tensor addition)

    return current_total_score


# --- Training Loop ---

def generate_dummy_training_data(num_samples: int, prototypes: Dict[str, ActionEntity]) -> List[Tuple[Dict[str, Any], List[Tuple[str, Optional[int]]], int]]:
    """Generates simple dummy data for training demonstration."""
    data = []
    entity_names = list(prototypes.keys())
    if not entity_names:
        print("Warning: No entity prototypes found for generating dummy data.")
        return []

    print(f"Generating {num_samples} dummy training samples...")
    for _ in range(num_samples):
        # Dummy state
        state = {
            "player_hp_ratio": random.uniform(0.1, 1.0),
            "opponent_hp_ratio": random.uniform(0.1, 1.0)
        }

        # Dummy sequence (1-3 actions)
        max_seq_len = min(3, len(entity_names))
        seq_len = random.randint(1, max_seq_len) if max_seq_len > 0 else 0
        if seq_len == 0: continue # Skip if no actions possible

        # Sample action names (allow replacement for simplicity, though real game is no replacement)
        action_names = random.choices(entity_names, k=seq_len)
        sequence = []
        valid_sample = True
        for name in action_names:
            entity_proto = prototypes.get(name)
            if not entity_proto: # Should not happen if entity_names is from prototypes
                 print(f"Error: Prototype for '{name}' not found during dummy data generation.")
                 valid_sample = False
                 break
            chosen_scope = None
            # If the entity *can* have a scope, randomly choose one or None
            if entity_proto.scope:
                 # Include None as a possibility even if scopes are defined
                 possible_choices = entity_proto.scope + [None]
                 chosen_scope = random.choice(possible_choices)
                 # If None was chosen, make it None type
                 if chosen_scope is None: pass
                 # If a scope number was chosen, ensure it's valid (it should be)
                 elif chosen_scope not in entity_proto.scope:
                      print(f"Warning: Invalid scope {chosen_scope} generated for {name}. Fixing.")
                      chosen_scope = random.choice(entity_proto.scope) # Pick a valid one
            # If entity_proto.scope is None or empty, chosen_scope remains None
            sequence.append((name, chosen_scope))

        if not valid_sample: continue

        # Dummy outcome (Win=+1, Loss=-1) - slightly biased towards positive score maybe?
        # Let's make it simple random for now
        outcome = 1 if random.random() < 0.5 else -1
        data.append((state, sequence, outcome))

    print(f"Generated {len(data)} valid dummy data samples.")
    return data

def training_loop(
    prototypes: Dict[str, ActionEntity],
    num_epochs: int = 10,
    learning_rate: float = 0.01,
    batch_size: int = 10,
    num_dummy_samples: int = 100
):
    """Main training loop."""
    # Load weights (initializes if file not found or error)
    # Pass prototypes for correct initialization structure
    weights = load_weights(prototypes)
    if weights is None or not list(weights.parameters()):
         print("Error: Weights could not be initialized or loaded properly. Aborting training.")
         return

    # Ensure parameters require gradients (should be true by default for Parameter)
    for param in weights.parameters():
        param.requires_grad = True

    optimizer = optim.Adam(weights.parameters(), lr=learning_rate)

    # Generate dummy data
    training_data = generate_dummy_training_data(num_dummy_samples, prototypes)
    if not training_data:
        print("No training data generated or available. Aborting training.")
        return

    print(f"\n--- Starting Training ---")
    print(f"Epochs: {num_epochs}, LR: {learning_rate}, Batch Size: {batch_size}")
    print(f"Number of parameters: {sum(p.numel() for p in weights.parameters() if p.requires_grad)}")

    for epoch in range(num_epochs):
        random.shuffle(training_data)
        epoch_loss = 0.0
        num_batches = 0
        processed_samples = 0

        for i in range(0, len(training_data), batch_size):
            batch = training_data[i:i+batch_size]
            optimizer.zero_grad() # Zero gradients for the batch

            batch_loss = torch.tensor(0.0, requires_grad=True) # Ensure batch loss tracks grad
            valid_samples_in_batch = 0

            for state, seq_name_scope_list, outcome in batch:
                 # Convert names back to entity instances for scoring
                sequence_choices = []
                valid_sequence = True
                for name, scope in seq_name_scope_list:
                     try:
                         entity = get_action_entity_instance(name)
                         # Validate chosen scope against the entity's possible scopes
                         if scope is not None and (entity.scope is None or scope not in entity.scope):
                             # This case should ideally be handled in data generation/validation
                             # print(f"Warning: Invalid scope {scope} for entity {name} in training data sample. Skipping sample.")
                             valid_sequence = False
                             break
                         sequence_choices.append((entity, scope))
                     except ValueError:
                         # print(f"Warning: Entity '{name}' not found in prototypes during training. Skipping sample.")
                         valid_sequence = False
                         break

                if not valid_sequence or not sequence_choices:
                    continue # Skip this sample if invalid

                # Calculate score using current weights
                calculated_score = calculate_sequence_score_with_weights(
                    sequence_choices,
                    state["player_hp_ratio"],
                    state["opponent_hp_ratio"]
                )

                # Simple Loss: Maximize score if outcome=1, Minimize score if outcome=-1
                # Equivalent to minimizing -outcome * score
                target_trend = torch.tensor(float(outcome), dtype=torch.float32, device=calculated_score.device)
                loss = -target_trend * calculated_score

                # Accumulate loss for the batch
                # Check if loss requires grad (it should if calculated_score did)
                if loss.requires_grad:
                    batch_loss = batch_loss + loss
                    valid_samples_in_batch += 1
                else:
                    # This might happen if a sequence score calculation somehow didn't involve any parameters
                    # Or if the sequence was empty (handled earlier)
                    # print(f"Warning: Loss for a sample did not require grad. Score: {calculated_score.item()}, Outcome: {outcome}")
                    pass


            if valid_samples_in_batch > 0:
                # Average loss over the valid samples in the batch
                avg_batch_loss = batch_loss / valid_samples_in_batch
                avg_batch_loss.backward() # Calculate gradients for the batch
                optimizer.step() # Update weights based on gradients
                epoch_loss += avg_batch_loss.item() * valid_samples_in_batch # Accumulate total loss back
                num_batches += 1
                processed_samples += valid_samples_in_batch
            # else: # No valid samples in batch, skip optimizer step
            #     print(f"Warning: Batch starting at index {i} had no valid samples.")


        if processed_samples > 0:
             avg_epoch_loss = epoch_loss / processed_samples
             print(f"Epoch {epoch+1}/{num_epochs}, Average Loss: {avg_epoch_loss:.6f}")
        else:
            print(f"Epoch {epoch+1}/{num_epochs}, No valid samples processed.")


        # Optional: Save weights periodically
        if (epoch + 1) % 5 == 0 or epoch == num_epochs - 1:
             if weights: # Ensure weights exist before saving
                 save_weights(weights)

    print("--- Training Finished ---")
