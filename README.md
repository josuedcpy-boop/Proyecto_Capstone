# Generador de Exámenes y Lecciones — Capstone MAI540

## Objetivo

Crear exámenes y lecciones consume mucho tiempo docente, y mantener consistencia de dificultad y cobertura de temas entre exámenes de distintos periodos es difícil de hacer a mano. Este proyecto construye un sistema que, dado un **banco de materiales y exámenes pasados**, genera **evaluaciones nuevas que cubren los mismos temas con dificultad comparable** — ancladas en los estándares curriculares oficiales (Puerto Rico y EE.UU.) y en mejores prácticas de diseño instruccional.

## Estado actual

El pipeline completo (ingesta → etiquetado de temas → perfil de dificultad → generación → validación → ensamblado) ya corre de punta a punta por CLI, sin necesidad de ninguna API key — ver [Cómo correr el pipeline](#cómo-correr-el-pipeline). La calidad de las preguntas generadas depende de qué proveedor de LLM se configure (por defecto es un *mock* de prueba; ver esa sección para activar uno real).

| Carpeta | Contenido |
|---|---|
| `data/raw/` | Copias de exámenes, guías de estudio y materiales de tema reales del docente (Historia 5°-8°, Tecnología 5°-8°) |
| `docs/estandares_y_mejores_practicas.md` | Estándares oficiales de PR y EE.UU. (Estudios Sociales y Tecnología/CS) + mejores prácticas de diseño de lecciones y exámenes |
| `pipeline/` | Código del pipeline (ingesta, estándares, embeddings/RAG, etiquetado, perfil de dificultad, proveedores de LLM, generación, validación, ensamblado) |
| `tests/` | Pruebas automáticas (`pytest`) de las partes deterministas del pipeline |
| `Examen_generado/` | Exámenes generados, como `.docx` listos para abrir en Word, nombrados `<Tema> - grado <N>.docx` |
| `Leccion_generada/` | Misma convención (`.docx` plano, `<Tema> - grado <N>.docx`), reservada para cuando se implemente generación de lecciones completas — hoy el pipeline solo genera exámenes |
| `Reportes_auditoria/` | Un `.md` por cada vez que se audita un examen ya generado (`pipeline.cli audit`), nombrado `<Tema> - Auditoria - <fecha abreviada>.md` (ej. `20Oct26`) |

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

El sistema está diseñado para **aprender de exámenes y materiales reales**: entre más completo el banco histórico, mejor cubre temas y calibra dificultad al generar exámenes nuevos. Cualquier docente puede añadir su propio material siguiendo estos pasos:

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
cp .env.example .env                # ajusta LLM_PROVIDER si quieres usar Ollama/Anthropic
```

### Comandos

```bash
python -m pipeline.cli ingest                                   # extrae texto de data/raw/ -> data/processed/documents/
python -m pipeline.cli tag                                      # cobertura de temas por materia/grado (sin LLM, solo embeddings)
python -m pipeline.cli profile "data/raw/history/top_level/History Test 7th.docx"   # tabla Bloom x DOK de un examen puntual
python -m pipeline.cli generate --materia historia --grado 7 --tema "Grito de Lares"   # genera + valida + audita + ensambla un examen nuevo
python -m pipeline.cli audit "Examen_generado/archivo.docx"                            # re-audita un examen ya generado; guarda el reporte en Reportes_auditoria/
python -m pipeline.cli topic-balance --materia historia --grado 8                      # agrupa preguntas históricas (k-means+PCA) y marca temas sobre/sub-representados
python -m pipeline.cli ml-bloom-eval                                                   # entrena/evalúa (CV + grid search) un clasificador ML de nivel Bloom — ver limitación abajo
python -m pipeline.cli run-all --materia historia --grado 7                            # ingest + tag + generate encadenados
```

`generate`/`run-all` toman el perfil de dificultad objetivo de un examen histórico real de esa materia/grado (el primero que encuentren, o el que indiques con `--perfil-de <ruta>`), y guardan el resultado directamente en `Examen_generado/` (sin subcarpetas) como **`<Tema> - grado <N>.docx`**, listo para abrir en Word. Si no pasas `--tema`, se usa el nombre del examen de referencia. Cualquier problema detectado en validación queda incluido al final del mismo documento. Si el nombre ya existe, se añade un sufijo (`_2`, `_3`, ...) en vez de sobrescribir.

### Proveedor de LLM (sin costo por defecto)

Las etapas de **ingesta, etiquetado de temas y perfil de dificultad no usan ningún LLM** — solo embeddings locales (`sentence-transformers`, gratis, se descarga una vez) y heurísticas. Solo la etapa de **generación** (y el paso opcional de LLM-juez en validación) necesita un modelo generativo, configurable en `.env` vía `LLM_PROVIDER` sin tocar código:

| `LLM_PROVIDER` | Costo | Requiere |
|---|---|---|
| `mock` (default) | Gratis | Nada — devuelve preguntas de ejemplo marcadas `[MOCK]`, útil para probar el flujo |
| `ollama` | Gratis | Instalar [Ollama](https://ollama.com) localmente y `ollama pull llama3.1:8b` (o el modelo que pongas en `OLLAMA_MODEL`) |
| `anthropic` | Bajo costo | `ANTHROPIC_API_KEY` en `.env` (ej. con `claude-haiku-5-5`, el modelo más económico) |

### Pruebas

```bash
pytest
```

Cubre extractores, el separador de preguntas, las reglas Bloom/DOK, auditoría y balance de temas — no requiere red ni ningún LLM.

### Servidor MCP

`mcp_server.py` expone el pipeline (ingesta, etiquetado, balance de temas, clasificación de dificultad, generación y auditoría de exámenes) como herramientas MCP, para orquestarlo conversacionalmente desde una sesión de Claude en vez de por comandos sueltos. Ya está conectado a este proyecto vía `.mcp.json` — basta con reabrir Claude Code aquí para que las herramientas aparezcan disponibles.

Dos formas de correrlo:
```bash
python mcp_server.py                          # local (stdio) — lo que usa .mcp.json
python mcp_server.py --http --port 8000       # como servidor web, accesible por red en http://<host>:8000/mcp
```
El modo `--http` no es una página para abrir en el navegador — es el protocolo MCP sobre HTTP, pensado para que otro cliente MCP (no un navegador) se conecte de forma remota en vez de solo desde esta terminal.

### Interfaz web (Streamlit)

Para usar el pipeline desde el navegador con botones en vez de la terminal:
```bash
streamlit run app.py
```
Abre `http://localhost:8501` con pestañas para generar un examen, auditar uno ya generado, ver el balance de temas, entrenar/evaluar el clasificador ML de dificultad, e ingerir/etiquetar materiales — todo reutilizando las mismas funciones que `pipeline/cli.py` y `mcp_server.py`.

### Modelo supervisado de dificultad (ML) — y su limitación honesta

`pipeline/ml/bloom_classifier.py` compara 5 modelos (línea base de clase mayoritaria, regresión logística, árbol de decisión, Random Forest, boosting — con búsqueda de hiperparámetros para los dos últimos) para predecir el **nivel Bloom** de una pregunta a partir de su texto (TF-IDF), con validación cruzada **agrupada por examen** (nunca se reparten preguntas del mismo examen entre entrenamiento y prueba, para no inflar el resultado con fuga de datos) y evaluación final en exámenes nunca vistos, desagregada por materia y grado.

**Limitación que hay que tener presente al leer los resultados:** las etiquetas de entrenamiento son la salida de la heurística de reglas del propio proyecto (`pipeline/difficulty/bloom_dok_rules.py`), no juicio humano independiente ni datos reales de estudiantes. El experimento mide si un modelo de texto puede *aprender a reproducir* ese criterio — no se presenta como "mejor que las reglas", y este modelo **no sustituye** `classify_question` en el pipeline de generación/auditoría. Al revisar los resultados con datos reales, esto además destapó una imprecisión real en la heurística: palabras como "create"/"creation" dentro de preguntas puramente factuales (ej. *"How did the creation of the United States affect..."*) se clasifican como nivel "Crear" (el más alto) solo por contener esa raíz, aunque la pregunta no pida crear nada — una mejora pendiente a `bloom_dok_rules.py`, no corregida todavía.

## Documento de referencia

[`docs/estandares_y_mejores_practicas.md`](docs/estandares_y_mejores_practicas.md) — compila:
- Los 8 estándares de contenido de Estudios Sociales de Puerto Rico (grado por grado, 5°-8°).
- El estado de los estándares de Tecnología/Ciencias de Cómputos de PR (en revisión para 2025-26).
- Marcos nacionales de EE.UU.: C3 Framework/NCSS (Estudios Sociales), ISTE y CSTA (Tecnología/CS).
- Mejores prácticas de diseño instruccional (Backward Design/UbD), calibración de dificultad (Bloom revisada + Webb's DOK), diseño de exámenes (tabla de especificaciones, redacción de ítems), psicometría básica (índice de dificultad y discriminación), objetivos de aprendizaje medibles (ABCD/SMART) y accesibilidad (UDL 3.0).

Este documento es la base para la taxonomía de temas y el perfil de dificultad que usará el pipeline de generación.

## Hoja de ruta

1. ✅ **Ingesta**: extrae texto de `data/raw/` (docx/pptx/xlsx/pdf/txt) a `data/processed/documents/`.
2. ✅ **Etiquetado de temas**: clasifica cada documento contra los estándares (similaridad de embeddings, sin LLM).
3. ✅ **Perfil de dificultad histórico**: tabla Bloom × DOK por examen, vía heurística de verbos (sin LLM).
4. ✅ **Generación**: RAG sobre el banco de materiales + proveedor de LLM intercambiable (mock/Ollama/Anthropic).
5. ✅ **Validación y ensamblado**: checklist Haladyna + detección de duplicados (sin LLM) + LLM-juez opcional; se ensambla a un `.docx` en `Examen_generado/`.
6. ⬜ **Pendiente**: transcribir el detalle grado-por-grado de los 7 estándares de Estudios Sociales que faltan (solo "Cambio y Continuidad" está completo, ver `pipeline/standards/pr_estudios_sociales.yaml`); evaluar OCR para los PDFs escaneados de 5° grado (excluidos por ahora); mejorar el separador de preguntas para formatos de examen que no usan numeración simple.

## Métrica de éxito

- **Cobertura temática**: % de temas del estándar/temario presentes en el examen generado vs. el examen de referencia.
- **Dificultad comparable**: distancia entre la distribución Bloom/DOK del examen generado y la del histórico.
- **Validez**: % de preguntas sin errores factuales ni ambigüedad.
- **Unicidad**: baja similaridad semántica contra el banco histórico (no son copias).
