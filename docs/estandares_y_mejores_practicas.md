# Estándares y mejores prácticas para generación de lecciones y exámenes

Documento de referencia para el pipeline de generación de exámenes/lecciones del capstone. Compila: (1) los estándares curriculares de Puerto Rico y EE.UU. relevantes a las materias del banco de materiales (Estudios Sociales/Historia y Tecnología/Ciencias de Cómputos, grados 5°-8°), y (2) mejores prácticas de diseño instruccional y de evaluación que el sistema debe seguir al generar contenido nuevo.

Última actualización: 2026-10-18.

---

## 1. Estándares de Puerto Rico — Estudios Sociales

**Documento vigente:** *Estándares de Contenido y Expectativas de Grado de Puerto Rico — Programa de Estudios Sociales* (Departamento de Educación de Puerto Rico, 2014), parte del "Nuevo Modelo Didáctico Auténtico de Transformación del Currículo de Estudios Sociales". Es la versión que sigue circulando oficialmente; una Carta Circular (CC-013-2022-2023) describe la política pública vigente de organización curricular del Programa de Estudios Sociales para 2023-24, pero no reemplaza los 8 estándares de contenido — solo organiza cómo se ofrecen en cursos.

⚠️ Verificar antes de usar en producción: confirmar con de.pr.gov o dedigital.dde.pr si hay una revisión posterior a 2014 ya publicada, ya que varias copias universitarias todavía citan esa versión como la vigente.

### 1.1 Estructura y código

Cada estándar y expectativa de grado se identifica con un código **Inicial.Grado.Expectativa** (ej. `CC 5.1`, `PLA. 5.2`, `CC.7.2`). La inicial identifica el estándar, el primer número el grado, y el segundo la expectativa/destreza específica dentro de ese estándar.

Las expectativas de grado se dividen en 4 tipos: de contenido (conceptos/vocabulario), de proceso (pensar/razonar/investigar), de producto (proyectos/presentaciones), y aquellas que fijan qué se enseña en cada grado según los indicadores correspondientes.

### 1.2 Los 8 estándares de contenido

| # | Estándar | Código | Enfoque |
|---|----------|--------|---------|
| 1 | Cambio y Continuidad | `CC` | Vida de las sociedades en el contexto de cambios y transformaciones a través del tiempo (historia). |
| 2 | Personas, Lugares y Ambiente | `PLA` | Interacción entre personas, lugares, regiones y ambiente; perspectivas geográficas. |
| 3 | Desarrollo Personal | `DP` | Valores de la persona, desarrollo humano, inserción social y participación ciudadana. |
| 4 | Identidad Cultural | `IC` | — |
| 5 | Producción, Distribución y Consumo | — | Sistemas económicos. |
| 6 | Conciencia Cívica y Democrática | — | Ciudadanía, gobierno, democracia. |
| 7 | Conciencia Global | — | Interdependencia mundial. |
| 8 | Sociedad Científica y Tecnológica | — | Impacto de la ciencia/tecnología en la sociedad. |

Estos 8 estándares se alinean (de forma condensada) con los 10 temas temáticos del National Council for the Social Studies (NCSS) de EE.UU. — ver sección 3.

### 1.3 Temas clave por grado (5°-8°), Estándar #1 (Cambio y Continuidad)

Esto confirma que el banco de materiales del docente (copiado en `data/raw/history/`) está alineado con el estándar oficial:

- **5° grado (`CC 5.x`):** Historia de Puerto Rico y las Américas — sociedades precolombinas, conquista y colonización, instituciones coloniales, mestizaje, figuras como Moctezuma, Hernán Cortés, Fray Bartolomé de las Casas; lugares históricos (Machu Picchu, Tenochtitlán, Caguana, Tibes). → coincide con "Mesoamerica", "13 Colonies", "Age of Exploration", "The Indies" en el material copiado.
- **6° grado (`CC 6.x`):** Mundo antiguo — Edad de Piedra, Edad de los Metales, primeras civilizaciones, Mesopotamia, Egipto, Grecia, Roma, Edad Media; figuras como Sócrates, Alejandro Magno, Julio César. → coincide con "Rise of Civilizations", "Ancient Rome", "Greek Test", "Prehistory/Neolithic Age".
- **7° grado (`CC.7.x`):** Puerto Rico desde mediados del s. XIX — Real Cédula de Gracias 1815, Grito de Lares, abolición de la esclavitud, autonomismo, Guerra Hispanoamericana de 1898. → coincide con "Las Reformas", "Los Tainos", "Guerra Hispanoamericana", "La Explosión de Maine".
- **8° grado (`CC.8.x`):** Independencia y surgimiento de naciones americanas — Bolívar, San Martín, Martí, Washington, Jefferson; construcción de líneas de tiempo. → coincide con "Collapse of Great Empires", "Colombus Trips", "Hispanic Colonial Government", "New World".

