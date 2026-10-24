const rupees = value => `₹${Number(value || 0).toLocaleString('en-IN', {maximumFractionDigits: 2, minimumFractionDigits: 2})}`;
const number = value => Number(value || 0).toLocaleString('en-IN');

function addRow(tbody, values, numericColumns = []) {
    const row = document.createElement('tr');
    values.forEach((value, index) => {
        const cell = document.createElement('td');
        cell.textContent = value;
        if (numericColumns.includes(index)) cell.classList.add('numeric');
        row.appendChild(cell);
    });
    tbody.appendChild(row);
}

function fillTable(id, items, render) {
    const body = document.getElementById(id);
    body.replaceChildren();
    if (!items.length) {
        const row = document.createElement('tr');
        const cell = document.createElement('td');
        cell.colSpan = body.closest('table').querySelectorAll('th').length;
        cell.textContent = 'Nothing to show';
        cell.className = 'empty-cell';
        row.appendChild(cell);
        body.appendChild(row);
        return;
    }
    items.forEach(item => addRow(body, render(item), [1, 2, 3, 4, 5]));
}

function renderPortfolio(data) {
    const holdings = data.holdings || [];
    const positions = (data.positions || []).filter(item => Number(item.quantity) !== 0);
    const orders = [...(data.orders || [])].reverse();
    const holdingsCost = holdings.reduce((sum, item) => sum + Number(item.quantity || 0) * Number(item.average_price || 0), 0);
    const holdingsValue = holdings.reduce((sum, item) => sum + Number(item.quantity || 0) * Number(item.last_price || 0), 0);
    const holdingsPnl = holdings.reduce((sum, item) => sum + Number(item.pnl || 0), 0);
    const positionsPnl = positions.reduce((sum, item) => sum + Number(item.pnl || 0), 0);
    document.getElementById('holdingsCost').textContent = rupees(holdingsCost);
    document.getElementById('holdingsValue').textContent = rupees(holdingsValue);
    document.getElementById('holdingsPnl').textContent = rupees(holdingsPnl);
    const availableFunds = data.funds?.equity?.available?.cash ?? data.funds?.equity?.net;
    document.getElementById('equityFunds').textContent = availableFunds == null ? '—' : rupees(availableFunds);
    document.getElementById('positionsPnl').textContent = `P&L ${rupees(positionsPnl)}`;

    fillTable('holdingsRows', holdings, item => [
        `${item.exchange}:${item.tradingsymbol}`, number(item.quantity), rupees(item.average_price),
        rupees(item.last_price), rupees(Number(item.quantity || 0) * Number(item.last_price || 0)), rupees(item.pnl)
    ]);
    fillTable('positionsRows', positions, item => [
        `${item.exchange}:${item.tradingsymbol}`, item.product || '—', number(item.quantity),
        rupees(item.average_price), rupees(item.last_price), rupees(item.pnl)
    ]);
    fillTable('ordersRows', orders, item => [
        item.order_timestamp || '—', `${item.exchange}:${item.tradingsymbol}`,
        item.transaction_type || '—', number(item.quantity), number(item.filled_quantity), item.status || '—'
    ]);
    document.getElementById('brokerContent').hidden = false;
    document.getElementById('kiteConnect').hidden = true;
    document.getElementById('refreshKite').hidden = false;
    document.getElementById('disconnectKite').hidden = false;
    const time = new Date(data.fetched_at).toLocaleString('en-IN');
    document.getElementById('kiteStatus').textContent = `Connected to Kite account ${data.broker_user_id}. Updated ${time}.`;
}

async function loadKitePortfolio() {
    const status = document.getElementById('kiteStatus');
    status.textContent = 'Syncing with Kite...';
    try {
        const response = await fetch('/api/kite/portfolio', {credentials: 'same-origin', cache: 'no-store'});
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Could not load Kite portfolio.');
        if (!data.connected) {
            document.getElementById('brokerContent').hidden = true;
            document.getElementById('kiteConnect').hidden = false;
            document.getElementById('refreshKite').hidden = true;
            document.getElementById('disconnectKite').hidden = true;
            document.getElementById('kiteConnect').textContent = data.reconnect_required ? 'Reconnect Kite' : 'Connect Kite';
            status.textContent = data.reconnect_required
                ? 'Your Kite session has expired. Reconnect to view current data.'
                : 'Connect your Zerodha account to display your portfolio here.';
            return;
        }
        renderPortfolio(data);
    } catch (error) {
        document.getElementById('brokerContent').hidden = true;
        status.textContent = error.message;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('refreshKite').addEventListener('click', loadKitePortfolio);
    document.getElementById('disconnectKite').addEventListener('click', async () => {
        const status = document.getElementById('kiteStatus');
        status.textContent = 'Disconnecting Kite...';
        try {
            const response = await fetch('/api/kite/disconnect', {
                method: 'POST', credentials: 'same-origin',
                headers: {'X-Requested-With': 'XMLHttpRequest'}
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Could not disconnect Kite.');
            await loadKitePortfolio();
            status.textContent = data.warning || 'Kite account disconnected. Connect again whenever you need it.';
        } catch (error) {
            status.textContent = error.message;
        }
    });
    loadKitePortfolio();
    setInterval(() => { if (!document.hidden) loadKitePortfolio(); }, 60000);
});
