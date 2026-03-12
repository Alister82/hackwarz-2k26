// ── Init: Show logged-in user ──────────────────────────────────────────────
const userName = localStorage.getItem("userName") || "Guest";
const welcomeEl = document.getElementById("welcome-text");
const avatarEl  = document.getElementById("avatar-initials");
if (welcomeEl) welcomeEl.innerText = userName;
if (avatarEl)  avatarEl.innerText  = userName.charAt(0).toUpperCase();

// ── Leaflet map state ──────────────────────────────────────────────────────
let map = null;
let markers = [];

// ── Custom map icons ──────────────────────────────────────────────────────
function makeIcon(color) {
    // Creates a colored circle SVG marker
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="32" height="42" viewBox="0 0 32 42">
        <ellipse cx="16" cy="40" rx="7" ry="3" fill="rgba(0,0,0,0.3)"/>
        <path d="M16 0 C7.16 0 0 7.16 0 16 C0 28 16 42 16 42 C16 42 32 28 32 16 C32 7.16 24.84 0 16 0Z" fill="${color}"/>
        <circle cx="16" cy="16" r="8" fill="white" opacity="0.9"/>
    </svg>`;
    return L.divIcon({
        html: svg,
        iconSize: [32, 42],
        iconAnchor: [16, 42],
        popupAnchor: [0, -44],
        className: ''
    });
}

const ICONS = {
    high:       makeIcon('#ef4444'),
    medium:     makeIcon('#f59e0b'),
    low:        makeIcon('#22c55e'),
    suggestion: makeIcon('#4f8ef7')
};

// ── Geocode a place name → {lat, lon} via Nominatim ───────────────────────
async function geocode(place) {
    try {
        const url = `https://nominatim.openstreetmap.org/search?format=json&limit=1&q=${encodeURIComponent(place + " Goa India")}`;
        const res  = await fetch(url, { headers: { 'Accept-Language': 'en' } });
        const data = await res.json();
        if (data && data.length > 0) {
            return { lat: parseFloat(data[0].lat), lon: parseFloat(data[0].lon) };
        }
    } catch (_) {}
    return null;
}

// ── Add a marker to the Leaflet map ───────────────────────────────────────
function addMarker(lat, lon, icon, popupHtml) {
    const m = L.marker([lat, lon], { icon })
        .addTo(map)
        .bindPopup(popupHtml, { maxWidth: 280 });
    markers.push(m);
    return m;
}

// ── Build Google Maps directions URL ──────────────────────────────────────
function gmapsUrl(placeName) {
    const encoded = encodeURIComponent(placeName + ", Goa, India");
    return `https://www.google.com/maps/dir/?api=1&destination=${encoded}&travelmode=driving`;
}

// ── Crowd badge HTML ───────────────────────────────────────────────────────
function badgeFor(level) {
    const dot  = level === 'High'   ? '🔴'
               : level === 'Medium' ? '🟡'
               : level === 'Low'    ? '🟢' : '⚪';
    const cls  = level === 'High'   ? 'badge-high'
               : level === 'Medium' ? 'badge-medium'
               : level === 'Low'    ? 'badge-low' : 'badge-error';
    return `<span class="crowd-badge ${cls}">${dot} ${level}</span>`;
}