Cada grado repite esta misma estructura de 8 estándares (Cambio y Continuidad, Personas/Lugares/Ambiente, Desarrollo Personal, Identidad Cultural, Producción/Distribución/Consumo, Conciencia Cívica, Conciencia Global, Sociedad Científica y Tecnológica) con expectativas propias — el pipeline debería extraer y usar las 8, no solo la de contenido histórico.

**Implicación para el pipeline:** usar esta tabla de 8 estándares × grado como la **taxonomía de temas objetivo** contra la cual medir cobertura, en vez de inventar una taxonomía ad-hoc a partir del texto libre de los materiales.

---

## 2. Estándares de Puerto Rico — Tecnología / Ciencias de Cómputos

A diferencia de Estudios Sociales, el área de Ciencias de Cómputos y Tecnologías Aplicadas está en transición activa:

- La iniciativa de Tecnología Educativa de 2022 publicó un primer set de estándares para el área.
- La Orden Ejecutiva **OE-2023-031** (firmada el 16 de octubre de 2023 por el gobernador) ordena al DEPR crear un plan estratégico (2024-2028) para integrar cursos de Ciencias de Cómputos, alineado al **K-12 Computer Science Framework** de EE.UU.
- Se estableció un **requisito de graduación**: todas las escuelas superiores deben ofrecer al menos 1/2 crédito de un curso del área.
- La implementación es por fases: escuela superior primero (2024-25), luego intermedia, luego todo el sistema.
- **Los estándares actuales están programados para revisión en el año escolar 2025-2026** — es decir, lo más probable es que cambien pronto.

**Implicación para el pipeline:** para Tecnología, dado que el estándar local de PR está en revisión, conviene anclar la generación de contenido a los marcos nacionales de EE.UU. (ISTE + CSTA, sección 4) como referencia más estable, y tratar el estándar de PR como una capa de alineación a verificar/actualizar cuando se publique la revisión 2025-26.

---

## 3. Estándares de EE.UU. — Estudios Sociales (C3 Framework / NCSS)

El **C3 Framework** ("College, Career, and Civic Life Framework for Social Studies State Standards", NCSS, 2013) es el marco de referencia nacional. No reemplaza los estándares estatales/de PR — los estados y territorios lo usan para mejorar sus propios estándares.

**Estructura — 4 dimensiones de la indagación (inquiry):**
1. Desarrollar preguntas y planificar indagaciones.
2. Aplicar conceptos y herramientas disciplinarias (civismo, economía, geografía, historia).
3. Evaluar fuentes y usar evidencia.
4. Comunicar conclusiones y tomar acción informada.

**Los 10 temas NCSS** (marco temático que organiza el contenido disciplinario, y con el que los 8 estándares de PR guardan correspondencia aproximada): Cultura; Tiempo, Continuidad y Cambio; Personas, Lugares y Ambientes; Desarrollo y Identidad Individual; Individuos, Grupos e Instituciones; Poder, Autoridad y Gobernanza; Producción, Distribución y Consumo; Ciencia, Tecnología y Sociedad; Conexiones Globales; Ideales y Prácticas Cívicas.

**Implicación para el pipeline:** el C3 Framework es útil sobre todo por su énfasis en *indagación* — preguntas de examen que solo piden recordar un dato no reflejan este estándar tan bien como preguntas que piden evaluar fuentes/evidencia (dimensión 3) o aplicar conceptos a un caso nuevo (dimensión 2). Esto debe informar qué tipos de pregunta generar, no solo qué temas cubrir.

---

## 4. Estándares de EE.UU. — Tecnología / Ciencias de Cómputos (ISTE + CSTA)

### 4.1 ISTE Standards for Students

7 estándares centrados en el aprendizaje (no en herramientas específicas): **Empowered Learner, Digital Citizen, Knowledge Constructor, Innovative Designer, Computational Thinker, Creative Communicator, Global Collaborator.** Cada uno tiene sub-indicadores (ej. Empowered Learner 1.1.a–d: el estudiante fija metas, construye redes de aprendizaje, busca retroalimentación).

### 4.2 CSTA K-12 Computer Science Standards

Organizados en bandas/niveles alineados al **K-12 CS Framework** (5 conceptos centrales + 7 prácticas):

