# Código archivado: generación de exámenes/lecciones

**Archivado el 2026-10-20.** El capstone pivoteó de "generar exámenes/lecciones calibrados
por dificultad y cobertura de temas" a **"identificar, con un modelo entrenado, de qué
materia es un examen y qué estándares curriculares cumple"**. Esta carpeta conserva el
trabajo de generación tal cual estaba al momento del pivote, para no perderlo — no para
seguir corriendo desde aquí.

## Qué hay aquí

- `pipeline/generation/` — generación de preguntas nuevas vía RAG + LLM (`generate_exam`).
- `pipeline/assemble/` — ensamblado del examen generado a `.docx` (`assemble_exam`).
- `pipeline/validation/` — heurísticas de redacción (Haladyna), duplicados, y el paso
  opcional de "LLM-juez" (`validate_exam`).
- `pipeline/audit/` — los 5 criterios de auditoría de un examen generado (`audit_exam`),
  re-parseo del `.docx` ya ensamblado, y el reporte `.md`.
- `pipeline/llm/` — los 3 proveedores de LLM (mock/Ollama/Anthropic) que usaban generación
  y validación. Nada del código activo del proyecto depende de esto.
- `tests/` — las pruebas que solo cubrían lo anterior (`test_exam_audit.py`,
  `test_mock_provider.py`).
- `docs/criterios_auditoria.md` — la especificación de los criterios de auditoría de
  exámenes y (para cuando existiera) lecciones generadas.
- `Examen_generado/`, `Reportes_auditoria/` — los `.docx`/`.md` que ese flujo había
  producido hasta el momento del pivote.

## Por qué no es un paquete importable tal cual

Esta carpeta ya no está bajo el paquete real `pipeline/` de la raíz, así que
`from pipeline.generation.run import generate_exam` (y similares) **no funcionan** desde
aquí — es una foto de referencia, no un módulo activo en paralelo. Esto es intencional:
mantenerlo "medio vivo" (importable pero no mantenido) sería más confuso que útil.

## Cómo reactivarlo si se necesita

1. Mover de vuelta a la raíz real del paquete: `pipeline/generation/`, `pipeline/assemble/`,
   `pipeline/validation/`, `pipeline/audit/`, `pipeline/llm/` (con `git mv`, para conservar
   el historial otra vez).
2. En `pipeline/config.py`, restaurar `EXAMEN_GENERADO_DIR`, `LECCION_GENERADA_DIR`,
   `REPORTES_AUDITORIA_DIR`, y en `Settings`/`get_settings()` los campos `llm_provider`,
   `ollama_model`, `ollama_host`, `anthropic_api_key`, `anthropic_model`.
3. En `pipeline/schemas.py`, restaurar `ValidationIssue`, `GeneratedExam`,
   `AuditCriterionResult`, `AuditReport`, y en `Question` los campos `options`/
   `correct_option_index`.
4. Reconectar en `pipeline/cli.py` los comandos `generate`/`audit`/`run-all`, en
   `mcp_server.py` las herramientas `generar_examen`/`auditar_examen`, y en `app.py` las
   tabs "Generar examen"/"Auditar examen".
5. Restaurar `anthropic` y `requests` en `requirements.txt`, y las variables
   `LLM_PROVIDER`/`OLLAMA_*`/`ANTHROPIC_*` en `.env.example`.

Para la versión íntegra y exacta de todo lo anterior (antes de que cualquiera de estos
pasos se deshiciera), ver el commit `c578a59` (el último antes del pivote) o cualquier
commit anterior en el historial de git.
