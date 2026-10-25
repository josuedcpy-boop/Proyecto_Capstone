# Reporte de auditoría — 8th Grade Final test

**Fecha:** 24-oct-2026
**Archivo auditado:** `data/raw/history/grade8_supplement/8th Grade Final test.docx`
**Herramienta:** `auditar_examen` (MCP) / `pipeline/audit/exam_review.py` — audita la forma de cualquier examen subido, no requiere que haya sido generado por este pipeline.

## Contexto (identificación de materia/estándares)

| | Resultado | Confianza |
|---|---|---|
| Materia | Historia (`history`) | 98.83% (modelo `boosting`) |
| Grado | 8° (inferido de la carpeta) | — |
| Estándar curricular | `CC` — Cambio y Continuidad | 78.2% (umbral 0.5) |

El estándar `CC` para 8° grado cubre, según `docs/estandares_y_mejores_practicas.md` §1.3, "Independencia y surgimiento de naciones americanas", con alineación documentada a temario como *"Colombus Trips"* y *"New World"* — coincide con el contenido real del examen (caída de Constantinopla, viajes de los hermanos Polo, Colón, exploración ibérica). La identificación de materia/estándar es consistente con el contenido.

## Resultado de la auditoría de forma: **NO APROBADO** (2 de 3 criterios fallan)

| Criterio | Resultado | Detalle |
|---|---|---|
| Puntuación total > 50 (heurística por DOK) | ❌ FALLA | Total: 15 puntos (1 pregunta detectada) — **ver limitación abajo, esta cifra no es confiable para este archivo** |
| Mínimo 4 tipos de parte distintos | ❌ FALLA | 1 tipo detectado: `opcion_multiple` |
| Sin preguntas casi duplicadas (dentro del mismo examen) | ✅ OK | Menos de 2 preguntas detectadas — no hay pares que comparar |

## Limitación honesta encontrada durante esta auditoría

El reporte automático dice "1 pregunta detectada", pero el examen real (confirmado leyendo el `.docx` directamente) tiene **~45 preguntas de opción múltiple**, todas sin numerar ("¿Cuál...?" en vez de "1. ¿Cuál...?").

El separador de preguntas (`pipeline/difficulty/splitter.py`) solo reconoce el inicio de una pregunta por un patrón de numeración explícita (`"1."`, `"2)"`, etc.) — limitación que el propio archivo ya documenta. Al no encontrar ninguna línea numerada, trata **todo el documento como una sola "pregunta"**, con dos consecuencias concretas en esta auditoría:

1. **Criterio 1 (puntuación) no es confiable para este archivo**: el "total: 15 puntos" corresponde a 1 bloque de texto gigante, no a las ~45 preguntas reales — no se puede concluir de aquí si el examen es "corto" o no.
2. **El perfil Bloom/DOK también queda distorsionado**: el clasificador (`pipeline/difficulty/bloom_dok_rules.py`) marcó el examen completo como `Crear | DOK4`, el nivel cognitivo más alto posible — pero el disparador real es la palabra **"create"** dentro de una opción incorrecta de una sola pregunta ("*d) to create a maritime school*"), no el verbo de la pregunta en sí. Con las ~45 preguntas fusionadas en un solo bloque, basta una palabra suelta en un distractor para dominar la clasificación de todo el examen — el mismo patrón de falso positivo que el README ya documenta en general para este clasificador.

El **criterio 2 (variedad de tipos de parte)** sí falla legítimamente, numeración aparte: la inspección manual confirma que el examen es 100% opción múltiple, sin pareo, verdadero/falso, respuesta corta ni ensayo — no depende del bug de separación.

**Sugerencia (no aplicada, a decisión del usuario):** si se quiere auditar de forma confiable exámenes sin numeración explícita como este, `split_questions` necesitaría una señal adicional de corte (ej. el patrón de opciones `a) ... b) ... c) ... d)` que ya reconoce `detect_part_type`, usado como límite de pregunta además de la numeración). No se modificó nada del pipeline para este reporte.

## Resumen

- La identificación de materia/estándar es razonable y consistente con el contenido.
- La auditoría de forma marca **NO APROBADO**, y al menos el criterio de variedad de tipos de pregunta es una falla real (examen 100% opción múltiple).
- El criterio de puntuación total, sin embargo, está invalidado para este archivo específico por la falta de numeración — no se puede confiar en el "15 puntos" reportado como reflejo del examen real de ~45 preguntas.
