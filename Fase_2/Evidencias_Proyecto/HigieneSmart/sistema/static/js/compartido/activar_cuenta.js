document.addEventListener("DOMContentLoaded", () => {
  const botones = document.querySelectorAll(".password-toggle");

  botones.forEach((boton) => {
    boton.addEventListener("click", () => {
      const inputId = boton.dataset.target;
      const input = document.getElementById(inputId);
      const icono = boton.querySelector("i");

      if (!input) {
        return;
      }

      const mostrar = input.type === "password";

      input.type = mostrar ? "text" : "password";

      icono.classList.toggle("bi-eye-slash", !mostrar);
      icono.classList.toggle("bi-eye", mostrar);

      boton.setAttribute(
        "aria-label",
        mostrar ? "Ocultar contraseña" : "Mostrar contraseña"
      );
    });
  });
});