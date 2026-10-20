# Criterios de auditoría — Exámenes y Lecciones generadas

Contexto de referencia para el código de verificación/auditoría (próximo paso, pendiente de implementar). Define **qué** se audita y **por qué**, antes de escribir el código. Se apoya en lo ya construido: el módulo de validación (`pipeline/validation/`, reglas Haladyna + duplicados), el etiquetado de temas (`pipeline/tagging/`) y el marco de estándares (`docs/estandares_y_mejores_practicas.md`).

Última actualización: 2026-10-19.

---

## 1. Criterios para exámenes generados

### 1.1 Puntuación total > 50 puntos
Cada examen debe sumar más de 50 puntos en total.

**Gap actual:** `Question` (en `pipeline/schemas.py`) no tiene un campo de puntos. Hay que decidir cómo se asignan puntos antes de poder auditar esto — opciones: puntos fijos por pregunta, o puntos que escalan con el nivel Bloom/DOK (una pregunta de Analizar/DOK3 vale más que una de Recordar/DOK1, como ya hacen varios exámenes reales del banco, ej. "8th Grade Test - Colombus Trips.docx" da más peso a las preguntas de ensayo finales que al pareo de vocabulario).

### 1.2 Mínimo 4 partes distintas
El examen debe tener al menos 4 secciones de tipo distinto (ej. pareo de vocabulario, verdadero/falso, opción múltiple, respuesta corta/ensayo) — este patrón ya aparece en los exámenes reales del docente (ver `data/raw/history/grade8_supplement/8th Grade Test - Colombus Trips.docx`: tiene 5 partes — Vocabulary Match, Fill in the Blanks, True/False, Multiple Choice, Questions).

**Gap actual:** `Question` no tiene un campo de tipo/parte (`part_type`). Hay que añadirlo (ej. `pareo` | `verdadero_falso` | `opcion_multiple` | `respuesta_corta` | `ensayo` | `completar`) y hacer que la generación lo asigne, para poder contar cuántas partes distintas hay.

### 1.3 Cobertura de temas
La distribución de temas (estándares) del examen generado debe parecerse a la del material fuente — no basta con "cubrir algo", tiene que ser una distribución comparable, no concentrada en un solo estándar mientras el material fuente cubre varios.

**Cómo medirlo:** ya existe `pipeline/tagging/run.py` (`tag_document`, `document_coverage`) que produce un histograma de estándares por documento vía similaridad de embeddings. El chequeo sería: generar ese histograma para (a) el material fuente/examen de referencia y (b) las preguntas del examen generado, y comparar las dos distribuciones (ej. distancia coseno entre los vectores de conteo normalizados, o KL-divergence). Un umbral de similaridad mínima define "pasa"/"no pasa".

### 1.4 Sin fuga de respuesta ("answer leakage")
Ninguna pregunta generada debe revelar la respuesta correcta en su propio enunciado (ej. una pregunta de opción múltiple cuyo stem ya menciona la respuesta correcta, o una verdadero/falso que se auto-contesta por cómo está redactada).

**Gap actual:** `Question` no guarda las opciones de respuesta ni cuál es la correcta — solo el texto completo. Para auditar esto de forma confiable hace falta estructurar las preguntas de opción múltiple (stem + lista de opciones + índice de la correcta) en vez de un solo bloque de texto, así el chequeo puede comparar el stem contra el texto de la opción correcta (similaridad de texto/subcadena) sin ambigüedad. Sin esa estructura, solo se podría hacer una heurística débil (buscar si el stem contiene texto muy similar a la "respuesta esperada" inferida del contexto RAG, lo cual es frágil).

### 1.5 Sin preguntas casi duplicadas
Ninguna pregunta generada debe ser casi idéntica a otra.

**Ya parcialmente implementado:** `pipeline/validation/heuristics.py` (`check_duplicates`) ya compara preguntas generadas contra el banco **histórico** vía similaridad de embeddings (umbral 0.90). **Falta:** la misma comparación pero **entre las preguntas generadas del mismo examen entre sí** (duplicados internos), que hoy no se chequea.

---

## 2. Criterios para lecciones generadas

⚠️ El generador de lecciones **todavía no existe** (solo se generan exámenes, ver hoja de ruta en `README.md`). Estos criterios quedan documentados ahora para que el generador de lecciones, cuando se construya, ya nazca diseñado para cumplirlos — no es una auditoría que se pueda correr hoy.

### 2.1 Orden lógico
La lección debe seguir el orden de progresión temática definido por los estándares de grado (ej. los códigos `CC.5.1`, `CC.5.2`... en `pipeline/standards/pr_estudios_sociales.yaml` siguen un orden narrativo/cronológico) y/o el orden en que aparece el tema en el material fuente real del docente.

### 2.2 Cumple los estándares postulados en la data
Cada lección debe declarar explícitamente a qué código(s) de estándar corresponde (de `pipeline/standards/*.yaml`), igual que ya hacemos con el etiquetado de exámenes — no puede ser una lección "genérica" sin trazabilidad a un estándar real.

### 2.3 Correlación del tema
El contenido de la lección debe estar temáticamente alineado con el material de referencia de ese tema/grado — mismo mecanismo de anclaje por `tema` + contexto RAG garantizado que ya se implementó para generación de exámenes (ver `pipeline/generation/run.py`, parámetro `reference_text`).

### 2.4 Incluye práctica para los estudiantes
La lección no puede ser puramente expositiva — debe incluir al menos un ejercicio de práctica (ej. preguntas de aplicación, actividad corta) donde el estudiante use el contenido, no solo lo lea.

### 2.5 Chequeos periódicos de aprendizaje
La lección debe incluir preguntas de verificación ("exit ticket"/chequeo formativo) distribuidas **a lo largo** del contenido (no solo una al final) para confirmar que el estudiante va entendiendo antes de avanzar al siguiente punto.

---

## 3. Qué falta antes de poder escribir el código de auditoría

Estos son los bloqueos reales, no decisiones de implementación menores — hay que resolverlos (o decidir una heurística temporal) antes de que el código de auditoría de exámenes (sección 1) tenga sentido:

1. **Esquema de puntos** (criterio 1.1): decidir la regla de asignación de puntos por pregunta.
2. **Campo de tipo de pregunta/parte** (criterio 1.2): añadir `part_type` a `Question` y que la generación lo asigne.
3. **Estructura de opción múltiple** (criterio 1.4): decidir si vale la pena estructurar preguntas de opción múltiple (stem + opciones + respuesta correcta) para poder chequear fuga de respuesta de forma confiable, o aceptar una heurística más débil por ahora.

El resto (1.3 cobertura de temas, 1.5 duplicados internos) se puede construir ya mismo reutilizando código existente, sin bloqueos.

Los criterios de lecciones (sección 2) no bloquean nada todavía porque el generador de lecciones no existe — quedan como especificación para cuando se construya.
