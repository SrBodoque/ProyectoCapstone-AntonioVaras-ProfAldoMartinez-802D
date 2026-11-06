
document.addEventListener("DOMContentLoaded", function () {
    const selectorBano = document.getElementById("bano-limite");
    const campoLimite = document.getElementById("limite-entradas");
    const textoLimite = document.getElementById("limite-actual");

    if (!selectorBano || !campoLimite || !textoLimite) {
        return;
    }

    function actualizarLimite() {
        const opcion = selectorBano.options[
            selectorBano.selectedIndex
        ];

        if (!selectorBano.value) {
            campoLimite.value = "";

            textoLimite.textContent =
                "Selecciona un baño para consultar su límite de entradas.";

            return;
        }

        const limiteGuardado = opcion.dataset.limite || "";

        campoLimite.value = limiteGuardado;

        if (limiteGuardado) {
            textoLimite.textContent =
                `Límite guardado: ${limiteGuardado} entradas.`;
        } else {
            textoLimite.textContent =
                "Este baño no tiene un límite configurado.";
        }
    }

    selectorBano.addEventListener("change", actualizarLimite);

    actualizarLimite();
});
