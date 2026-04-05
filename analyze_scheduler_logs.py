import json
import argparse
import re
from collections import Counter

def pseudo_ground_truth(query):
    """
    Heurística original usada como pseudo-ground-truth.
    """
    pattern = r"(∫|\\int|d/dx|∑|\\sum|sqrt|\\sqrt|[\d\w\(\)]+\s*[\+\-\*/\^]\s*[\d\w\(\)]+)"
    keywords = ["integral", "normalización", "derivar", "conmutador", "integrate", "commutator", "calcular"]
    has_math_structure = bool(re.search(pattern, query))
    has_keyword = any(k in query.lower().split() for k in keywords)
    return has_math_structure or has_keyword

def main(log_file):
    stats = {
        "tp": 0, # Ambas activan Wolfram
        "fp": 0, # Scheduler activa, heurística no (OVERUSE)
        "fn": 0, # Heurística activa, scheduler no (MISS)
        "tn": 0  # Ninguna activa
    }
    total_requests = 0

    try:
        with open(log_file, "r", encoding="utf-8") as f:
            for line_number, line in enumerate(f, 1):
                if "SCHED_METRICS" in line:
                    try:
                        json_str = line[line.find("{"):line.rfind("}")+1]
                        data = json.loads(json_str)
                        
                        query = data.get("query", "")
                        scheduler_wl = "wolfram" in data.get("selected", [])
                        heuristic_wl = pseudo_ground_truth(query)
                        
                        total_requests += 1
                        
                        if heuristic_wl and scheduler_wl:
                            stats["tp"] += 1
                        elif not heuristic_wl and scheduler_wl:
                            stats["fp"] += 1
                        elif heuristic_wl and not scheduler_wl:
                            stats["fn"] += 1
                        else:
                            stats["tn"] += 1
                            
                    except json.JSONDecodeError:
                        continue
    except FileNotFoundError:
        print(f"Error: {log_file} not found.")
        return

    print("\n=== Scheduler Performance Analysis (Heuristic Baseline) ===")
    if total_requests == 0:
        print("No SCHED_METRICS events found in log.")
        return

    precision = stats["tp"] / (stats["tp"] + stats["fp"]) if (stats["tp"] + stats["fp"]) > 0 else 0
    recall = stats["tp"] / (stats["tp"] + stats["fn"]) if (stats["tp"] + stats["fn"]) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

    miss_rate = (stats["fn"] / total_requests) * 100
    overuse_rate = (stats["fp"] / total_requests) * 100

    print(f"Total Requests Analyzed: {total_requests}")
    print(f"TP: {stats['tp']} | FP: {stats['fp']} | FN: {stats['fn']} | TN: {stats['tn']}")
    print("-" * 40)
    print(f"Precision: {precision:.3f}")
    print(f"Recall:    {recall:.3f} (Goal: > 0.90)")
    print(f"F1-Score:  {f1:.3f}")
    print("-" * 40)
    print(f"MISS Rate (FN):    {miss_rate:.1f}%")
    print(f"OVERUSE Rate (FP): {overuse_rate:.1f}% (Goal: < 15%)")
    
    print("\n=== Tuning Recommendations ===")
    if recall < 0.90:
        print("[!] Recommendation: INCREASE Wolfram aggressiveness. Add missing keywords to `is_computation` or broaden `math_pattern`.")
    elif overuse_rate > 15:
        print("[!] Recommendation: DECREASE noise. Reduce base weights or check for overly broad features.")
    else:
        print("[+] Recommendation: System is within performance targets.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze scheduler logs for Precision/Recall.")
    parser.add_argument("--log", default="quantum_tutor_system.log", help="Path to the log file.")
    args = parser.parse_args()
    
    main(args.log)
