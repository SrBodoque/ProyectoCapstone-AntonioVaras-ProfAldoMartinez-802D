
document.addEventListener("DOMContentLoaded", () => {
    const encabezado = document.querySelector(
        "[data-datos-url]"
    );

    if (!encabezado) {
        return;
    }

    const urlDatos = encabezado.dataset.datosUrl;

    // ==========================================
    // INDICADORES EXISTENTES
    // ==========================================

    const alertasElemento = document.getElementById(
        "alertas-pendientes-valor"
    );

    const limpiezasElemento = document.getElementById(
        "limpiezas-en-curso-valor"
    );

    const limpiezasHoyElemento = document.getElementById(
        "limpiezas-hoy-valor"
    );

    const conteoElemento = document.getElementById(
        "conteo-demo-valor"
    );

    // ==========================================
    // NUEVOS INDICADORES IN / OUT
    // ==========================================

    const ocupacionElemento = document.getElementById(
        "ocupacion-estimada-valor"
    );

    const estadoOcupacionElemento = document.getElementById(
        "ocupacion-estado-valor"
    );

    const movimientosElemento = document.getElementById(
        "movimientos-jornada-valor"
    );

    let consultaEnCurso = false;

    // ==========================================
    // MOSTRAR EL ESTADO DE OCUPACION
    // ==========================================

    
    function actualizarOcupacion(resumen) {
        if (!ocupacionElemento || !estadoOcupacionElemento) {
            return;
        }

        const estado = resumen?.ocupacion_estado;
        const ocupacion = resumen?.ocupacion_estimada;
        const motivo = resumen?.ocupacion_motivo;

        if (
            estado === "CONOCIDA" &&
            Number.isInteger(ocupacion) &&
            ocupacion >= 0
        ) {
            // Mostrar el numero incluso cuando
            // existieron salidas excedentes.
            ocupacionElemento.textContent =
                `${ocupacion} ${ocupacion === 1 ? "persona" : "personas"}`;

            // Mostrar advertencia si Python informo
            // que la estimacion tuvo que ajustarse.
            if (
                typeof motivo === "string" &&
                motivo.trim().length > 0
            ) {
                estadoOcupacionElemento.textContent =
                    `⚠️ ${motivo}`;
            } else {
                estadoOcupacionElemento.textContent =
                    "Ocupación estimada con referencia verificada";
            }

        } else if (estado === "INCONSISTENTE") {
            // Compatibilidad con estados antiguos.
            ocupacionElemento.textContent = "—";

            estadoOcupacionElemento.textContent =
                "Conteo inconsistente: requiere verificación";

        } else if (estado === "DESCONOCIDA") {
            ocupacionElemento.textContent = "—";

            estadoOcupacionElemento.textContent =
                "Ocupación desconocida: requiere verificación";

        } else {
            ocupacionElemento.textContent = "—";

            estadoOcupacionElemento.textContent =
                "Sin datos de ocupación disponibles";
        }
    }


    // ==========================================
    // MOSTRAR MOVIMIENTOS DE LA JORNADA
    // ==========================================

    function actualizarMovimientos(resumen) {
        if (!movimientosElemento) {
            return;
        }

        const entradas = resumen?.entradas_jornada;
        const salidas = resumen?.salidas_jornada;

        if (
            Number.isInteger(entradas) &&
            Number.isInteger(salidas)
        ) {
            movimientosElemento.textContent =
                `${entradas} / ${salidas}`;
        } else {
            movimientosElemento.textContent = "—";
        }
    }

    // ==========================================
    // ACTUALIZACION AUTOMATICA DEL DASHBOARD
    // ==========================================

    async function actualizarDashboard() {
        // Evitar consultas simultaneas y consultas
        // innecesarias cuando la pestaña esta oculta.
        if (consultaEnCurso || document.hidden) {
            return;
        }

        consultaEnCurso = true;

        try {
            const respuesta = await fetch(urlDatos, {
                method: "GET",
                credentials: "same-origin",
                cache: "no-store",
                headers: {
                    "Accept": "application/json"
                }
            });

            if (!respuesta.ok) {
                throw new Error(
                    `Error HTTP ${respuesta.status}`
                );
            }

            const datos = await respuesta.json();

            // Actualizar alertas pendientes.
            if (alertasElemento) {
                alertasElemento.textContent =
                    datos.alertas_pendientes;
            }

            // Actualizar limpiezas en curso.
            if (limpiezasElemento) {
                limpiezasElemento.textContent =
                    datos.limpiezas_en_curso;
            }

            // Actualizar limpiezas realizadas hoy.
            if (limpiezasHoyElemento) {
                limpiezasHoyElemento.textContent =
                    datos.limpiezas_hoy;
            }

            // ==========================================
            // CONTADOR EXISTENTE DE DROIDCAM
            // ==========================================

            if (conteoElemento && datos.conteo_demo) {
                const entradas =
                    datos.conteo_demo.entradas;

                const limite =
                    datos.conteo_demo.limite ?? "—";

                conteoElemento.textContent =
                    `${entradas} / ${limite}`;
            }

            // ==========================================
            // NUEVOS CONTADORES IN / OUT
            // ==========================================

            // El resumen solo estará disponible cuando
            // la funcionalidad esté habilitada.
            const resumen =
                datos.conteo_demo?.resumen_in_out;

            actualizarOcupacion(resumen);
            actualizarMovimientos(resumen);

        } catch (error) {
            console.warn(
                "No se pudo actualizar el dashboard:",
                error
            );

        } finally {
            consultaEnCurso = false;
        }
    }

    // Primera consulta al abrir el dashboard.
    actualizarDashboard();

    // Consultar automaticamente cada 3 segundos.
    setInterval(actualizarDashboard, 3000);
});
