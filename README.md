# Identificador de Materia y Estándares en Exámenes — Capstone MAI540

## Objetivo

Dado un examen (del docente o subido por cualquiera), este proyecto identifica, con modelos entrenados sobre un **banco de exámenes y materiales reales** (Historia y Tecnología, 5°-8°), **de qué materia es** y **qué estándares curriculares cumple** — ancladas en los estándares oficiales (Puerto Rico y EE.UU.) y apoyado en un perfil de dificultad Bloom/DOK como señal de contexto adicional.

## Estado actual

El pipeline completo (ingesta → etiquetado de temas → perfil de dificultad → entrenamiento de los clasificadores de materia/estándares → identificación de un examen nuevo) corre de punta a punta por CLI, **sin necesidad de ningún LLM ni API key** — todo es embeddings locales (`sentence-transformers`) + `scikit-learn`. Ver [Cómo correr el pipeline](#cómo-correr-el-pipeline).

| Carpeta | Contenido |
|---|---|
| `data/raw/` | Copias de exámenes, guías de estudio y materiales de tema reales del docente (Historia 5°-8°, Tecnología 5°-8°) |
| `docs/estandares_y_mejores_practicas.md` | Estándares oficiales de PR y EE.UU. (Estudios Sociales y Tecnología/CS) + mejores prácticas de diseño de lecciones y exámenes |
| `pipeline/` | Código del pipeline (ingesta, estándares, embeddings/RAG, etiquetado, perfil de dificultad, clasificadores ML de materia/estándares/dificultad) |
| `tests/` | Pruebas automáticas (`pytest`) de las partes deterministas del pipeline |
| `_deprecated/` | Generación de exámenes/lecciones calibrados por dificultad — el enfoque original del capstone, archivado (no borrado) el 2026-10-20 al pivotear hacia identificación de materia/estándares. Ver `_deprecated/README.md`. |

## Estructura de `data/raw/`

```
data/raw/
├── history/
│   ├── top_level/                 # Exámenes y reviews generales 5°-8°
│   ├── grade5_supplement/          # Material de tema 5° (2024-25)
│   ├── grade6_supplement/          # Material de tema 6° (2024-25)
│   ├── grade7_supplement/          # Material de tema 7° (2024-25)
│   ├── grade8_supplement/          # Material de tema 8° (2024-25)
│   ├── grade5_2025-26/             # Exámenes/guías 5° (año actual)
│   └── middle_school_2025-26/      # Exámenes/guías 6° y 8° (año actual)
├── technology/
│   ├── top_level/                  # Exámenes generales
│   ├── intermedia/                 # Material Tecnología Intermedia (2023-24)
│   └── intermedia_2025-26/         # Material Tecnología Intermedia (año actual)
└── textbook_text/
    └── grade8/                     # Texto extraído de los capítulos del libro de 8°
```

## Cómo añadir tus propios exámenes o materiales

El sistema está diseñado para **aprender de exámenes y materiales reales**: entre más completo el banco histórico, mejor identifican los modelos materia y estándares en exámenes nuevos. Cualquier docente puede añadir su propio material siguiendo estos pasos:

1. **Ubica la carpeta de la materia y grado correspondiente** dentro de `data/raw/` (ej. `data/raw/history/grade7_supplement/`). Si no existe una carpeta para tu materia/grado, créala siguiendo el mismo patrón de nombres.
2. **Copia tus archivos tal cual** — exámenes, guías de repaso ("review"), pruebas cortas, apuntes de tema. Formatos aceptados: `.docx`, `.pdf`, `.xlsx`, `.pptx`.
   - Si el PDF es un documento digital (no un escaneo), su texto se puede extraer directamente.
   - Si el PDF es un **escaneo de imagen** (por ejemplo, páginas fotografiadas de un libro), el sistema no puede leer su contenido sin pasar primero por OCR (reconocimiento óptico de caracteres) — avisa si tienes material así para evaluar esa opción.
3. **Evita archivos con información identificable de estudiantes** (notas, informes individuales, trabajos con nombres) — este banco es solo de material de enseñanza (exámenes/temario), no de resultados de alumnos.
4. Una vez añadido el material, corre `python -m pipeline.cli ingest` (y luego `tag`) para incorporarlo al banco de temas y dificultad histórica — ver [Cómo correr el pipeline](#cómo-correr-el-pipeline).

## Cómo correr el pipeline

### Instalación

Requiere Python 3.11+.

```bash
python -m venv .venv
source .venv/Scripts/activate      # Windows (PowerShell): .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env                # opcional — solo trae EMBEDDING_MODEL, no hace falta tocarlo
```

### Comandos

```bash
python -m pipeline.cli ingest                                   # extrae texto de data/raw/ -> data/processed/documents/
python -m pipeline.cli tag                                      # cobertura de temas por materia/grado (sin LLM, solo embeddings)
python -m pipeline.cli profile "data/raw/history/top_level/History Test 7th.docx"   # tabla Bloom x DOK de un examen puntual
python -m pipeline.cli topic-balance --materia historia --grado 8                      # agrupa preguntas históricas (k-means+PCA) y marca temas sobre/sub-representados
python -m pipeline.cli ml-bloom-eval                                                   # entrena/evalúa (CV + grid search) el clasificador de nivel Bloom por pregunta
python -m pipeline.cli ml-subject-eval                                                 # entrena/evalúa el clasificador de MATERIA a nivel de examen completo
python -m pipeline.cli ml-estandares-eval --materia historia                           # entrena/evalúa el clasificador multi-etiqueta de ESTÁNDARES para una materia
python -m pipeline.cli predecir-examen "archivo.docx" --objetivo materia               # identifica la materia de un examen nuevo
python -m pipeline.cli predecir-examen "archivo.docx" --objetivo estandares            # identifica los estándares que cumple (infiere materia si no se da --materia)
python -m pipeline.cli predecir-examen "archivo.docx" --objetivo dificultad            # perfil Bloom/DOK por pregunta de un examen nuevo
```

### Niveles Bloom y Webb's DOK (qué mide cada uno)

El comando `profile` (y `predecir-examen --objetivo dificultad`) clasifica cada pregunta en dos marcos complementarios, usados como señal de contexto adicional junto a materia/estándares:

- **Bloom revisada** (Anderson & Krathwohl, 2001): mide **qué tipo de proceso cognitivo** pide la pregunta — Recordar, Comprender, Aplicar, Analizar, Evaluar, Crear (de menor a mayor nivel).
- **Webb's Depth of Knowledge (DOK)**: mide la **profundidad/complejidad** de la tarea, independientemente del verbo usado — una pregunta puede usar el verbo "explica" y aun así ser DOK 1 o DOK 2 según qué tan rutinaria sea.

| DOK | Nombre | Qué implica | Ejemplo |
|---|---|---|---|
| 1 | Recall | Hecho memorizado, un solo paso | Definir, identificar una fecha |
| 2 | Skill/Concept | Aplicar un procedimiento conocido, 2+ pasos | Resumir un capítulo, resolver un cálculo |
| 3 | Strategic Thinking | Razonamiento abstracto, justificación, más de una respuesta válida | Diseñar un experimento, defender una postura |
| 4 | Extended Thinking | Síntesis de varias fuentes, transferencia entre dominios, trabajo extendido | Escribir un ensayo original con múltiples fuentes |

**Cómo lo calcula el pipeline (honestamente, sin LLM):** `pipeline/difficulty/bloom_dok_rules.py` es una heurística de palabras clave — busca el verbo de mayor nivel cognitivo en el texto de la pregunta y de ahí **deriva el DOK directamente del nivel Bloom detectado** (ej. "Crear" → DOK 4, "Aplicar" → DOK 2). No evalúa la complejidad real de la tarea de forma independiente del verbo, que es la distinción que Webb's DOK busca capturar en teoría — es una simplificación práctica, no una medición psicométrica validada. Si una pregunta de opción múltiple no usa ningún verbo reconocido (ej. "¿Cuál de los siguientes...?"), cae por defecto a Recordar/DOK 1. Detalle completo de ambos marcos en [`docs/estandares_y_mejores_practicas.md`](docs/estandares_y_mejores_practicas.md) sección 6.

### Identificar materia y estándares de un examen nuevo

`predecir-examen --objetivo materia` entrena el clasificador de materia con el banco actual (reentrena desde cero cada vez, ~1 min) y devuelve **una sola predicción para el examen completo** (no por pregunta, ya que la materia no varía dentro de un mismo examen) con su confianza.

`predecir-examen --objetivo estandares [--materia <historia|tecnologia>]` identifica qué estándares curriculares cumple el examen (multi-etiqueta — puede cumplir varios a la vez). Si no se da `--materia`, primero se infiere automáticamente con el clasificador de materia.

**Limitación honesta de los estándares (léase antes de confiar en los resultados):** no existe ninguna verdad de terreno humana sobre qué estándares cumple cada examen histórico. Las etiquetas de entrenamiento son **pseudo-etiquetas** producidas por el etiquetado por similaridad de embeddings que ya existía (`pipeline/tagging/run.py`, comando `tag`) — el nuevo clasificador (`pipeline/ml/standards_classifier.py`) aprende a reproducir esa heurística desde texto crudo (TF-IDF), no es una validación independiente. Con ~20 códigos de estándar repartidos entre ~130 documentos tipo examen (96 historia / 34 tecnología), muchos códigos tienen muy pocos documentos positivos — los resultados de `ml-estandares-eval` por código con poco soporte deben leerse con mucha cautela (ver esa salida: varios códigos quedan en 0.00 de F1 simplemente por tener 0-3 documentos de soporte).

La materia, en cambio, sí tiene verdad de terreno real (viene de la carpeta de origen en `data/raw/<subject>/...`), no es una pseudo-etiqueta.

Lo mismo está disponible sin terminal: herramientas MCP `identificar_materia`/`identificar_estandares`, o la pestaña "Identificar examen" de `streamlit run app.py`.

### Pruebas

```bash
pytest
```

Cubre extractores, el separador de preguntas, las reglas Bloom/DOK, balance de temas, y los clasificadores ML de dificultad/materia/estándares — no requiere red ni ningún LLM.

### Servidor MCP

`mcp_server.py` expone el pipeline (ingesta, etiquetado de temas, balance de temas, perfil de dificultad, y los clasificadores de materia/estándares/dificultad) como herramientas MCP, para orquestarlo conversacionalmente desde una sesión de Claude en vez de por comandos sueltos.

**Opción 1 — desde Claude Code en este proyecto (recomendado, no requiere arrancarlo a mano):** ya está conectado vía `.mcp.json` en la raíz del repo. Basta con abrir (o reabrir) Claude Code con esta carpeta como directorio de trabajo para que las herramientas `mcp__capstone-pipeline__*` (`ingerir_materiales`, `etiquetar_temas`, `verificar_cobertura_temas`, `clasificar_dificultad`, `identificar_materia`, `identificar_estandares`, `construir_banco_examenes`, `entrenar_clasificador_dificultad`, `entrenar_clasificador_materia`, `entrenar_clasificador_estandares`, `predecir_dificultad`) aparezcan disponibles automáticamente — Claude Code arranca el proceso del servidor por su cuenta. Si no aparecen, correr `/mcp` dentro de la sesión para ver el estado de la conexión.

**Opción 2 — correrlo a mano (para otro cliente MCP, o para probarlo suelto):**
```bash
python mcp_server.py                          # local (stdio) — el mismo modo que usa .mcp.json
python mcp_server.py --http --port 8000       # como servidor web, accesible por red en http://<host>:8000/mcp
```
El modo `--http` no es una página para abrir en el navegador — es el protocolo MCP sobre HTTP, pensado para que otro cliente MCP (no un navegador) se conecte de forma remota en vez de solo desde esta terminal.

### Interfaz web (Streamlit)

Para usar el pipeline desde el navegador con botones en vez de la terminal:
```bash
streamlit run app.py
```
Abre `http://localhost:8501` con pestañas para identificar materia/estándares de un examen subido, ver el balance de temas, entrenar/evaluar los 3 clasificadores ML (dificultad/materia/estándares), e ingerir/etiquetar materiales — todo reutilizando las mismas funciones que `pipeline/cli.py` y `mcp_server.py`.

### Modelos supervisados (ML) — y sus limitaciones honestas

Los tres clasificadores comparten el mismo motor genérico TF-IDF + scikit-learn (`pipeline/ml/bloom_classifier.py` para dificultad y materia, `pipeline/ml/standards_classifier.py` para estándares):

- **Dificultad (nivel Bloom) por pregunta** (`ml-bloom-eval`): compara 5 modelos (línea base de clase mayoritaria, regresión logística, árbol de decisión, Random Forest, boosting — con búsqueda de hiperparámetros para los dos últimos), con validación cruzada **agrupada por examen** y evaluación en exámenes nunca vistos. **Limitación:** las etiquetas de entrenamiento son la salida de la heurística de reglas del propio proyecto (`pipeline/difficulty/bloom_dok_rules.py`), no juicio humano independiente — el experimento mide si un modelo de texto puede *aprender a reproducir* ese criterio, no es una validación independiente. Esto además destapó una imprecisión real en la heurística: palabras como "create"/"creation" dentro de preguntas puramente factuales se clasifican como nivel "Crear" solo por contener esa raíz — mejora pendiente a `bloom_dok_rules.py`, no corregida todavía.
- **Materia a nivel de examen completo** (`ml-subject-eval`): mismo motor de comparación de 5 modelos, pero con una fila por documento completo (no por pregunta) — materia no varía dentro de un mismo examen. A diferencia de Bloom, esta etiqueta **sí es verdad de terreno real** (viene de la carpeta de origen en `data/raw/`). **Limitación:** solo 2 materias de vocabulario muy distinto y pocos documentos tipo examen/review (96 historia / 34 tecnología), así que el F1-macro es modesto por el desbalance y el tamaño chico del banco, no por falla del modelo.
- **Estándares curriculares, multi-etiqueta** (`ml-estandares-eval --materia <...>`): un solo modelo razonable (regresión logística multi-etiqueta vía `OneVsRestClassifier`), sin la comparación de 5 modelos que sí tiene sentido para Bloom — con ~20 códigos repartidos en ~130 documentos, esa comparación no sería estadísticamente significativa. **Limitación honesta** (la más fuerte de las tres): las etiquetas son pseudo-etiquetas del etiquetado por embeddings, no juicio humano — ver la sección anterior.

## Documento de referencia

[`docs/estandares_y_mejores_practicas.md`](docs/estandares_y_mejores_practicas.md) — compila:
- Los 8 estándares de contenido de Estudios Sociales de Puerto Rico (grado por grado, 5°-8°).
- El estado de los estándares de Tecnología/Ciencias de Cómputos de PR (en revisión para 2025-26).
- Marcos nacionales de EE.UU.: C3 Framework/NCSS (Estudios Sociales), ISTE y CSTA (Tecnología/CS).
- Mejores prácticas de diseño instruccional (Backward Design/UbD), calibración de dificultad (Bloom revisada + Webb's DOK), diseño de exámenes (tabla de especificaciones, redacción de ítems), psicometría básica (índice de dificultad y discriminación), objetivos de aprendizaje medibles (ABCD/SMART) y accesibilidad (UDL 3.0).

Este documento es la base de los estándares curriculares que los clasificadores de materia/estándares intentan identificar.

## Hoja de ruta

1. ✅ **Ingesta**: extrae texto de `data/raw/` (docx/pptx/xlsx/pdf/txt) a `data/processed/documents/`.
2. ✅ **Etiquetado de temas**: clasifica cada documento contra los estándares (similaridad de embeddings, sin LLM).
3. ✅ **Perfil de dificultad histórico**: tabla Bloom × DOK por examen, vía heurística de verbos (sin LLM).
4. ✅ **Clasificador de materia a nivel de examen completo**: entrena/evalúa (CV + grid search) y predice sobre un archivo nuevo.
5. ✅ **Clasificador multi-etiqueta de estándares**: entrena/evalúa (pseudo-etiquetas del etiquetado por embeddings) y predice sobre un archivo nuevo.
6. 🗄️ **Archivado (2026-10-20)**: generación de exámenes/lecciones, validación, ensamblado a `.docx` y auditoría — era el enfoque original del capstone; ver `_deprecated/README.md`.
7. ⬜ **Pendiente**: transcribir el detalle grado-por-grado de los 7 estándares de Estudios Sociales que faltan (solo "Cambio y Continuidad" está completo, ver `pipeline/standards/pr_estudios_sociales.yaml`); llevar los estándares de tecnología a nivel de indicador CSTA (hoy solo a nivel de concepto/estándar general); evaluar una estratificación multi-etiqueta real para `ml-estandares-eval` en vez del split aleatorio simple actual; evaluar OCR para los PDFs escaneados de 5° grado (excluidos por ahora).

## Métrica de éxito

- **Precisión de materia por examen**: accuracy/F1-macro del clasificador de materia en exámenes nunca vistos en entrenamiento (`ml-subject-eval`).
- **Precisión de estándares por examen**: F1 micro/macro del clasificador multi-etiqueta de estándares (`ml-estandares-eval`), leído junto al soporte por código.
- **Cobertura temática**: qué tan bien el etiquetado por embeddings (`tag`) y el clasificador de estándares coinciden en qué estándares cubre un documento.
- **Dificultad comparable**: distribución Bloom/DOK de un examen nuevo frente al banco histórico de la misma materia/grado.
