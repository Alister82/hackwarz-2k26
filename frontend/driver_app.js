// ── Authentication Check ───────────────────────────────────────────────────
const driverPhone = localStorage.getItem("driverPhone");

if (!driverPhone) {
    alert("Unauthorized access. Please login first.");
    window.location.href = "login.html";
}

// ── Logout ─────────────────────────────────────────────────────────────────
function driverLogout() {
    localStorage.removeItem("driverPhone");
    window.location.href = "login.html";
}

// ── Show Toast Notification ────────────────────────────────────────────────
function showToast(message) {
    const toast = document.getElementById('toast-msg');
    toast.innerText = message;
    toast.classList.add('show');
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

// ── Fetch Profile Details ──────────────────────────────────────────────────
async function loadProfile() {
    try {
        const res = await fetch(`http://127.0.0.1:8000/api/drivers/details?phone=${encodeURIComponent(driverPhone)}`);
        const data = await res.json();
        
        if (res.ok && data.status !== "error") {
            document.getElementById('prof-phone').value = data.phone;
            document.getElementById('prof-name').value = data.name;
            document.getElementById('prof-zone').value = data.zone;
        } else {
            throw new Error(data.message || "Failed to load profile.");
        }
    } catch (err) {
        alert("Error loading profile details: " + err.message);
    }
}

// ── Update Profile Details ─────────────────────────────────────────────────
async function updateProfile() {
    const name = document.getElementById('prof-name').value.trim();
    const zone = document.getElementById('prof-zone').value.trim();
    const btn = document.getElementById('save-btn');

    if (!name || !zone) {
        alert("Name and zones cannot be empty.");
        return;
    }

    const originalText = btn.innerHTML;
    btn.innerHTML = 'Saving...';
    btn.style.opacity = '0.8';

    try {
        // We reuse the register endpoint since we updated it to handle PUT/UPSERT automatically
        const res = await fetch('http://127.0.0.1:8000/api/drivers/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, phone: driverPhone, zone })
        });
        
        const data = await res.json();
        
        if (res.ok) {
            showToast("✅ " + data.message);
        } else {
            throw new Error(data.message || "Update failed");
        }
    } catch (err) {
        alert("Error updating profile.");
    } finally {
        btn.innerHTML = originalText;
        btn.style.opacity = '1';
    }
}

// ── Initialization ─────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    loadProfile();
});
