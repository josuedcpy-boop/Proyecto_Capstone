# Reporte de auditoría — La seguridad en el Internet

**Fecha:** 20Oct26 (2026-10-20 23:46 UTC)
**Preguntas auditadas:** 20
**Material de referencia:** C:\Users\whate\Documents\Capstone_Canderlaria_Josue_MAI540\Proyecto_Capstone\data\raw\technology\top_level\Technology Final  Test 5th.docx

**Resultado general: NO APROBADO**

- [OK] **Puntuación total > 50**: Total: 110 puntos (20 pregunta(s)).
- [FALLA] **Mínimo 4 partes distintas**: Partes encontradas (3): ensayo, pareo, respuesta_corta.
  - *Por qué falla:* Solo hay 3 tipo(s) de pregunta distinto(s); se requieren al menos 4. Añade 1 tipo(s) más, por ejemplo: verdadero_falso.
- [FALLA] **Cobertura de temas comparable al material fuente**: Similaridad coseno entre distribución de estándares: 0.14 (umbral 0.5). Fuente: {'ISTE-CT': 3, 'AP': 1}. Generado: {'AP': 1, 'NI': 2}.
  - *Por qué falla:* La distribución de temas del examen generado no se parece a la del material fuente (similaridad 0.14, se requiere al menos 0.5). Estándares del material fuente que no aparecen en lo generado: ISTE-CT. Estándares presentes en lo generado pero no en la fuente: NI. Revisa si el contexto RAG está anclado al tema correcto, o genera más preguntas de los estándares faltantes.
- [OK] **Sin fuga de respuesta**: No hay preguntas de opción múltiple en este examen.
- [FALLA] **Sin preguntas casi duplicadas**: Pares casi-duplicados encontrados: [('parsed_0', 'parsed_5', 0.91), ('parsed_3', 'parsed_7', 0.92), ('parsed_3', 'parsed_8', 1.0), ('parsed_6', 'parsed_7', 0.9), ('parsed_7', 'parsed_8', 0.92), ('parsed_11', 'parsed_19', 0.94)].
  - *Por qué falla:* Las preguntas de cada par listado son casi idénticas entre sí (similaridad semántica >= 0.9) — elimina o reescribe una de cada par para no repetir contenido dentro del mismo examen.