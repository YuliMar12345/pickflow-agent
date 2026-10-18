"""PICKFLOW-AGENT — app web (Parcial A, Opción A: plataforma de despliegue).

Ejecuta el agente REAL (pickflow_agent.py) desde cero en cada clic: no muestra resultados guardados.
Ejecutar localmente:  streamlit run app.py
"""
import pandas as pd
import streamlit as st

import core

st.set_page_config(page_title="PICKFLOW-AGENT", page_icon="📦", layout="wide")

st.title("📦 PICKFLOW-AGENT")
st.caption("Agente de optimización de picking en una bodega simulada · Inteligencia Artificial · "
           "Universidad Tecnológica de Bolívar · Datos sintéticos, no de una bodega real")

tab_uso, tab_run, tab_tests = st.tabs(["1 · Instrucciones", "2 · Ejecutar el agente", "3 · Pruebas y tabla de resultados"])

# ---------------------------------------------------------------- 1. Instrucciones
with tab_uso:
    st.subheader("Cómo usar la app")
    st.markdown(
        """
1. Ve a la pestaña **2 · Ejecutar el agente**, elige un escenario y una semilla, y pulsa **Ejecutar agente**.
   Cada clic ejecuta el código del agente desde cero (percepción → decisión → acción) y genera un log nuevo.
2. Ve a **3 · Pruebas y tabla de resultados** y pulsa **Ejecutar las 50 pruebas**: se corren los 10 escenarios × 5
   repeticiones y la prueba de reproducibilidad, y se calculan los valores de la tabla de resultados.
   La app los compara con los valores publicados en el documento.

**El agente en una línea:** agente basado en utilidad con planificación voraz. Para cada pedido *o* y operario *p*
calcula `U(o,p) = 10·prioridad(o) − 2·distancia_Manhattan(p,o)` y asigna la pareja de mayor utilidad.
        """
    )
    st.subheader("Casos de prueba sugeridos")
    st.dataframe(
        pd.DataFrame(
            [
                ["S01", "Carga estándar (4 pedidos, 2 operarios)", "Escenario típico", "Los 4 pedidos se completan (100 %); ~16 min simulados."],
                ["S03", "Carga alta (6 pedidos)", "Escenario típico", "Los 6 pedidos se completan; ~24 min simulados."],
                ["S06", "Un solo operario", "Capacidad limitada", "100 % completado; es donde el agente más reduce el tiempo frente a FIFO (~10 %)."],
                ["S04 / S05", "Prioridad alta / baja en todos", "Caso límite", "100 % completado; el agente tarda ~12 % más que FIFO (limitación documentada)."],
                ["S09", "Pedido con ubicación inválida «Z99»", "FALLA ESPERADA", "El agente lanza KeyError: 'Z99' y no completa pedidos. Defecto documentado en la Fase 3."],
                ["S10", "Ningún operario disponible", "FALLA ESPERADA", "No asigna nada, no declara pedidos completados y termina sin excepción."],
            ],
            columns=["ID", "Escenario", "Tipo", "Resultado esperado"],
        ),
        hide_index=True,
    )
    st.info("La meta SMART original (reducir ≥ 20 % el tiempo frente a la referencia) **no** se alcanza en ningún "
            "escenario; la app lo muestra tal cual. FIFO es una línea base sintética, no el método real de una bodega.")

