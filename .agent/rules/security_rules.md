# Reglas de Seguridad

- Nunca confiar en `student_id` desde el cliente
- Derivar identidad exclusivamente desde sesión autenticada
- Proteger endpoints críticos:
  - `/api/learning-insights`
  - `/api/learning-kpis`
  - `/api/learning-cohort-*`
- Sanitizar TODO contenido renderizado (XSS → DOMPurify)
- No exponer API keys ni tokens en frontend
- Validar roles estrictamente (student, professor, admin)
