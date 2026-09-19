document.addEventListener("DOMContentLoaded", function () {

    const form = document.querySelector("form");

    form.addEventListener("submit", function (event) {

        let age = document.getElementsByName("age")[0].value;
        let bp = document.getElementsByName("bp")[0].value;
        let chol = document.getElementsByName("chol")[0].value;

        if (age <= 0 || bp <= 0 || chol <= 0) {
            alert("Please enter valid input values.");
            event.preventDefault();
        }

    });

});