# ---------------------------------------------------------------- 2. Ejecutar
with tab_run:
    c1, c2, c3 = st.columns([3, 1, 1])
    with c1:
        sid = st.selectbox(
            "Escenario", list(core.SCENARIO_INFO),
            format_func=lambda s: f"{s} · {core.SCENARIO_INFO[s][0]}  [{core.KIND_LABEL[core.SCENARIO_INFO[s][1]]}]",
        )
    with c2:
        seed = st.number_input("Semilla", min_value=0, max_value=10**9, value=42, step=1)
    with c3:
        st.write("")
        st.write("")
        go = st.button("▶ Ejecutar agente", type="primary")

    if go:
        st.session_state["run"] = core.run_scenario(sid, int(seed))

    res = st.session_state.get("run")
    if res is None:
        st.write("Elige un escenario y pulsa **Ejecutar agente**.")
    else:
        st.markdown(f"### {res['scenario_id']} · {res['scenario_name']} · semilla {res['seed']}")
        if res["exception"]:
            st.error(f"**Falla esperada capturada:** `{res['exception']}`")
            st.markdown(
                "El agente intentó calcular la distancia hacia una ubicación que no existe en el mapa "
                "(`A1, A2, B1, B2, C1`) y se detuvo con una excepción. Es el defecto que la Fase 3 detectó en S09: "
                "la implementación **no valida** las ubicaciones. Ningún pedido se declara completado "
                f"({res['completed']} completados, {res['pending']} pendientes)."
            )
        elif res["completed"] == 0:
            st.warning(f"**Falla esperada controlada:** {res['stop_reason']['reason'] if res['stop_reason'] else 'sin recursos'}. "
                       f"El agente no asignó pedidos y los {res['pending']} permanecen pendientes (no se declararon completados).")
        else:
            st.success(f"Ejecución completada: {res['completed']} de {res['attempted']} pedidos.")

        m = st.columns(4)
        m[0].metric("Pedidos completados", f"{res['completed']} / {res['attempted']}")
        m[1].metric("Tiempo del agente (min)", "N/A" if res["exception"] or not res["completed"] else f"{res['total_minutes']:.2f}")
        m[2].metric("Tiempo FIFO (min)", "N/A" if not res["baseline_minutes"] else f"{res['baseline_minutes']:.2f}")
        m[3].metric("Reducción vs FIFO", "N/A" if res["reduction_pct"] is None else f"{res['reduction_pct']:.2f} %")

        if res["steps"]:
            st.markdown("**Decisiones y acciones del agente (en orden)**")
            st.dataframe(pd.DataFrame(res["steps"]), hide_index=True)
        with st.expander("Log JSONL completo (percepción, decisión, acción, resumen)"):
            st.code(res["log_text"], language="json")
        st.download_button("⬇ Descargar log JSONL", res["log_text"], file_name=f"{res['scenario_id']}_seed{res['seed']}.jsonl")

# ---------------------------------------------------------------- 3. Pruebas
with tab_tests:
    st.markdown("Ejecuta **10 escenarios × 5 repeticiones (50 ejecuciones)** + la comprobación de reproducibilidad, "
                "con las semillas de la Fase 3. Tarda menos de un segundo.")
    if st.button("▶ Ejecutar las 50 pruebas", type="primary"):
        st.session_state["tests"] = core.run_all_tests()

    t = st.session_state.get("tests")
    if t is None:
        st.write("Pulsa el botón para calcular la tabla de resultados.")
    else:
        rows = t["rows"]
        match = core.compare_with_document(rows)
        table = []
        for r, ok in zip(rows, match):
            fail = r["id"] in ("S09", "S10")
            table.append({
                "ID": r["id"], "Escenario": r["scenario"], "Rep.": int(r["repetitions"]),
                "Finalización (%)": float(r["completion_mean_pct"]),
                "Agente (min)": "N/A" if fail else float(r["agent_time_mean_min"]),
                "DE (min)": "N/A" if fail else float(r["agent_time_sd_min"]),
                "FIFO (min)": "N/A" if fail else float(r["baseline_time_mean_min"]),
                "Reducción (%)": "N/A" if fail else float(r["reduction_mean_pct"]),
                "Meta ≥20 %": "—" if fail else ("Sí" if float(r["reduction_mean_pct"]) >= 20 else "No"),
                "¿Cumple?": "Sí" if r["pass"] == "True" else "No",
                "Resultado / nota": r["notes"] if fail else "finalización ≥ 90 %",
                "Igual al documento": "✓" if ok else "✗",
            })
        st.markdown("#### Tabla de resultados")
        st.dataframe(pd.DataFrame(table), hide_index=True)
        st.caption("Tiempos en minutos simulados (media ± desviación estándar muestral de 5 repeticiones). "
                   "«¿Cumple?» = finalización ≥ 90 % en escenarios operativos, o manejo controlado en los de falla. "
                   "La meta SMART de reducción ≥ 20 % se muestra aparte.")

        a, b, c = st.columns(3)
        a.metric("Ejecuciones", "50")
        b.metric("Reproducibilidad (misma semilla)", "CUMPLE" if t["repro"]["repeatable"] else "NO CUMPLE")
        c.metric("Valores iguales al documento", f"{sum(match)} / {len(match)}")
        st.warning("**S09 no cumple:** la ubicación inválida «Z99» produce `KeyError`. Es una falla esperada y está "
                   "documentada como defecto de la implementación, no ocultada.")
        with st.expander("Salida de consola de la ejecución de pruebas"):
            st.code(t["stdout"])
        st.download_button("⬇ Descargar resumen (CSV)", pd.DataFrame(table).to_csv(index=False), file_name="resumen_fase3.csv")
