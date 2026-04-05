import asyncio
from sentinel_monitor import QuantumSentinel

def test_sentinel():
    print("Testing QuantumSentinel...")
    
    # 1. Test check_latex_integrity
    valid_text = "Esto es un bloque $$ x^2 $$ y uno inline $y=mc$."
    broken_text_1 = "Bloque roto $$ x^2 y falta el cierre."
    broken_text_2 = "Inline roto $ y=mc y no cierra."
    
    assert QuantumSentinel.check_latex_integrity(valid_text) == True
    assert QuantumSentinel.check_latex_integrity(broken_text_1) == False
    assert QuantumSentinel.check_latex_integrity(broken_text_2) == False
    print("- Integrity Checks PASSED")
    
    # 2. Test fix_latex_integrity
    fixed_1 = QuantumSentinel.fix_latex_integrity(broken_text_1)
    fixed_2 = QuantumSentinel.fix_latex_integrity(broken_text_2)
    
    assert fixed_1.endswith("$$")
    assert fixed_2.endswith("$")
    assert QuantumSentinel.check_latex_integrity(fixed_1) == True
    assert QuantumSentinel.check_latex_integrity(fixed_2) == True
    print("- Auto-Closer PASSED")
    
    # 3. Test handle_undefined_rupture — actualizado para coincidir con sentinel v3.1
    EXPECTED_RUPTURE_MSG = "[RE-SINCRONIZACIÓN DE FASE]"
    EXPECTED_ALERT_MSG = "[ALERTA: Fluctuación detectada. Re-estabilizando...]"
    assert QuantumSentinel.handle_undefined_rupture("undefined") == EXPECTED_RUPTURE_MSG
    assert QuantumSentinel.handle_undefined_rupture("null") == EXPECTED_RUPTURE_MSG
    assert QuantumSentinel.handle_undefined_rupture(None) == EXPECTED_ALERT_MSG
    assert QuantumSentinel.handle_undefined_rupture("Valid chunk") == "Valid chunk"
    print("- Undefined Fallback PASSED")
    print("All tests passed.")

if __name__ == "__main__":
    test_sentinel()
