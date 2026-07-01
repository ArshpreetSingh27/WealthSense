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
        
        row.innerHTML = `
            <td><strong>${user.email}</strong></td>
            <td>${date}</td>
            <td><span class="classic-badge ${user.holdings > 0 ? 'BUY' : 'HOLD'}">${user.holdings} Items</span></td>
            <td style="display:flex; gap:8px;">
                <button class="filter-btn" style="padding: 4px 8px; font-size: 9px;" onclick="alert('Audit logs for ${user.email} are classified.')">AUDIT</button>
                ${user.email !== 'admin@masterpredictor.com' ? `<button class="filter-btn" style="padding: 4px 8px; font-size: 9px; color: var(--color-sell); border-color: var(--color-sell);" onclick="deleteUser('${user.email}')">DELETE</button>` : ''}
            </td>
        `;
        tbody.appendChild(row);
    });

    document.getElementById('totalHoldings').innerText = totalHoldings;
}

async function deleteUser(email) {
    if (!confirm(`PERMANENTLY DELETE account and all portfolio data for ${email}?\nThis action cannot be undone.`)) return;

    try {
        const response = await fetch('/api/admin/delete_user', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
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
