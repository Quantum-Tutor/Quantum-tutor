import json
import os
import sys
import re

def build_dataset(log_path, output_path):
    sessions = {}
    
    if not os.path.exists(log_path):
        print(f"Log file not found: {log_path}")
        return
        
    with open(log_path, 'r', encoding='utf-8') as f:
        for idx, line in enumerate(f):
            try:
                # Búsqueda segura con Regex
                json_match = re.search(r'\{.*\}$', line.strip())
                if not json_match:
                    continue
                    
                event = json.loads(json_match.group())
                
                if "session_id" not in event or "event" not in event:
                    continue
                    
                sid = event["session_id"]
                session = sessions.setdefault(sid, {
                    "metrics": None,
                    "outcome": None,
                    "line_metrics": -1,
                    "line_outcome": -1
                })
                
                # Usamos el índice de la línea como proxy temporal (monotónico)
                if event["event"] == "SCHED_METRICS":
                    if session["line_metrics"] < idx:
                        session["metrics"] = event
                        session["line_metrics"] = idx
                elif event["event"] == "PIPELINE_OUTCOME":
                    if session["line_outcome"] < idx:
                        session["outcome"] = event
                        session["line_outcome"] = idx
            except Exception:
                pass
                
    dataset = []
    for sid, data in sessions.items():
        if data["metrics"] and data["outcome"]:
            m = data["metrics"]
            o = data["outcome"]
            
            w_score = m.get("scores", {}).get("wolfram", 0.0)
            r_score = m.get("scores", {}).get("rag", 0.0)
            
            dataset.append({
                "session_id": sid,
                "delta": w_score - r_score,  # CRÍTICO: Preservar el signo para el threshold
                "wolfram_score": w_score,
                "rag_score": r_score,
                "latency": o.get("total_latency"),
                "executed_wolfram": o.get("executed_wolfram", False),
                "success": o.get("success", False),
                "heuristic_agreement": m.get("heuristic_agreement", False),
                "confidence_delta": m.get("confidence_delta", 0.0)
            })
            
    with open(output_path, 'w', encoding='utf-8') as f:
        for row in dataset:
            f.write(json.dumps(row) + "\n")
            
    print(f"Dataset construido exitosamente: {len(dataset)} sesiones válidas extraídas en {os.path.basename(output_path)}")

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    log_file = os.path.join(base_dir, "quantum_tutor_system.log")
    out_file = os.path.join(base_dir, "scheduler_dataset.jsonl")
    build_dataset(log_file, out_file)
