import threading
import requests
import time
import random
import sys

BASE_URL = "http://127.0.0.1:8000"

stats = {
    "success": 0,
    "fail_500": 0,
    "fail_other": 0,
    "idor_blocked": 0,
    "xss_handled": 0,
    "pedagogy_handled": 0,
}

lock = threading.Lock()

def _record(stat):
    with lock:
        stats[stat] += 1

def hit_guardar_progreso(student_id_prefix, thread_id):
    student_id = f"{student_id_prefix}_{thread_id}"
    for i in range(25):
        try:
            res = requests.post(f"{BASE_URL}/api/guardar-progreso", json={
                "student_id": student_id,
                "node_id": "math_basics",
                "question_id": f"q_{i}",
                "correct": random.choice([True, False]),
                "mastery_score": random.uniform(0.1, 0.9),
                "completed": False,
                "time_spent_seconds": 30,
                "reflection": "test",
            }, timeout=10)
            if res.status_code == 200:
                _record("success")
            elif res.status_code >= 500:
                _record("fail_500")
            else:
                _record("fail_other")
        except Exception:
            _record("fail_other")

def test_idor():
    for _ in range(5):
        try:
            # We don't have internal auth header here, so it should fallback to 'anonymous'
            res = requests.get(f"{BASE_URL}/api/learning-kpis?student_id=target_victim_123", timeout=10)
            data = res.json()
            if data.get("student_id") == "anonymous" or res.status_code in [401, 403, 400]:
                _record("idor_blocked")
            else:
                print(f"[IDOR ALERT] Acceso no bloqueado. Data: {data}")
        except Exception as e:
            pass

def test_xss():
    try:
        # Peticion de chat con XSS 
        payload = {"message": "<img src=x onerror=alert('xss')>", "history": [], "user_id": "test_xss_user"}
        res = requests.post(f"{BASE_URL}/api/chat", json=payload, timeout=25)
        # Lo importante es que el backend devuelva 200 sin explotar, la sanitizacion XSS principal 
        # (DOMPurify) pasa en JS, el backend deberia al menos contestar con texto.
        if res.status_code == 200:
            _record("xss_handled")
    except Exception:
        pass

def test_pedagogy_fuzzing():
    spam_text = "esto es un test incoherente x 1000 " * 100
    try:
        res = requests.post(f"{BASE_URL}/api/evaluar-respuesta", json={
            "student_id": "fuzzing_student",
            "question_id": "q1",
            "answer": spam_text
        }, timeout=25)
        
        if res.status_code == 200:
            _record("pedagogy_handled")
        else:
            print(f"[FUZZING ALERT] Respuesta fallo HTTP {res.status_code}")
    except Exception:
        pass

def main():
    print("Iniciando Escenario de Carga (Simulacion Preflight)")
    t0 = time.time()
    
    threads = []
    
    # 20 threads writing to progressing simultaneously (Race condition test)
    for i in range(20):
        t = threading.Thread(target=hit_guardar_progreso, args=("stu_agresivo", i))
        threads.append(t)
    
    # Add Security and Fuzzing threads
    t_idor = threading.Thread(target=test_idor)
    threads.append(t_idor)
    
    for _ in range(3):
        t_xss = threading.Thread(target=test_xss)
        threads.append(t_xss)
    
    for _ in range(5):
        t_fuzz = threading.Thread(target=test_pedagogy_fuzzing)
        threads.append(t_fuzz)
    
    for t in threads:
        t.start()
    for t in threads:
        t.join()
        
    t1 = time.time()
    
    print("="*40)
    print("REPORTE PREFLIGHT - FASE 1")
    print("="*40)
    print(f"Tiempo Total: {t1-t0:.2f}s")
    print(f"Requests Exitosos: {stats['success']}")
    print(f"Errores Servidor (500): {stats['fail_500']}")
    print(f"Errores Cliente/Timeout: {stats['fail_other']}")
    print(f"IDOR bloqueos exitosos: {stats['idor_blocked']}")
    print(f"XSS asimilados backend: {stats['xss_handled']}")
    print(f"Fuzzing pedagógico estable: {stats['pedagogy_handled']}")

if __name__ == "__main__":
    main()
