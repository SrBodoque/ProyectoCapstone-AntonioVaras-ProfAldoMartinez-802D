
document.addEventListener("DOMContentLoaded", () => {
    const selectorPanel = "#panel-trabajador-dinamico";

    const panelInicial = document.querySelector(selectorPanel);

    if (!panelInicial || !panelInicial.dataset.estadoUrl) {
        return;
    }

    let consultaEnCurso = false;
    let formularioEnviandose = false;

    // Evitar reemplazar el panel mientras se envía
    // un formulario de limpieza.
    document.addEventListener("submit", (evento) => {
        if (evento.target.closest(`${selectorPanel} form`)) {
            formularioEnviandose = true;
        }
    }, true);

    // Proteger la fotografía seleccionada por el trabajador.
    function tieneFotografiaSeleccionada() {
        const archivo = document.querySelector(
            `${selectorPanel} input[type="file"]`
        );

        return Boolean(
            archivo &&
            archivo.files &&
            archivo.files.length > 0
        );
    }

    async function actualizarPanelTrabajador() {
        if (
            consultaEnCurso ||
            document.hidden ||
            formularioEnviandose ||
            tieneFotografiaSeleccionada()
        ) {
            return;
        }

        consultaEnCurso = true;

        try {
            const panelActual = document.querySelector(selectorPanel);

            if (!panelActual) {
                return;
            }

            // Consultar los identificadores actuales en Django.
            const respuesta = await fetch(
                panelActual.dataset.estadoUrl,
                {
                    method: "GET",
                    credentials: "same-origin",
                    cache: "no-store",
                    headers: {
                        "Accept": "application/json"
                    }
                }
            );

            if (
                !respuesta.ok ||
                !respuesta.headers.get("content-type")?.includes(
                    "application/json"
                )
            ) {
                throw new Error("No se pudo consultar el estado");
            }

            const datos = await respuesta.json();

            // Comparar los datos recibidos con los mostrados.
            const cambios = (
                panelActual.dataset.asignacionId !==
                    String(datos.asignacion_id ?? "") ||

                panelActual.dataset.alertaId !==
                    String(datos.alerta_pendiente_id ?? "") ||

                panelActual.dataset.intervencionId !==
                    String(datos.intervencion_activa_id ?? "")
            );

            // Si nada cambió, no tocar el HTML.
            if (!cambios) {
                return;
            }

            // Solicitar la versión actualizada del panel.
            const respuestaHtml = await fetch(
                window.location.href,
                {
                    method: "GET",
                    credentials: "same-origin",
                    cache: "no-store",
                    headers: {
                        "Accept": "text/html"
                    }
                }
            );

            if (!respuestaHtml.ok) {
                throw new Error("No se pudo actualizar el panel");
            }

            const html = await respuestaHtml.text();

            const documento = new DOMParser().parseFromString(
                html,
                "text/html"
            );

            const panelNuevo = documento.querySelector(
                selectorPanel
            );

            if (!panelNuevo) {
                throw new Error("No se encontró el panel actualizado");
            }

            // Comprobar nuevamente que no se haya seleccionado
            // una fotografía mientras llegaba la respuesta.
            if (
                !formularioEnviandose &&
                !tieneFotografiaSeleccionada()
            ) {
                const panelVigente = document.querySelector(
                    selectorPanel
                );

                if (panelVigente) {
                    panelVigente.replaceWith(panelNuevo);
                }
            }

        } catch (error) {
            console.warn(
                "No se pudo actualizar el panel del trabajador:",
                error
            );
        } finally {
            consultaEnCurso = false;
        }
    }

    // Primera consulta al abrir la página.
    actualizarPanelTrabajador();

    // Consultar cada 3 segundos.
    setInterval(actualizarPanelTrabajador, 3000);

    // Actualizar al volver a una pestaña que estaba oculta.
    document.addEventListener("visibilitychange", () => {
        if (!document.hidden) {
            actualizarPanelTrabajador();
        }
    });
});