| Nivel CSTA | Edades | Grado final | Equivalente a materiales del docente |
|---|---|---|---|
| 1A | 5-7 | fin de 2° | — |
| **1B** | 8-11 | **fin de 5°** | Technology Intro/5th |
| **2** | 11-14 | **fin de 8°** | Technology Intermedia (7°-8°) |
| 3A | 14-16 | fin de 10° | — |

Códigos de estándar con formato `Nivel-Concepto-Número` (ej. `1B-AP-10`, donde AP = Algorithms & Programming). Licencia CC BY-NC-SA 4.0. Los niveles 1B y 2 están diseñados para integrarse en materias existentes (no requieren curso aparte), lo cual calza con cómo el docente ya enseña Tecnología como materia transversal.

**Implicación para el pipeline:** para exámenes de Tecnología grados 5°-8°, usar CSTA niveles 1B (5°) y 2 (6°-8°) como ancla de contenido/dificultad, e ISTE como marco de habilidades transversales (pensamiento computacional, ciudadanía digital) que debe reflejarse en el tipo de pregunta, no solo en el tema.

---

## 5. Diseño instruccional: Backward Design / Understanding by Design (UbD)

Marco de Wiggins & McTighe para planificar lecciones y evaluaciones **empezando por el resultado deseado**, no por las actividades:

1. **Identificar los resultados deseados** (qué debe entender/poder hacer el estudiante — usar Bloom para fijar el nivel cognitivo esperado).
2. **Determinar evidencia aceptable** (cómo se va a evaluar que el estudiante llegó ahí — esto es, literalmente, diseñar el examen/rúbrica *antes* de planear las actividades de clase).
3. **Planificar las experiencias de aprendizaje** (actividades, materiales, secuencia).

Distinción clave: "cubrir contenido" ≠ "construir comprensión". Un examen que solo verifica que se "cubrió" el tema no es el objetivo; debe verificar comprensión real.

**Implicación para el pipeline:** el orden correcto para generar una lección nueva es: (a) fijar el resultado de aprendizaje y su nivel Bloom/DOK → (b) diseñar la evaluación (tabla de especificaciones) → (c) generar el contenido/actividades de la lección. Generar la lección primero y "derivar" el examen después invierte el diseño recomendado.

---

## 6. Calibración de dificultad: Bloom revisada + Webb's DOK

Dos marcos complementarios — Bloom mide el **tipo de proceso cognitivo**, DOK mide la **profundidad/complejidad** de la tarea independientemente del verbo usado. Usar DOK es más confiable para calibrar dificultad real, porque el verbo solo (ej. "explicar") no garantiza el nivel de complejidad.

### 6.1 Bloom revisada (Anderson & Krathwohl, 2001)

Recordar → Comprender → Aplicar → Analizar → Evaluar → Crear (orden de dificultad creciente; "Evaluar" y "Crear" intercambiaron posición respecto a la taxonomía original de 1956).

| Nivel | Formato de pregunta sugerido |
|---|---|
| Recordar | Opción múltiple, pareo, completar espacios |
| Comprender | + respuesta corta |
| Aplicar | Cálculos, respuesta corta, bosquejos |
| Analizar/Evaluar/Crear | Ensayo, justificación, diseño original |

### 6.2 Webb's Depth of Knowledge (DOK)

| Nivel | Nombre | Descripción | Ejemplo |
|---|---|---|---|
| 1 | Recall | Recordar un hecho o aplicar un procedimiento simple por rutina | Definir, copiar, calcular |
| 2 | Skills & Concepts | Requiere decidir un enfoque, >1 paso mental | Comparar, organizar, resumir, predecir |
| 3 | Strategic Thinking | Razonamiento abstracto, justificación, respuestas múltiples válidas | Diseñar un experimento, resolver un problema no rutinario |
| 4 | Extended Thinking | Síntesis de múltiples fuentes, transferencia entre dominios, trabajo extendido | Diseñar y analizar una encuesta, escribir un mito original en estilo antiguo |

⚠️ Para exámenes de aula/estandarizados de tiempo limitado, Webb recomienda limitarse a los niveles 1-3; el nivel 4 es más apropiado para evaluación local/proyectos extendidos, no para un examen de período de clase.

**Implicación directa para "dificultad comparable" (la métrica central del capstone):** en vez de pedirle al LLM que estime "dificultad" de forma difusa, cada pregunta generada debe etiquetarse con (Bloom, DOK) y el perfil de dificultad de un examen = distribución de pares (Bloom, DOK) entre sus preguntas. Comparar dos exámenes = comparar estas distribuciones, no una sola escala 1-5 subjetiva.

---

## 7. Diseño de la evaluación: tabla de especificaciones (test blueprint)

