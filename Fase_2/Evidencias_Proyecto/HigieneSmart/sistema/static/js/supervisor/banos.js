
document.addEventListener("DOMContentLoaded", () => {
    // Localizar la tabla de Gestión de baños.
    const seccion = document.querySelector(
        ".banos-card[data-datos-url]"
    );

    if (!seccion) {
        return;
    }

    const urlDatos = seccion.dataset.datosUrl;

    let consultaEnCurso = false;

    async function actualizarConteosBanos() {
        // Evitar consultas simultáneas.
        if (consultaEnCurso || document.hidden) {
            return;
        }

        consultaEnCurso = true;

        try {
            // Consultar los valores actuales de PostgreSQL.
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

            if (!Array.isArray(datos.banos)) {
                throw new Error(
                    "Formato de datos incorrecto"
                );
            }

            // Actualizar cada baño de la tabla.
            for (const bano of datos.banos) {
                const fila = document.querySelector(
                    `[data-bano-id="${bano.id}"]`
                );

                if (!fila) {
                    continue;
                }

                const contador = fila.querySelector(
                    "[data-entradas-limite]"
                );

                if (!contador) {
                    continue;
                }

                const entradas = bano.entradas;
                const limite = bano.limite ?? "—";

                // Cambiar solamente el número.
                contador.textContent =
                    `${entradas} / ${limite}`;
            }

        } catch (error) {
            console.warn(
                "No se pudo actualizar Gestión de baños:",
                error
            );

        } finally {
            consultaEnCurso = false;
        }
    }

    // Consultar inmediatamente al abrir la página.
    actualizarConteosBanos();

    // Actualizar automáticamente cada 3 segundos.
    setInterval(actualizarConteosBanos, 3000);

    // Consultar al regresar a la pestaña.
    document.addEventListener("visibilitychange", () => {
        if (!document.hidden) {
            actualizarConteosBanos();
        }
    });
});
