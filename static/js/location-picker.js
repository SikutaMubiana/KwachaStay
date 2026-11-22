(function () {
    const mapElement = document.getElementById('locationPickerMap');
    const latitudeInput = document.getElementById('latitude');
    const longitudeInput = document.getElementById('longitude');
    const status = document.getElementById('locationPickerStatus');
    const locateButton = document.getElementById('useCurrentLocation');
    const searchInput = document.getElementById('locationSearchInput');
    const searchButton = document.getElementById('locationSearchBtn');
    const toggleLayerBtn = document.getElementById('toggleMapLayerBtn');
    const clearPinBtn = document.getElementById('clearLocationPinBtn');
    const previewLink = document.getElementById('googleMapsPreviewLink');
    const compoundSelect = document.querySelector('select[name="compound"]');
    if (!mapElement || !latitudeInput || !longitudeInput || !status) return;

    const neighbourhoodCoords = window.LUSAKA_NEIGHBOURHOOD_COORDS || {};
    const lusakaCenter = [-15.4167, 28.2833];
    let map;
    let marker;
    let streetLayer;
    let satelliteLayer;
    let isSatellite = false;

    function updatePreviewLink() {
        if (!previewLink) return;
        const lat = Number(latitudeInput.value);
        const lng = Number(longitudeInput.value);
        if (latitudeInput.value && longitudeInput.value && Number.isFinite(lat) && Number.isFinite(lng)) {
            previewLink.href = 'https://www.google.com/maps/search/?api=1&query=' + encodeURIComponent(lat.toFixed(6) + ',' + lng.toFixed(6));
            previewLink.classList.remove('hidden');
            if (clearPinBtn) clearPinBtn.classList.remove('hidden');
        } else {
            previewLink.classList.add('hidden');
            if (clearPinBtn) clearPinBtn.classList.add('hidden');
        }
    }

    function findNearestCompound(lat, lng) {
        let bestName = null;
        let bestDist = Infinity;
        Object.entries(neighbourhoodCoords).forEach(function ([name, coords]) {
            if (!Array.isArray(coords) || coords.length < 2) return;
            const dLat = lat - coords[0];
            const dLng = lng - coords[1];
            const dist = dLat * dLat + dLng * dLng;
            if (dist < bestDist) {
                bestDist = dist;
                bestName = name;
            }
        });
        // Roughly within ~5km of a known Lusaka neighbourhood center
        return bestDist <= 0.0025 ? bestName : null;
    }

    function selectCompoundIfEmpty(lat, lng) {
        if (!compoundSelect || compoundSelect.value) return;
        const nearest = findNearestCompound(lat, lng);
        if (!nearest) return;
        for (let i = 0; i < compoundSelect.options.length; i++) {
            if (compoundSelect.options[i].value === nearest) {
                compoundSelect.value = nearest;
                break;
            }
        }
    }

    function extractDirectCoords(rawText) {
        const text = (rawText || '').trim();
        if (!text) return null;
        const patterns = [
            /@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/,
            /[?&](?:q|ll|destination|viewpoint)=(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/,
            /!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)/,
            /^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$/
        ];
        for (let i = 0; i < patterns.length; i++) {
            const match = text.match(patterns[i]);
            if (match) {
                const lat = Number(match[1]);
                const lng = Number(match[2]);
                if (Number.isFinite(lat) && Number.isFinite(lng) && lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180) {
                    return [lat, lng];
                }
            }
        }
        return null;
    }

    function setCoordinates(latitude, longitude, zoomLevel, customMessage) {
        latitudeInput.value = Number(latitude).toFixed(6);
        longitudeInput.value = Number(longitude).toFixed(6);
        if (map && window.L) {
            const point = [Number(latitude), Number(longitude)];
            if (marker) {
                marker.setLatLng(point);
            } else {
                marker = L.marker(point, { draggable: true }).addTo(map);
                marker.on('dragend', function (event) {
                    const position = event.target.getLatLng();
                    latitudeInput.value = position.lat.toFixed(6);
                    longitudeInput.value = position.lng.toFixed(6);
                    status.textContent = 'Exact pin updated. Guests will see this house/villa on Google Maps & Satellite view.';
                    updatePreviewLink();
                });
            }
            if (zoomLevel) {
                map.setView(point, typeof zoomLevel === 'number' ? zoomLevel : 17);
            }
        }
        status.textContent = customMessage || 'Exact pin set! Drag the marker or switch to Satellite view to align right on your house or villa.';
        updatePreviewLink();
    }

    function updateFromInputs() {
        const latitude = Number(latitudeInput.value);
        const longitude = Number(longitudeInput.value);
        if (!latitudeInput.value && !longitudeInput.value) {
            if (marker && map) map.removeLayer(marker);
            marker = null;
            status.textContent = 'No exact pin yet — guests will still see your selected Lusaka neighbourhood on Google Maps.';
            updatePreviewLink();
            return;
        }
        if (!latitudeInput.value || !longitudeInput.value ||
            !Number.isFinite(latitude) || !Number.isFinite(longitude) ||
            latitude < -90 || latitude > 90 || longitude < -180 || longitude > 180) {
            status.textContent = 'Enter a valid latitude and longitude to set a pin.';
            updatePreviewLink();
            return;
        }
        setCoordinates(latitude, longitude, 17);
    }

    if (window.L) {
        map = L.map(mapElement).setView(lusakaCenter, 12);
        streetLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OpenStreetMap contributors',
            maxZoom: 19
        });
        satelliteLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
            attribution: 'Tiles &copy; Esri &mdash; Satellite imagery',
            maxZoom: 19
        });
        streetLayer.addTo(map);

        map.on('click', function (event) {
            setCoordinates(event.latlng.lat, event.latlng.lng, false);
            selectCompoundIfEmpty(event.latlng.lat, event.latlng.lng);
        });
        updateFromInputs();
        // If editing or neighbourhood already chosen without pin, center on that neighbourhood
        if (!latitudeInput.value && compoundSelect && compoundSelect.value && neighbourhoodCoords[compoundSelect.value]) {
            map.setView(neighbourhoodCoords[compoundSelect.value], 14);
        }
        window.setTimeout(function () { map.invalidateSize(); }, 120);
    } else {
        status.textContent = 'Map tiles could not load. You can still paste a Google Maps link or enter coordinates manually.';
    }

    if (toggleLayerBtn && map) {
        toggleLayerBtn.addEventListener('click', function () {
            if (isSatellite) {
                map.removeLayer(satelliteLayer);
                streetLayer.addTo(map);
                isSatellite = false;
                toggleLayerBtn.innerHTML = '<i class="fa-solid fa-satellite mr-1"></i>Satellite view';
            } else {
                map.removeLayer(streetLayer);
                satelliteLayer.addTo(map);
                isSatellite = true;
                toggleLayerBtn.innerHTML = '<i class="fa-solid fa-map mr-1"></i>Street map';
            }
        });
    }

    if (clearPinBtn) {
        clearPinBtn.addEventListener('click', function () {
            latitudeInput.value = '';
            longitudeInput.value = '';
            updateFromInputs();
        });
    }

    if (compoundSelect) {
        compoundSelect.addEventListener('change', function () {
            const selected = compoundSelect.value;
            const coords = neighbourhoodCoords[selected];
            if (!coords) return;
            if (!latitudeInput.value && !longitudeInput.value) {
                setCoordinates(
                    coords[0],
                    coords[1],
                    15,
                    'Auto-centred on ' + selected + '. Drag the pin or switch to Satellite view to pinpoint the exact house/villa.'
                );
            } else if (map) {
                map.panTo(coords);
            }
        });
    }

    async function runLocationSearch() {
        if (!searchInput) return;
        const query = searchInput.value.trim();
        if (!query) return;

        const direct = extractDirectCoords(query);
        if (direct) {
            setCoordinates(direct[0], direct[1], 17, 'Exact location loaded from coordinates / Google Maps link!');
            selectCompoundIfEmpty(direct[0], direct[1]);
            return;
        }

        if (searchButton) searchButton.disabled = true;
        status.textContent = 'Searching Lusaka location…';
        try {
            const resp = await fetch('/api/geocode?q=' + encodeURIComponent(query));
            const data = await resp.json();
            if (!resp.ok || data.error) {
                status.textContent = data.error || 'Could not find that place. Try a street name, neighbourhood, or click the map.';
            } else {
                setCoordinates(
                    data.latitude,
                    data.longitude,
                    data.source === 'neighbourhood' ? 15 : 17,
                    'Found: ' + (data.label || query) + '. Drag the pin to fine-tune onto your exact house/villa.'
                );
                selectCompoundIfEmpty(data.latitude, data.longitude);
            }
        } catch (err) {
            status.textContent = 'Location search failed. You can drop a pin directly on the map or use GPS.';
        } finally {
            if (searchButton) searchButton.disabled = false;
        }
    }

    if (searchButton) {
        searchButton.addEventListener('click', runLocationSearch);
    }
    if (searchInput) {
        searchInput.addEventListener('keydown', function (event) {
            if (event.key === 'Enter') {
                event.preventDefault();
                runLocationSearch();
            }
        });
    }

    latitudeInput.addEventListener('change', updateFromInputs);
    longitudeInput.addEventListener('change', updateFromInputs);

    if (locateButton) {
        locateButton.addEventListener('click', function () {
            if (!navigator.geolocation) {
                status.textContent = 'This browser does not support automatic GPS location. Search an address or click the map.';
                return;
            }
            locateButton.disabled = true;
            status.textContent = 'Detecting your exact GPS location…';
            navigator.geolocation.getCurrentPosition(
                function (position) {
                    setCoordinates(
                        position.coords.latitude,
                        position.coords.longitude,
                        18,
                        'Automatic GPS location detected! Switch to Satellite view to confirm the pin sits right on your property.'
                    );
                    selectCompoundIfEmpty(position.coords.latitude, position.coords.longitude);
                    locateButton.disabled = false;
                },
                function (error) {
                    const messages = {
                        1: 'Location permission was denied. You can search an address, paste a Google Maps link, or click the map.',
                        2: 'Your device could not determine its GPS location. Try searching the address or clicking the map.',
                        3: 'GPS request timed out. Try again or search the address above.'
                    };
                    status.textContent = messages[error.code] || 'Could not detect location. Select the point on the map.';
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