Antes de escribir preguntas, construir una **tabla de especificaciones**: filas = temas/estándares a cubrir, columnas = nivel cognitivo (Bloom/DOK), celdas = cuántos puntos/preguntas corresponden a cada combinación. Esto es exactamente el "perfil objetivo" que el pipeline debe generar a partir del examen histórico antes de generar preguntas nuevas (ver plan original, paso 3 "Perfil de dificultad histórico").

Buenas prácticas generales:
- Cada pregunta debe trazarse (tag) a un objetivo/estándar específico — mantener ese registro.
- Escribir más preguntas de las necesarias (banco extra) para poder descartar las débiles en revisión.
- Revisar el examen ensamblado después de un tiempo de "reposo", no inmediatamente tras escribirlo (aplicable a revisión humana del output del sistema).

---

## 8. Redacción de preguntas de opción múltiple

Reglas basadas en Haladyna et al. (2002), ampliamente adoptadas:

- **Un solo enunciado (stem) claro**, evitar negaciones ("¿Cuál NO es...", "todas excepto") — confunden sin medir más conocimiento.
- **Distractores plausibles**: deben reflejar errores comunes de estudiantes, no ser absurdos (un distractor absurdo permite adivinar sin saber el tema).
- **Forma paralela**: todas las opciones con longitud y gramática similar; la gramática de cada opción debe calzar con el enunciado.
- **Evitar "todas/ninguna de las anteriores"** y el formato complejo tipo "A y C son correctas".
- **Menos opciones bien escritas > más opciones de relleno**: si no se puede escribir un distractor creíble, es mejor usar menos alternativas.
- **Una sola respuesta correcta defendible.**

**Implicación para el pipeline:** estas reglas son ideales como checklist de validación automática post-generación (ej. un paso de LLM-juez que verifique cada ítem contra esta lista) antes de aceptar una pregunta generada.

---

## 9. Psicometría básica para validar "dificultad comparable"

Si en el futuro se recopilan resultados reales de estudiantes (no solo generación ciega), estos dos índices de la teoría clásica de tests permiten validar empíricamente la dificultad/calidad de cada ítem:

- **Índice de dificultad (p-value):** proporción de estudiantes que responden correctamente = (respuestas correctas) / (total de respuestas). Va de 0 a 1; **valores altos = pregunta fácil** (contraintuitivo). Rango óptimo típico: p entre 0.30 y 0.89; p > 0.90 es demasiado fácil, p < 0.20 demasiado difícil.
- **Índice de discriminación (D):** D = P_grupo_alto − P_grupo_bajo, donde cada P es la proporción de respuestas correctas en el 27% superior/inferior de puntuaciones totales. D = 1.00 es discriminación perfecta; D = 0 no discrimina; D negativo es señal de un ítem roto (lo contestan mejor los de puntuación baja). Rangos de referencia: 0.41-1.00 muy buena, 0.31-0.40 buena, 0.21-0.30 moderada, 0.11-0.20 pobre, <0.10 cuestionable.

**Implicación para el pipeline:** estos índices requieren datos reales de respuestas de estudiantes — no se pueden calcular solo con el LLM. Son la métrica de validación de la Fase 2 del capstone (después de pilotear los exámenes generados en un salón real), no de la generación inicial.

---

## 10. Objetivos de aprendizaje medibles (formato ABCD / SMART)

Para la generación de lecciones (no solo exámenes), cada objetivo de aprendizaje debe tener:

- **A — Audience:** quién (el estudiante de qué grado).
- **B — Behavior:** qué hará, en verbo observable (evitar "entender"/"saber" — usar verbos de Bloom como "explicar", "comparar", "construir").
- **C — Condition:** bajo qué circunstancia/con qué recurso.
- **D — Degree:** con qué nivel de exactitud/criterio de éxito.

Ejemplo aplicado a 7° grado historia: *"Dado un mapa de Puerto Rico y una línea de tiempo, el estudiante explicará con al menos 2 causas documentadas por qué ocurrió el Grito de Lares (1868)."*

Complementar con criterios **SMART** (específico, medible, alcanzable, relevante, con tiempo definido) al revisar el objetivo generado.

---

## 11. Diseño Universal para el Aprendizaje (UDL 3.0, CAST, 2024)

Framework de accesibilidad/inclusión a tener en cuenta al generar lecciones (no solo exámenes). 3 principios:

1. **Compromiso** ("el por qué") — múltiples formas de motivar/enganchar al estudiante.
2. **Representación** ("el qué") — múltiples formas de presentar la información (texto, imagen, audio).
3. **Acción y Expresión** ("el cómo") — múltiples formas de que el estudiante demuestre lo aprendido.

