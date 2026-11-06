
document.addEventListener("DOMContentLoaded", () => {
    const encabezado = document.querySelector(
        "[data-datos-url]"
    );

    if (!encabezado) {
        return;
    }

    const urlDatos = encabezado.dataset.datosUrl;

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

    let consultaEnCurso = false;

    async function actualizarDashboard() {
        // Evitar consultas simultáneas.
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

            // Actualizar las alertas pendientes.
            if (alertasElemento) {
                alertasElemento.textContent =
                    datos.alertas_pendientes;
            }

            // Actualizar las limpiezas en curso.
            if (limpiezasElemento) {
                limpiezasElemento.textContent =
                    datos.limpiezas_en_curso;
            }

            // Actualizar las limpiezas realizadas hoy.
            if (limpiezasHoyElemento) {
                limpiezasHoyElemento.textContent =
                    datos.limpiezas_hoy;
            }

            // Actualizar el contador de DroidCam.
            if (conteoElemento && datos.conteo_demo) {
                const entradas =
                    datos.conteo_demo.entradas;

                const limite =
                    datos.conteo_demo.limite ?? "—";

                conteoElemento.textContent =
                    `${entradas} / ${limite}`;
            }

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

    // Consultar automáticamente cada 3 segundos.
    setInterval(actualizarDashboard, 3000);
});