// ── Main: Check Crowd ──────────────────────────────────────────────────────
async function checkCrowd() {
    const place = document.getElementById('place-input').value.trim();
    if (!place) { alert("Please enter a place name!"); return; }

    // Loading state
    const btn     = document.getElementById('search-btn');
    const btnText = document.getElementById('btn-text');
    btn.disabled  = true;
    btnText.innerHTML = `<span class="spinner"></span> Analysing…`;

    const resultArea = document.getElementById('result-area');
    const mapCard    = document.getElementById('map-card');
    resultArea.style.display = 'none';
    mapCard.style.display    = 'none';
    resultArea.innerHTML     = '';

    // Clear old map markers
    if (map) { markers.forEach(m => m.remove()); markers = []; }

    try {
        // ── 1. Fetch AI crowd data from the backend ───────────────────────
        const apiRes  = await fetch(`http://127.0.0.1:8000/api/search?place=${encodeURIComponent(place)}`);
        if (!apiRes.ok) throw new Error(`Server returned ${apiRes.status}`);
        const data    = await apiRes.json();

        const level     = data.status || 'Unknown';   // Low / Medium / High / Error
        const isCrowded = level === 'High' || level === 'Medium';

        // ── 2. Render main crowd result card ─────────────────────────────
        resultArea.style.display = 'block';

        if (level === 'Error' || level === 'Unknown') {
            resultArea.innerHTML = `
                <div class="error-box">
                    ⚠️ <strong>${data.headline || 'Could not fetch crowd data.'}</strong><br>
                    <small>${data.description || 'Please try again in a moment.'}</small>
                </div>`;
            return;
        }

        // Feature cards (only render if content exists)
        const featuresHtml = (data.feature_1_title || data.feature_2_title) ? `
        <div class="features-grid">
            ${data.feature_1_title ? `
            <div class="feature-item">
                <h4>${data.feature_1_title}</h4>
                <p>${data.feature_1_desc}</p>
            </div>` : ''}
            ${data.feature_2_title ? `
            <div class="feature-item">
                <h4>${data.feature_2_title}</h4>
                <p>${data.feature_2_desc}</p>
            </div>` : ''}
        </div>` : '';

        const trendsHtml = data.trends ? `
        <div class="trends-block">
            <div class="label">📈 Crowd Trends</div>
            <p>${data.trends}</p>
        </div>` : '';

        resultArea.innerHTML = `
        <div class="card" style="animation-delay:0s">
            <div class="crowd-header">
                <div class="crowd-headline">${data.headline || `Crowd check for ${place}`}</div>
                ${badgeFor(level)}
            </div>
            <p class="crowd-desc">${data.description || ''}</p>
            ${featuresHtml}
            ${trendsHtml}
        </div>`;

        // ── 3. Suggestion card (High or Medium) ──────────────────────────
        const suggested = (data.suggested_place || '').trim();
        const hasSuggestion = suggested && suggested.toLowerCase() !== 'none needed' && suggested.toLowerCase() !== 'none';

        if (isCrowded && hasSuggestion) {
            const dirUrl = data.google_maps_url || gmapsUrl(suggested);
            resultArea.innerHTML += `
            <div class="suggestion-card">
                <div class="tag">✨ Less Crowded Alternative</div>
                <h3>${suggested}</h3>
                <p>${data.suggestion_reason || 'A quieter nearby spot worth visiting.'}</p>
                <a href="${dirUrl}" target="_blank" rel="noopener" class="btn-directions">
                    🗺️ Get Directions in Google Maps
                </a>
            </div>`;
        }

        // ── 4. Map & Markers ──────────────────────────────────────────────
        const mainCoords = await geocode(place);

        if (mainCoords) {
            mapCard.style.display = 'block';

            // Init or reuse map
            if (!map) {
                map = L.map('map', { zoomControl: true }).setView([mainCoords.lat, mainCoords.lon], 14);
                L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                }).addTo(map);
            } else {
                map.setView([mainCoords.lat, mainCoords.lon], 14);
            }

            // Main place marker
            const mainIcon    = ICONS[level.toLowerCase()] || ICONS.low;
            const mainGmaps   = gmapsUrl(place);
            const mainPopup   = `
                <div style="font-family:sans-serif;min-width:180px">
                    <strong style="font-size:1rem">${place}</strong><br>
                    <span style="font-size:0.82rem;color:#666">Crowd: <b>${level}</b></span><br><br>
                    <a href="${mainGmaps}" target="_blank" rel="noopener"
                       style="display:inline-block;background:#4f8ef7;color:#fff;padding:6px 14px;border-radius:20px;text-decoration:none;font-size:0.82rem;font-weight:600">
                        🗺️ Directions Here
                    </a>
                </div>`;
            const mainMarker = addMarker(mainCoords.lat, mainCoords.lon, mainIcon, mainPopup);
            mainMarker.openPopup();

            // Update legend
            const legendEl = document.getElementById('map-legend');
            legendEl.innerHTML = `
                <div class="legend-item"><div class="legend-dot" style="background:#ef4444"></div> High Crowd</div>
                <div class="legend-item"><div class="legend-dot" style="background:#f59e0b"></div> Medium Crowd</div>
                <div class="legend-item"><div class="legend-dot" style="background:#22c55e"></div> Low Crowd</div>
                <div class="legend-item"><div class="legend-dot" style="background:#4f8ef7"></div> Alternative Spot</div>`;

            // Alternative place marker
            if (isCrowded && hasSuggestion) {
                const altCoords = await geocode(suggested);
                if (altCoords) {
                    const altGmaps  = data.google_maps_url || gmapsUrl(suggested);
                    const altPopup  = `
                        <div style="font-family:sans-serif;min-width:180px">
                            <strong style="font-size:1rem">${suggested}</strong><br>
                            <span style="font-size:0.82rem;color:#16a34a;font-weight:600">✅ Less Crowded Alternative</span><br>
                            <span style="font-size:0.78rem;color:#666">${(data.suggestion_reason || '').slice(0, 80)}…</span><br><br>
                            <a href="${altGmaps}" target="_blank" rel="noopener"
                               style="display:inline-block;background:#22c55e;color:#000;padding:6px 14px;border-radius:20px;text-decoration:none;font-size:0.82rem;font-weight:700">
                                🗺️ Navigate Here
                            </a>
                        </div>`;
                    const altMarker = addMarker(altCoords.lat, altCoords.lon, ICONS.suggestion, altPopup);

                    // Draw a dashed polyline between the two spots
                    L.polyline(
                        [[mainCoords.lat, mainCoords.lon], [altCoords.lat, altCoords.lon]],
                        { color: '#4f8ef7', weight: 2, dashArray: '6 6', opacity: 0.6 }
                    ).addTo(map);

                    // Fit both markers in view
                    const bounds = L.latLngBounds(
                        [mainCoords.lat, mainCoords.lon],
                        [altCoords.lat, altCoords.lon]
                    );
                    map.fitBounds(bounds, { padding: [60, 60] });
                }
            }

            // Force Leaflet to recalculate size (needed when div was previously hidden)
            setTimeout(() => map.invalidateSize(), 100);
        }

    } catch (err) {
        resultArea.style.display = 'block';
        resultArea.innerHTML = `
            <div class="error-box">
                ⚠️ <strong>Could not connect to the AI server.</strong><br>
                <small>Make sure the backend is running at <code>http://127.0.0.1:8000</code>. Error: ${err.message}</small>
            </div>`;
    } finally {
        btn.disabled      = false;
        btnText.innerHTML = 'Search & Map';
    }
}

