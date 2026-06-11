document.addEventListener("DOMContentLoaded", function () {

    const forms = document.querySelectorAll("form");

    forms.forEach(form => {

        form.addEventListener("submit", function (e) {

            let valid = true;

            const requiredFields =
                form.querySelectorAll("[required]");

            requiredFields.forEach(field => {

                field.classList.remove("is-invalid");

                const errorId =
                    field.id + "-error";

                const existingError =
                    document.getElementById(errorId);

                if (existingError) {
                    existingError.remove();
                }

                if (!field.value.trim()) {

                    valid = false;

                    field.classList.add("is-invalid");

                    const error =
                        document.createElement("div");

                    error.id = errorId;

                    error.className =
                        "invalid-feedback d-block";

                    error.innerText =
                        "This field is required.";

                    field.parentNode.appendChild(error);
                }

            });

            if (!valid) {

                e.preventDefault();

                const firstError =
                    form.querySelector(".is-invalid");

                if (firstError) {

                    firstError.scrollIntoView({
                        behavior: "smooth",
                        block: "center"
                    });

                    firstError.focus();
                }

            }

        });

    });

});

document.addEventListener("DOMContentLoaded", function () {

    const requiredFields =
        document.querySelectorAll("[required]");

    requiredFields.forEach(field => {

        field.addEventListener("input", function () {

            hideFieldError(field);

        });

        field.addEventListener("change", function () {

            hideFieldError(field);

        });

    });

});


function hideFieldError(field) {

    field.classList.remove("is-invalid");

    const errorDiv =
        document.getElementById(
            field.id + "-error"
        );

    if (errorDiv) {

        errorDiv.remove();

    }

}

