import numpy as np
from relational_engine import RelationalMind

def test_energy_stability():
    print("[TEST] Initializing RelationalMind...")
    rm = RelationalMind()
    
    print("[TEST] Simulating 50 turns of 'decay-only' (no new topics)...")
    for i in range(50):
        # Update with a dummy topic to trigger decay
        rm.update_state("General")
    
    final_energy = rm.E
    min_e = np.min(final_energy)
    max_e = np.max(final_energy)
    
    print(f"\nFINAL ENERGY STATE:")
    print(f"  Min: {min_e:.4f}")
    print(f"  Max: {max_e:.4f}")
    
    if min_e >= 0.01:
        print("\n[SUCCESS] ENERGY_FLOOR protected the system from depletion.")
    else:
        print("\n[FAIL] Energy fell below 0.01 floor.")

    print("\n[TEST] Verifying diffusion (activating one topic)...")
    rm.update_state("Pozo Infinito", interaction_weight=0.8)
    rm.update_state("Pozo Infinito", interaction_weight=0.8) # Saturate it
    
    energy_after = rm.E
    idx = rm.concepts.index("Pozo Infinito")
    print(f"  Topic 'Pozo Infinito' energy: {energy_after[idx]:.4f}")
    
    # Check neighbors (Should have higher than floor)
    neighbors_count = np.sum(energy_after > 0.01)
    print(f"  Nodes above floor after diffusion: {neighbors_count}")
    
    if neighbors_count > 1:
        print("[SUCCESS] Energy diffusion is active.")
    else:
        print("[WARNING] No diffusion detected (might be due to low initial affinity).")

if __name__ == "__main__":
    test_energy_stability()
