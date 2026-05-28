(function () {
    const cities = window.CITY_RESULTS || [];
    const apiKey = window.YANDEX_MAPS_API_KEY;
    const message = document.getElementById("map-message");
    const mapElement = document.getElementById("map");
    const usdToRub = 90;

    function showFallback(text) {
        if (message) {
            message.textContent = text;
            message.classList.remove("hidden");
        }
        if (mapElement) {
            mapElement.innerHTML = "<div class=\"map-fallback\">Добавьте ключ Яндекс.Карт, чтобы увидеть интерактивную карту.</div>";
        }
    }

    function markerColor(score) {
        if (typeof score !== "number") return "blue";
        if (score >= 80) return "darkGreen";
        if (score >= 60) return "blue";
        if (score >= 40) return "orange";
        return "red";
    }

    function formatRub(value) {
        return `${Math.round(Number(value || 0) * usdToRub).toLocaleString("ru-RU")} ₽`;
    }

    function balloonBody(city) {
        const rating = typeof city.score === "number"
            ? `Рейтинг: ${city.score}%<br>`
            : "";
        const detailUrl = city.detail_url || `/city/${city.id}`;

        return `
            <strong>${city.region}</strong><br>
            ${rating}
            Аренда: ${formatRub(city.avg_rent_usd)}<br>
            Безопасность: ${city.safety_score}/10<br>
            Интернет: ${city.internet_score}/10<br>
            <p>${city.description}</p>
            <a href="${detailUrl}">Подробнее о городе</a>
        `;
    }

    if (!mapElement) {
        return;
    }

    if (!apiKey || apiKey === "YOUR_YANDEX_MAPS_API_KEY") {
        showFallback("Ключ Яндекс.Карт не указан. Замените YOUR_YANDEX_MAPS_API_KEY на настоящий ключ, и карта начнет работать.");
        return;
    }

    if (typeof ymaps === "undefined") {
        showFallback("Не удалось загрузить Яндекс.Карты. Проверьте ключ API и подключение к интернету.");
        return;
    }

    // Построение карты вынесено в отдельный JS-файл, чтобы шаблон оставался простым.
    ymaps.ready(function () {
        if (message) {
            message.classList.add("hidden");
        }

        const map = new ymaps.Map("map", {
            center: cities.length === 1 ? [cities[0].latitude, cities[0].longitude] : [55.75, 37.62],
            zoom: cities.length === 1 ? 10 : 4,
            controls: ["zoomControl", "fullscreenControl"]
        });

        const collection = new ymaps.GeoObjectCollection();

        cities.forEach(function (city) {
            const placemark = new ymaps.Placemark(
                [city.latitude, city.longitude],
                {
                    balloonContentHeader: city.name,
                    balloonContentBody: balloonBody(city),
                    hintContent: typeof city.score === "number" ? `${city.name}: ${city.score}%` : city.name
                },
                {
                    preset: "islands#circleDotIcon",
                    iconColor: markerColor(city.score)
                }
            );
            collection.add(placemark);
        });

        map.geoObjects.add(collection);
        if (cities.length > 0) {
            if (cities.length === 1) {
                collection.each(function (placemark) {
                    placemark.balloon.open();
                });
            } else {
                map.setBounds(collection.getBounds(), {
                    checkZoomRange: true,
                    zoomMargin: 40
                });
            }
        }
    });
})();
