// Show user's name from login
const userName = localStorage.getItem("userName");
if (userName) document.getElementById('welcome-text').innerText = `🏖️ Welcome, ${userName}`;

// Initialize the map variable
let map;
let marker;

async function checkCrowd() {
    const place = document.getElementById('place-input').value;
    if (!place) return alert("Please enter a place!");

    // 1. Get AI Crowd Data
    const response = await fetch(`http://127.0.0.1:8000/api/search?place=${place}`);
    const data = await response.json();

    document.getElementById('result-box').style.display = 'block';
    const statusSpan = document.getElementById('crowd-status');
    statusSpan.innerText = data.status;

    if (data.status === "High") {
        statusSpan.className = "danger";
        document.getElementById('ai-suggestion-box').style.display = 'block';
        document.getElementById('ai-text').innerText = data.ai_suggestion;
    } else {
        statusSpan.className = "safe";
        document.getElementById('ai-suggestion-box').style.display = 'none';
    }

    // 2. Free Geocoding (Convert Place name to GPS coordinates)
    const geoResponse = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${place}+Goa`);
    const geoData = await geoResponse.json();

    if (geoData.length > 0) {
        const lat = geoData[0].lat;
        const lon = geoData[0].lon;

        // Show the map div
        document.getElementById('map').style.display = 'block';

        // Load map if it doesn't exist, or just pan to new location if it does
        if (!map) {
            map = L.map('map').setView([lat, lon], 14);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap'
            }).addTo(map);
            marker = L.marker([lat, lon]).addTo(map).bindPopup(`<b>${place}</b>`).openPopup();
        } else {
            map.setView([lat, lon], 14);
            marker.setLatLng([lat, lon]).bindPopup(`<b>${place}</b>`).openPopup();
        }
    } else {
        alert("Could not find this location on the map.");
    }
}

async function findCabs() {
    const zone = document.getElementById('zone-input').value;
    const response = await fetch(`http://127.0.0.1:8000/api/drivers/search?zone=${zone}`);
    const data = await response.json();
    const cabList = document.getElementById('cab-list');
    cabList.innerHTML = ""; 

    if (data.drivers.length === 0) {
        cabList.innerHTML = `<li>${data.message}</li>`;
        return;
    }
    data.drivers.forEach(driver => {
        const li = document.createElement('li');
        li.innerText = `🚖 ${driver.name} - 📞 ${driver.phone}`;
        cabList.appendChild(li);
    });
}