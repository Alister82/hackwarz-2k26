// ── Authentication Check ───────────────────────────────────────────────────
if (localStorage.getItem("govAuth") !== "true") {
    alert("Unauthorized access. Redirecting to login...");
    window.location.href = "login.html";
}

// ── Logout ─────────────────────────────────────────────────────────────────
function govLogout() {
    localStorage.removeItem("govAuth");
    window.location.href = "login.html";
}

// ── Fetch and Render Dashboard Data ────────────────────────────────────────
async function loadDashboard() {
    const tbody = document.getElementById('dashboard-body');

    try {
        const res = await fetch('http://127.0.0.1:8000/api/gov/dashboard');
        if (!res.ok) throw new Error("Failed to fetch data");
        
        const json = await res.json();
        const data = json.data;
        
        if (!data || data.length === 0) {
            tbody.innerHTML = `<tr><td colspan="4" style="text-align:center; padding: 2rem; color: #94a3b8;">No data available yet.</td></tr>`;
            return;
        }

        // Calculate Stats
        const totalLocations = data.length;
        const totalSearches = data.reduce((sum, item) => sum + item.searches, 0);
        const highAlerts = data.filter(item => item.crowd_level === "High" || item.searches > 100).length;

        document.getElementById('stat-locations').innerText = totalLocations;
        document.getElementById('stat-searches').innerText = totalSearches.toLocaleString();
        document.getElementById('stat-alerts').innerText = highAlerts;

        // Render Table
        tbody.innerHTML = '';
        data.forEach(item => {
            const tr = document.createElement('tr');
            
            // Badge formatting
            let badgeClass = 'badge-low';
            let dot = '🟢';
            if (item.crowd_level === 'High') { badgeClass = 'badge-high'; dot = '🔴'; }
            else if (item.crowd_level === 'Medium') { badgeClass = 'badge-medium'; dot = '🟡'; }

            // Actions formating styling
            const isHigh = badgeClass === 'badge-high';
            
            tr.innerHTML = `
                <td><strong>${item.place}</strong></td>
                <td><span style="font-size:1.1rem; font-weight:600;">${item.searches}</span></td>
                <td><span class="badge ${badgeClass}">${dot} ${item.crowd_level}</span></td>
                <td>
                    <div class="suggestion-box">
                        <div class="${isHigh ? 's-police' : 's-neutral'}">${item.police_suggestion}</div>
                        <div class="${isHigh ? 's-clean' : 's-neutral'}">${item.cleaning_suggestion}</div>
                    </div>
                </td>
            `;
            tbody.appendChild(tr);
        });

    } catch (err) {
        tbody.innerHTML = `
            <tr>
                <td colspan="4">
                    <div style="text-align:center; color: #ef4444; padding: 2rem;">
                        ⚠️ Error connecting to server. Make sure the backend is running.
                    </div>
                </td>
            </tr>
        `;
    }
}

// ── Initialization ─────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    loadDashboard();
});
