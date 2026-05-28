(function () {
    const storageKey = "city-helper-theme";
    const themes = ["light-theme", "dark-theme", "super-dark-theme"];

    function applyTheme(theme) {
        const safeTheme = themes.includes(theme) ? theme : "light-theme";
        document.body.classList.remove(...themes);
        document.body.classList.add(safeTheme);
        localStorage.setItem(storageKey, safeTheme);

        const select = document.getElementById("theme-select");
        if (select) {
            select.value = safeTheme;
        }
    }

    document.addEventListener("DOMContentLoaded", function () {
        const savedTheme = localStorage.getItem(storageKey) || "light-theme";
        applyTheme(savedTheme);

        const select = document.getElementById("theme-select");
        if (select) {
            select.addEventListener("change", function () {
                applyTheme(select.value);
            });
        }
    });
})();
