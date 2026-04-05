import json
import os
import sys
import time

def train_adaptive_scheduler(dataset_path, output_path):
    if not os.path.exists(dataset_path):
        print(f"Error: Dataset {dataset_path} no encontrado.")
        return
        
    data = []
    with open(dataset_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
                
    dataset_size = len(data)
    # [GUARDRAIL 1] Minimum data threshold (1 para lab/dev, 1000 en prod)
    if dataset_size < 1:  
        print(f"Abortando entrenamiento: data insuficiente ({dataset_size} registros).")
        return
        
    # [GUARDRAIL 2] Freeze Window (Evitar overfitting con updates muy frecuentes - desactivado en DEV)
    if os.path.exists(output_path):
        mod_time = os.path.getmtime(output_path)
        # if time.time() - mod_time < 3600:
        #    print("Aviso: Ventana de congelamiento (1h) activa. Update ignorado.")
        #    return
            
    old_theta = 0.2
    old_expected_success = 0.0
    old_expected_usage = 0.0
    if os.path.exists(output_path):
        try:
            with open(output_path, 'r') as f:
                old_conf = json.load(f)
                old_theta = old_conf.get("threshold", 0.2)
                old_expected_success = old_conf.get("expected_success", 0.0)
                old_expected_usage = old_conf.get("expected_wolfram_usage", 0.0)
        except Exception:
            pass
            
    # Extraer únicos deltas observados y discretizarlos (evita explosión en big data)
    unique_deltas = sorted(list(set(round(row["delta"], 2) for row in data)))
    if not unique_deltas:
        unique_deltas = [0.1, 0.2, 0.3, 0.4, 0.5]
    
    best_theta = old_theta
    best_score = -999.0
    best_stats = {}
    
    # Búsqueda exhaustiva 1D sobre deltas discretos
    for theta in unique_deltas:
        clamped_theta = max(0.1, min(theta, 0.7))
        
        success_count = 0
        valid_count = 0
        wolfram_calls = 0
        
        for row in data:
            decision_wolfram = row["delta"] > clamped_theta
            
            if decision_wolfram:
                wolfram_calls += 1
                
            # Off-Policy Evaluation riguroso (solo contamos cuando nuestra policy empata con la realidad logueada)
            if decision_wolfram == row["executed_wolfram"]:
                success_count += 1 if row["success"] else 0
                valid_count += 1
                
        # [SUAVIZADO ESTADÍSTICO] Laplace smoothing sobre los casos válidos evaluados
        success_rate = (success_count + 1) / (valid_count + 2)
        wolfram_usage = wolfram_calls / dataset_size
        
        # [FUNCIÓN OBJETIVO] Cost-aware penalizado
        usage_penalty = 0.1 * wolfram_usage
        
        # Anti-degeneración ("Always Wolfram")
        if wolfram_usage > 0.8:
            usage_penalty += 2.0 
            
        score = success_rate - usage_penalty
        
        if score > best_score:
            best_score = score
            best_theta = clamped_theta
            best_stats = {
                "success_rate": success_rate,
                "wolfram_usage": wolfram_usage
            }
            
    print(f"DEBUG: Grid Search Result -> Theta={best_theta:.2f}, Success={best_stats.get('success_rate', 0):.2f}, Usage={best_stats.get('wolfram_usage', 0):.2f}, Score={best_score:.2f}")

    # [GUARDRAIL 4] Filtrado Semántico / Insignificativo
    success_delta = best_stats.get("success_rate", 0) - old_expected_success
    usage_delta = best_stats.get("wolfram_usage", 0) - old_expected_usage
    
    if abs(success_delta) < 0.01 and abs(usage_delta) < 0.02 and abs(best_theta - old_theta) < 0.2:
        print("Update ignorado: mejora de metrica sub-critica (<1% success delta y <2% usage delta).")
        best_theta = old_theta
        
    # [GUARDRAIL 5] Drift Limit (Amplitud máxima de salto)
    if abs(best_theta - old_theta) > 0.2:
        print(f"[!] Alerta Drift: Salto brusco propuesto ({old_theta:.2f} -> {best_theta:.2f}). Limitando a 0.1 max step.")
        best_theta = old_theta + 0.1 if best_theta > old_theta else old_theta - 0.1
            
    out_data = {
        "threshold": round(best_theta, 3),
        "trained_at": time.time(),
        "dataset_size": dataset_size,
        "expected_success": round(best_stats.get("success_rate", 0.0), 3),
        "expected_wolfram_usage": round(best_stats.get("wolfram_usage", 0.0), 3)
    }
    
    # Escritura Atómica (.tmp rename)
    tmp_path = output_path + ".tmp"
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(out_data, f, indent=2)
        
    os.replace(tmp_path, output_path)
    print(f"[+] Entrenamiento completado. Nuevo Threshold (theta): {best_theta:.3f} | Score: {best_score:.3f}")

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    dataset_file = os.path.join(base_dir, "scheduler_dataset.jsonl")
    thresholds_file = os.path.join(base_dir, "scheduler_thresholds.json")
    train_adaptive_scheduler(dataset_file, thresholds_file)
