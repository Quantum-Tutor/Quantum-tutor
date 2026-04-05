# Integridad de Datos

- No sobrescribir progreso sin validación previa
- Usar atomic writes para persistencia
- Evitar corrupción en entornos multi-proceso
- Mantener estricta consistencia entre:
  - `student_profile`
  - `learning_paths`
  - `evaluations`
