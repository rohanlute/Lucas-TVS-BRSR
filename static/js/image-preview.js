document.addEventListener("DOMContentLoaded", function () {

    const fileInput = document.querySelector(".file-upload");

    const previewImage = document.querySelector(".upload-pic");

    if (!fileInput || !previewImage) return;

    fileInput.addEventListener("change", function () {

        const file = this.files[0];

        if (!file) return;

        const reader = new FileReader();

        reader.onload = function (e) {

            previewImage.src = e.target.result;

        };

        reader.readAsDataURL(file);

    });

});


document.addEventListener("DOMContentLoaded", function () {

    const uploadButton =
        document.querySelector(".upload-button");

    const fileInput =
        document.querySelector(".file-upload");

    if (uploadButton && fileInput) {

        uploadButton.addEventListener(
            "click",
            function () {

                fileInput.click();

            }
        );

    }

});