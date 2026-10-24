document.addEventListener("DOMContentLoaded", () => {
    // Date update
    const now = new Date();
    const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
    document.getElementById('headerDate').innerText = now.toLocaleDateString('en-US', options).toUpperCase();

    fetchAdminData();
});

async function fetchAdminData() {
    const tbody = document.getElementById('userTableBody');
    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;">Retrieving records...</td></tr>';

    try {
        const response = await fetch('/api/admin/data');
        if (!response.ok) throw new Error("Access Denied");

        const data = await response.json();
        renderAdminDashboard(data);
    } catch (error) {
        console.error("Admin error:", error);
        tbody.innerHTML = `<tr><td colspan="4" style="text-align:center; color: var(--color-sell);">FATAL ERROR: Unauthorized Access to Intelligence Hub.</td></tr>`;
    }
}

function renderAdminDashboard(data) {
    const tbody = document.getElementById('userTableBody');
    tbody.innerHTML = '';

    let totalHoldings = 0;
    document.getElementById('totalUsers').innerText = data.length;

    data.forEach(user => {
        totalHoldings += user.holdings;
        const row = document.createElement('tr');
        const date = new Date(user.created_at).toLocaleDateString();
        const emailCell = row.insertCell();
        const emailText = document.createElement('strong');
        emailText.textContent = user.email;
        emailCell.appendChild(emailText);
        row.insertCell().textContent = date;
        const holdingsCell = row.insertCell();
        const badge = document.createElement('span');
        badge.className = `classic-badge ${user.holdings > 0 ? 'BUY' : 'HOLD'}`;
        badge.textContent = `${user.holdings} Items`;
        holdingsCell.appendChild(badge);
        const actions = row.insertCell();
        if (!user.is_admin) {
            const remove = document.createElement('button');
            remove.className = 'filter-btn';
            remove.textContent = 'DELETE';
            remove.style.color = 'var(--color-sell)';
            remove.addEventListener('click', () => deleteUser(user.email));
            actions.appendChild(remove);
        }
        tbody.appendChild(row);
    });

    document.getElementById('totalHoldings').innerText = totalHoldings;
}

async function deleteUser(email) {
    if (!confirm(`PERMANENTLY DELETE account and all portfolio data for ${email}?\nThis action cannot be undone.`)) return;

    try {
        const response = await fetch('/api/admin/delete_user', {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest'},
            body: JSON.stringify({ email })
        });

        const result = await response.json();
        if (response.ok) {
            alert(result.message);
            fetchAdminData(); // Refresh
        } else {
            alert(result.error || "Failed to delete user.");
        }
    } catch (error) {
        console.error("Delete error:", error);
        alert("Wire transmission failed. User remains in system.");
    }
}
