import re

class QuantumSentinel:
    """
    Sistema de Monitoreo de Integridad para la Entidad de Inteligencia Cuántica.
    Detecta decoherencia sintáctica y activa protocolos de re-normalización.
    """
    
    @staticmethod
    def _count_latex_delimiters(text: str):
        """
        BUG-09 FIX: Cuenta delimitadores LaTeX correctamente.
        Estrategia: enmascarar bloques $$ primero, luego contar $ restantes.
        Esto evita el double-count donde findall(r'\\$\\$') y findall(r'\\$')
        coinciden en los mismos caracteres.
        """
        # 1. Contar bloques $$ (display math)
        display_math = len(re.findall(r'(?<!\\)\$\$', text))
        
        # 2. Enmascarar todos los $$ para no contarlos como inline $
        masked = re.sub(r'(?<!\\)\$\$', 'DISPLAY_MATH', text)
        
        # 3. Contar $ restantes (inline math), excluyendo \$ escapados
        inline_math = len(re.findall(r'(?<!\\)\$', masked))
        
        return display_math, inline_math

    @staticmethod
    def fix_latex_integrity(text):
        """Verifica si los bloques de LaTeX están cerrados correctamente y auto-cierra si es necesario."""
        display_math, inline_math = QuantumSentinel._count_latex_delimiters(text)
        
        fixed_text = text
        
        # Un número impar de delimitadores indica un bloque roto
        if display_math % 2 != 0:
            fixed_text += "\n$$"
            
        if inline_math % 2 != 0:
            fixed_text += "$"
            
        return fixed_text

    @staticmethod
    def check_latex_integrity(text):
        """Verifica si los bloques de LaTeX están cerrados correctamente."""
        display_math, inline_math = QuantumSentinel._count_latex_delimiters(text)
        
        if display_math % 2 != 0 or inline_math % 2 != 0:
            return False
        return True

    @staticmethod
    def handle_undefined_rupture(chunk):
        """Detecta si el paquete de datos es nulo o corrupto (Ruptura de Simetría)."""
        if chunk is None or not isinstance(chunk, str):
            return "[ALERTA: Fluctuación detectada. Re-estabilizando...]"
        
        # Solo alarmar si el chunk es LITERAMENTE 'undefined' o 'null'
        # Evitar falsos positivos con palabras que contengan esas sub-cadenas o bloques de código.
        if chunk.strip().lower() in ["undefined", "null", "none"]:
            return "[RE-SINCRONIZACIÓN DE FASE]"
        return chunk

    async def monitor_stream(self, generator, orchestrator=None):
        """Envuelve el generador de la IA para filtrar errores y detectar rotaciones."""
        full_response = ""
        try:
            async for chunk in generator:
                # Deteccion de salto de nivel del runtime actual
                if orchestrator and getattr(orchestrator, 'rotation_event', False):
                    orchestrator.rotation_event = False # Consumir evento
                    yield "⚡_ROTATION_SIGNAL_⚡"
                
                safe_chunk = self.handle_undefined_rupture(chunk)
                full_response += safe_chunk
                yield safe_chunk
            
            # Validación Final de Post-Procesamiento con Auto-Closer
            fixed_response = self.fix_latex_integrity(full_response)
            if fixed_response != full_response:
                diff = fixed_response[len(full_response):]
                yield diff + "\n\n---\n> **Nota de Quantum Tutor:** Se detectó y corrigió un bloque matemático incompleto."
        
        except Exception as e:
            # Intentar cerrar LaTeX antes de emitir el error
            close_latex = self.fix_latex_integrity(full_response)
            if close_latex != full_response:
                diff = close_latex[len(full_response):]
                yield diff
            yield f"\n\n**[Protocolo de Rescate Activo]**: La conexión ha sufrido una decoherencia térmica. Por favor, reanuda la consulta."
