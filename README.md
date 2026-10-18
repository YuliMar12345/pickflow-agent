# PICKFLOW-AGENT — App web (Parcial A, Opción A)

App en Streamlit que ejecuta el agente real desde cero (`pickflow_agent.py`, sin cambios) y las pruebas de la Fase 3 (`fase3_tests.py`, sin cambios).

## Ejecutar localmente
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Archivos
- `app.py` — interfaz (3 pestañas: instrucciones, ejecutar agente, pruebas y tabla de resultados).
- `core.py` — lógica que usa la interfaz (se puede probar sin Streamlit).
- `pickflow_agent.py`, `fase3_tests.py` — agente y pruebas de las fases 2 y 3.
- `referencia/` — valores publicados en el documento, para que la app compare contra ellos.

## Desplegar en Streamlit Community Cloud (gratis)
1. Crea un repositorio público en GitHub y sube **el contenido de esta carpeta** (que `app.py` quede en la raíz).
2. Entra a https://share.streamlit.io con tu cuenta de GitHub → **Create app** → elige el repo, la rama `main` y `app.py` como archivo principal → **Deploy**.
3. Copia la URL pública (`https://<nombre>.streamlit.app`) y pégala en el documento, sección «Enlaces y evidencias».
4. Las apps gratuitas se duermen por inactividad: ábrela antes de la fecha de calificación para dejarla despierta y comprueba que carga en una ventana de incógnito.

## Casos de prueba sugeridos
| ID | Escenario | Tipo | Resultado esperado |
|----|-----------|------|--------------------|
| S01 | Carga estándar (semilla 42) | Típico | 4/4 pedidos completados, ~16 min simulados |
| S03 | Carga alta, 6 pedidos | Típico | 6/6 completados |
| S06 | Un operario | Capacidad limitada | 100 %, ~10 % menos que FIFO |
| S09 | Ubicación inválida Z99 | **Falla esperada** | `KeyError: 'Z99'`, 0 pedidos completados |
| S10 | Sin operarios | **Falla esperada** | Sin excepción, pedidos pendientes |

Para la tabla completa: pestaña 3 → «Ejecutar las 50 pruebas».

## Evidencia a capturar (pantallazos o video)
1. Pestaña 2, S01 → «Ejecutar agente» (tabla de decisiones y métricas visibles).
2. Pestaña 2, S09 → «Ejecutar agente» (mensaje de falla esperada con `KeyError: 'Z99'`).
3. Pestaña 3 → «Ejecutar las 50 pruebas» (tabla de resultados, reproducibilidad «CUMPLE», «10 / 10» iguales al documento).
4. La barra de direcciones con la URL pública en las capturas.