La versión 3.0 (julio 2024) añadió un énfasis explícito en función ejecutiva y en reconocer la identidad/variabilidad del estudiante como parte del diseño, no como excepción.

**Implicación para el pipeline:** si el sistema genera lecciones completas (no solo exámenes), debería ofrecer variantes de representación (ej. resumen en texto + línea de tiempo visual + lista de vocabulario) y variantes de evaluación (ej. opción múltiple + respuesta corta) para el mismo contenido, en vez de un solo formato fijo.

---

## 12. Síntesis: cómo se conecta esto con el pipeline del capstone

| Componente del pipeline (ver plan original) | Marco que lo informa |
|---|---|
| Taxonomía de temas para medir cobertura | 8 estándares de PR (sección 1.2) + 10 temas NCSS (sección 3) como validación cruzada |
| Perfil de dificultad histórico / tabla de especificaciones | Bloom + DOK (sección 6) cruzados con temas → tabla de especificaciones (sección 7) |
| Generación de preguntas ancladas en material (RAG) | Reglas de redacción de ítems (sección 8) como checklist de validación post-generación |
| Calibración de dificultad de preguntas generadas | Etiquetar cada ítem con (Bloom, DOK); comparar distribución contra el perfil objetivo |
| Validación con datos reales de alumnos (fase posterior) | p-value y D de la sección 9 |
| Orden de diseño (si se generan lecciones, no solo exámenes) | Backward Design/UbD (sección 5): resultado → evaluación → actividades |
| Accesibilidad de las lecciones generadas | UDL 3.0 (sección 11) |
| Tecnología: ancla de contenido/dificultad por grado | CSTA niveles 1B (5°) y 2 (6°-8°) + ISTE (sección 4) |

---

## Referencias

**Puerto Rico:**
- [Estándares de Contenido y Expectativas de Grado — Estudios Sociales (DEPR, 2014)](https://www.uprm.edu/ppm/wp-content/uploads/sites/47/2018/01/estandares_de_estudios_sociales.pdf)
- [Carta Circular CC-013-2022-2023 — Programa de Estudios Sociales](https://intraedu.dde.pr/Cartas%20Circulares/CARTA%20CIRCULAR%20NUM.%2013-2022-2023-FIRMADO.pdf)
- [DEPR — Ciencias de Cómputos y Tecnologías Aplicadas](https://de.pr.gov/secretaria-auxiliar-de-apoyo-integrado/ciencias-de-computos-y-tecnologias-aplicadas/)

**EE.UU. — Estudios Sociales:**
- [NCSS — Social Studies Standards](https://socialstudies.org/standards)
- [College, Career, and Civic Life (C3) Framework](https://www.socialstudies.org/c3)

**EE.UU. — Tecnología/CS:**
- [ISTE Standards for Students](https://iste.org/standards/for-students)
- [CSTA K-12 Computer Science Standards (copia OSPI Washington)](https://ospi.k12.wa.us/student-success/resources-subject-area/computer-science/computer-science-k-12-learning-standards)

**Diseño instruccional y evaluación:**
- [Understanding by Design — resumen (Vanderbilt CFT)](https://cdn.vanderbilt.edu/vu-cft/resources/teaching_resources/theory/design.htm)
- [Bloom's Taxonomy of Cognitive Levels, revisada](https://faculty.chass.ncsu.edu/slatta/hi216/learning/bloom.htm)
- [Webb's Depth of Knowledge — ejemplos por materia (Karin Hess)](https://www.veronaschools.org/cms/lib/NJ01001379/Centricity/Domain/17/DOKsocialstudies_KH08.pdf)
- [Steps to creating more valid exams — tabla de especificaciones (Vanderbilt CFT)](https://cft.vanderbilt.edu/?p=37758)
- [ASC Item Writing Guide 2025](https://assess.com/docs/ASC_Item-Writing-Guide_2025.pdf)
- [Rules for Multiple-Choice Items (Haladyna et al. 2002) — resumen](https://cpl.health.unm.edu/AssetListing/Writing-Questions-for-Learning-and-Assessment-2573/Rules-for-Multiple-Choice-Items-Haladyna-et-al-2002-5943)
- [Classical item difficulty (p-value)](https://assess.com/classical-item-difficulty-p-value/)
- [Discriminative Item Analysis](https://www.csueastbay.edu/testing/faculty/auto/score-reports/discriminative-analysis.html)
- [Writing measurable learning objectives — CDC](https://cdc.gov/training-development/php/about/design-training-learning-objectives.html)
- [UDL Guidelines 3.0 (CAST, 2024)](https://udlguidelines.cast.org/)
