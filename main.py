import argparse
import database
import game_elements as ge # Use ge prefix
from game_logic import find_best_sequence, estimate_opponent_hand_probabilities # Removed INITIAL_DECK_COMPOSITION import if not used directly here
# Import necessary functions from training.py
from training import training_loop, load_weights, save_weights # Removed initialize_influence_weights if only load_weights is used externally

def initialize_system():
    """Initializes database, loads entity prototypes, and prepares weights."""
    print("--- System Initialization ---")
    db_initialized = False
    try:
        # 1. Check Database and Load Base Data
        print("Checking database and loading base data...")
        all_entity_data = database.load_entities_from_db()
        hero_template = database.load_hero_template('白板1') # Test load a hero

        # Basic validation: Do we have entities and the test hero?
        if not all_entity_data or not hero_template:
             # If DB exists but data is missing, maybe repopulate? Or raise error.
             if database.os.path.exists(database.DB_PATH):
                 print("Database file exists but seems empty or incomplete.")
                 raise ValueError("Database missing required entities/heroes.")
             else:
                 print("Database file not found.")
                 raise FileNotFoundError("Database file missing.")
        print("Database appears valid and contains data.")
        db_initialized = True

    except (FileNotFoundError, ValueError, database.sqlite3.OperationalError) as e:
        print(f"Database check/load failed ({e}). Attempting to initialize/repopulate...")
        # If DB file might be corrupt or outdated, removing it first can be safer
        if database.os.path.exists(database.DB_PATH):
            print(f"Removing existing database file: {database.DB_PATH}")
            try:
                database.os.remove(database.DB_PATH)
            except OSError as rm_err:
                 print(f"Warning: Could not remove old DB file: {rm_err}. Proceeding anyway.")

        try:
            database.initialize_database()
            database.populate_initial_data()
            db_initialized = True
            print("Database initialized and populated successfully.")
            # Reload data after initializing
            all_entity_data = database.load_entities_from_db()
            if not all_entity_data: # Check again after init
                 raise RuntimeError("Failed to load entity data even after initialization.")
        except Exception as init_e:
            print(f"FATAL: Database initialization failed: {init_e}")
            return False # Indicate failure

    # 2. Load Prototypes into Game Elements (only if DB init/load succeeded)
    if db_initialized and all_entity_data:
        print("Loading entity prototypes...")
        ge.load_action_entity_prototypes(all_entity_data)
        if not ge.ACTION_ENTITY_PROTOTYPES:
             print("FATAL: Failed to load prototypes into game elements.")
             return False # Indicate failure
        print("Entity prototypes loaded.")
    else:
        print("FATAL: Cannot load prototypes because database initialization/loading failed.")
        return False # Indicate failure

    # 3. Load or Initialize Weights (depends on prototypes being loaded)
    print("Loading/Initializing influence weights...")
    # load_weights now handles initialization if file not found/error
    # It requires prototypes to be loaded first to know the structure
    load_weights(ge.ACTION_ENTITY_PROTOTYPES)
    if ge.influence_weights is None:
        print("FATAL: Failed to load or initialize influence weights.")
        return False # Indicate failure
    print("Influence weights ready.")

    print("--- System Initialization Complete ---")
    return True # Indicate success

