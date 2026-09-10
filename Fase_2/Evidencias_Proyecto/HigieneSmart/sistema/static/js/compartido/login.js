const loginForm = document.querySelector(".login-form");

const emailInput = document.getElementById("email");
const emailError = document.getElementById("email-error");

const passwordInput = document.getElementById("password");
const passwordError = document.getElementById("password-error");

const togglePassword = document.getElementById("toggle-password");
const iconEyeClosed = document.getElementById("icon-eye-closed");
const iconEyeOpen = document.getElementById("icon-eye-open");


function validarCorreo(correo) {
    const formatoCorreo = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/;

    return formatoCorreo.test(correo);
}


togglePassword.addEventListener("click", function () {
    const estaOculta = passwordInput.type === "password";

    if (estaOculta) {
        passwordInput.type = "text";

        iconEyeClosed.classList.add("hidden");
        iconEyeOpen.classList.remove("hidden");

        togglePassword.setAttribute(
            "aria-label",
            "Ocultar contraseña"
        );
    } else {
        passwordInput.type = "password";

        iconEyeOpen.classList.add("hidden");
        iconEyeClosed.classList.remove("hidden");

        togglePassword.setAttribute(
            "aria-label",
            "Mostrar contraseña"
        );
    }
});


loginForm.addEventListener("submit", function (event) {
    const correo = emailInput.value.trim();
    const password = passwordInput.value;

    let formularioValido = true;


    // Limpiar errores anteriores del correo
    emailError.textContent = "";
    emailError.classList.remove("visible");
    emailInput.classList.remove("input-error");


    // Limpiar errores anteriores de la contraseña
    passwordError.textContent = "";
    passwordError.classList.remove("visible");
    passwordInput.classList.remove("input-error");


    // Validar correo
    if (correo === "") {
        emailError.textContent = "Debes ingresar tu correo electrónico.";
        emailError.classList.add("visible");
        emailInput.classList.add("input-error");

        formularioValido = false;
    } else if (!validarCorreo(correo)) {
        emailError.textContent = "Ingresa un correo electrónico válido.";
        emailError.classList.add("visible");
        emailInput.classList.add("input-error");

        formularioValido = false;
    }


    // Validar contraseña
    if (password === "") {
        passwordError.textContent = "Debes ingresar tu contraseña.";
        passwordError.classList.add("visible");
        passwordInput.classList.add("input-error");

        formularioValido = false;
    }


    // Evitar el envío si existen errores
    if (!formularioValido) {
        event.preventDefault();
    }
});