// Allow pressing Enter in the search input
document.getElementById('place-input')?.addEventListener('keydown', e => {
    if (e.key === 'Enter') checkCrowd();
});

// ── Cab Booking ────────────────────────────────────────────────────────────
async function findCabs() {
    const zone    = document.getElementById('zone-input').value.trim();
    if (!zone) { alert("Please enter a zone!"); return; }

    const cabList = document.getElementById('cab-list');
    cabList.innerHTML = '<li style="color:#94a3b8">Searching…</li>';

    try {
        const res  = await fetch(`http://127.0.0.1:8000/api/drivers/search?zone=${encodeURIComponent(zone)}`);
        const data = await res.json();
        cabList.innerHTML = '';

        if (!data.drivers || data.drivers.length === 0) {
            cabList.innerHTML = `<li>${data.message || 'No cabs found in this zone.'}</li>`;
            return;
        }
        data.drivers.forEach(driver => {
            const li = document.createElement('li');
            li.innerHTML = `🚖 <strong>${driver.name}</strong> &nbsp;·&nbsp; 📞 ${driver.phone}`;
            cabList.appendChild(li);
        });
    } catch (err) {
        cabList.innerHTML = `<li style="color:#ef4444">⚠️ Could not reach server. Is the backend running?</li>`;
    }
}

// Allow pressing Enter in zone input
document.getElementById('zone-input')?.addEventListener('keydown', e => {
    if (e.key === 'Enter') findCabs();
});