def run_test_scenario():
    """Runs the simple 1v1 test scenario using loaded/initialized weights."""
    print("\n--- Running Test Scenario ---")

    # Weights should have been loaded by initialize_system()
    if ge.influence_weights is None:
        print("CRITICAL ERROR: Influence weights not available for test scenario. Aborting.")
        # Attempting to load again might be redundant if initialize_system failed
        return

    # --- Input Setup ---
    try:
        my_hero_template = database.load_hero_template("白板1")
        opponent_hero_template = database.load_hero_template("白板2")
        if not my_hero_template or not opponent_hero_template:
            raise ValueError("Required hero templates not found in database.")

        my_hero = ge.Hero(name=my_hero_template['name'], max_hp=my_hero_template['max_hp'], current_hp=4)
        my_hand_names = ["过河拆桥", "杀", "顺手牵羊"]
        my_hand_entities = []
        for name in my_hand_names:
            try:
                my_hand_entities.append(ge.get_action_entity_instance(name))
            except ValueError as e:
                print(f"Warning: Could not get instance for '{name}': {e}. Skipping card.")

        me = ge.Player(name="玩家1", hero=my_hero, hand=my_hand_entities)

        opponent_hero = ge.Hero(name=opponent_hero_template['name'], max_hp=opponent_hero_template['max_hp'], current_hp=2)
        opponent = ge.Player(name="玩家2", hero=opponent_hero, hand=[])
        opponent_hand_count = 3 # Example value

    except Exception as setup_e:
        print(f"Error setting up scenario: {setup_e}")
        return

    print("\n--- Scenario Info ---")
    print(f"己方: {me.name} ({me.hero.name} {me.hero.current_hp}/{me.hero.max_hp} HP)")
    print(f"  手牌: {[entity.name for entity in me.hand]}")
    print(f"敌方: {opponent.name} ({opponent.hero.name} {opponent.hero.current_hp}/{opponent.hero.max_hp} HP)")
    print(f"  手牌数: {opponent_hand_count}")
    print("-" * 20)

    # --- Calculate Best Sequence (Uses loaded learned weights via game_logic) ---
    try:
        best_sequence_choices, best_score = find_best_sequence(me, opponent)
    except Exception as calc_e:
        print(f"Error calculating best sequence: {calc_e}")
        return

    # --- Calculate Opponent Hand Probabilities (Unchanged logic) ---
    known_entities = [entity.name for entity in me.hand]
    opponent_probs = estimate_opponent_hand_probabilities(known_entities, opponent_hand_count)

    # --- Output ---
    print("--- Recommended Action Sequence (Based on Current Weights) ---")
    if best_sequence_choices:
        # More detailed representation showing entity and chosen scope
        sequence_repr = []
        for entity, scope in best_sequence_choices:
            scope_str = f"(作用域:{scope})" if scope is not None else ""
            sequence_repr.append(f"{entity.name}{scope_str}")
        print(f"Sequence: {' -> '.join(sequence_repr)}")
        print(f"Expected Score: {best_score:.4f}") # Show more precision
    else:
        print("No recommended actions.")
    print("-" * 20)

    print("--- Opponent Hand Probability Estimate ---")
    if opponent_probs:
        sorted_probs = sorted(opponent_probs.items(), key=lambda item: item[1], reverse=True)
        for entity_name, prob in sorted_probs:
            print(f"  {entity_name}: {prob:.2%}")
    else:
        print("Cannot estimate probabilities (check deck/opponent hand size).")
    print("-" * 38)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SGS AI - Train influence weights or Run test scenario.")
    parser.add_argument('mode', choices=['train', 'run'], help="Mode: 'train' the weights or 'run' the test scenario.")
    parser.add_argument('--epochs', type=int, default=20, help="Number of training epochs (if mode is train).")
    parser.add_argument('--lr', type=float, default=0.01, help="Learning rate (if mode is train).")
    parser.add_argument('--batch_size', type=int, default=16, help="Batch size for training.")
    parser.add_argument('--dummy_samples', type=int, default=200, help="Number of dummy samples to generate for training.")

    args = parser.parse_args()

    # --- Perform Initialization Once ---
    if not initialize_system():
         print("System initialization failed. Exiting.")
         exit(1)
    # --------------------------------

    # Ensure prototypes are loaded before proceeding
    if not ge.ACTION_ENTITY_PROTOTYPES:
         print("Fatal Error: Entity prototypes failed to load after initialization. Exiting.")
         exit(1)

    if args.mode == 'train':
        print("\n=== Starting Training Mode ===")
        # Training loop handles weight loading/initialization internally via load_weights
        training_loop(
            prototypes=ge.ACTION_ENTITY_PROTOTYPES, # Pass loaded prototypes
            num_epochs=args.epochs,
            learning_rate=args.lr,
            batch_size=args.batch_size,
            num_dummy_samples=args.dummy_samples
        )
        print("Training finished. Weights saved to influence_weights.pth (if successful).")

    elif args.mode == 'run':
        print("\n=== Starting Run Mode ===")
        # Weights should already be loaded by initialize_system()
        if ge.influence_weights is None:
             print("Error: Weights not loaded correctly before running scenario. Check initialization.")
        else:
             run_test_scenario()

# --- END OF FILE main.py ---
