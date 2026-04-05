"""
Script archivado para depurar la inicialización temprana del orquestador.
Se mantiene solo como referencia histórica.
"""

import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    print(f"Root Directory: {ROOT_DIR}")
    from quantum_tutor_orchestrator import QuantumTutorOrchestrator
    
    print("Attempting to initialize QuantumTutorOrchestrator...")
    tutor = QuantumTutorOrchestrator(base_dir=ROOT_DIR)
    print("Success!")
    print(f"Base Dir: {tutor.base_dir}")
    print(f"Config Path: {tutor.config_path}")
    
except Exception as e:
    print(f"\nCRASH DETECTED: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
