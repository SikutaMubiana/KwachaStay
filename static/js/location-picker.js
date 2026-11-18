(function () {
    const mapElement = document.getElementById('locationPickerMap');
    const latitudeInput = document.getElementById('latitude');
    const longitudeInput = document.getElementById('longitude');
    const status = document.getElementById('locationPickerStatus');
    const locateButton = document.getElementById('useCurrentLocation');
    if (!mapElement || !latitudeInput || !longitudeInput || !status) return;

    const lusakaCenter = [-15.4167, 28.2833];
    let map;
    let marker;

    function setCoordinates(latitude, longitude, zoom) {
        latitudeInput.value = Number(latitude).toFixed(6);
        longitudeInput.value = Number(longitude).toFixed(6);
        if (map && window.L) {
            const point = [Number(latitude), Number(longitude)];
            if (marker) marker.setLatLng(point);
            else {
                marker = L.marker(point, { draggable: true }).addTo(map);
                marker.on('dragend', function (event) {
                    const position = event.target.getLatLng();
                    latitudeInput.value = position.lat.toFixed(6);
                    longitudeInput.value = position.lng.toFixed(6);
                    status.textContent = 'Map pin selected. Guests can use it to open directions.';
                });
            }
            if (zoom) map.setView(point, 16);
        }
        status.textContent = 'Map pin selected. Guests can use it to open directions.';
    }

    function updateFromInputs() {
        const latitude = Number(latitudeInput.value);
        const longitude = Number(longitudeInput.value);
        if (!latitudeInput.value && !longitudeInput.value) {
            if (marker && map) map.removeLayer(marker);
            marker = null;
            status.textContent = 'No map pin selected. Guests will see the neighbourhood only.';
            return;
        }
        if (!latitudeInput.value || !longitudeInput.value ||
            !Number.isFinite(latitude) || !Number.isFinite(longitude) ||
            latitude < -90 || latitude > 90 || longitude < -180 || longitude > 180) {
            status.textContent = 'Enter a valid latitude and longitude to set a pin.';
            return;
        }
        setCoordinates(latitude, longitude, true);
    }

    if (window.L) {
        map = L.map(mapElement).setView(lusakaCenter, 12);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OpenStreetMap contributors',
            maxZoom: 19
        }).addTo(map);
        map.on('click', function (event) {
            setCoordinates(event.latlng.lat, event.latlng.lng, false);
        });
        updateFromInputs();
        window.setTimeout(function () { map.invalidateSize(); }, 100);
    } else {
        status.textContent = 'Map tiles could not load. You can still enter the coordinates manually.';
    }

    latitudeInput.addEventListener('change', updateFromInputs);
    longitudeInput.addEventListener('change', updateFromInputs);

    if (locateButton) {
        locateButton.addEventListener('click', function () {
            if (!navigator.geolocation) {
                status.textContent = 'This browser does not support location access. Choose a point on the map or enter coordinates.';
                return;
            }
            locateButton.disabled = true;
            status.textContent = 'Requesting your permission to use this device location…';
            navigator.geolocation.getCurrentPosition(
                function (position) {
                    setCoordinates(position.coords.latitude, position.coords.longitude, true);
                    locateButton.disabled = false;
                },
                function (error) {
                    const messages = {
                        1: 'Location permission was denied. You can still set the pin on the map.',
                        2: 'Your device could not determine its location. Try selecting the map point manually.',
                        3: 'Location request timed out. Try again or select the map point manually.'
                    };
                    status.textContent = messages[error.code] || 'Could not get your location. Select the map point manually.';
                    locateButton.disabled = false;
                },
                { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 }
            );
        });
    }

    const form = latitudeInput.closest('form');
    if (form) {
        form.addEventListener('submit', function (event) {
            const hasLatitude = Boolean(latitudeInput.value.trim());
            const hasLongitude = Boolean(longitudeInput.value.trim());
            latitudeInput.setCustomValidity('');
            longitudeInput.setCustomValidity('');
            if (hasLatitude !== hasLongitude) {
                event.preventDefault();
                const missingInput = hasLatitude ? longitudeInput : latitudeInput;
                missingInput.setCustomValidity('Enter both coordinates or leave both blank.');
                missingInput.reportValidity();
                status.textContent = 'Enter both coordinates or clear both fields.';
            }
        });
    }
})();
