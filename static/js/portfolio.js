document.addEventListener('DOMContentLoaded', () => {
    fetchPortfolio();

    const refreshBtn = document.getElementById('refreshPortfolio');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            refreshBtn.classList.add('spinning');
            fetchPortfolio().finally(() => {
                setTimeout(() => refreshBtn.classList.remove('spinning'), 1000);
            });
        });
    }
});

async function fetchPortfolio() {
    const portfolioGrid = document.getElementById('portfolioGrid');
    if (!portfolioGrid) return;

    try {
        const response = await fetch('/api/portfolio');
        if (!response.ok) throw new Error('System failure');
        
        const data = await response.json();
        const holdings = data.holdings || [];
        const summary = data.summary || {};
        const unpriced = data.unpriced_holdings || [];
        
        if (holdings.length > 0) {
            portfolioGrid.innerHTML = '';
            holdings.forEach((item) => {
                const isProfit = item.p_l >= 0;
                const plColor = isProfit ? 'var(--color-buy)' : 'var(--color-sell)';
                
                const card = document.createElement('div');
                card.className = 'holding-card';
                card.innerHTML = `
                    <div class="holding-header">
                        <strong>${item.ticker}</strong>
                        <button class="remove-btn-premium" onclick="removeFromPortfolio('${item.ticker}')">
                            <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" fill="none" stroke-width="2"><path d="M3 6h18m-2 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                        </button>
                    </div>
                    <div class="holding-body">
                        <div class="pl-row">
                            <span class="stat-label">Position</span>
                            <span>${item.quantity} units @ ₹${item.purchase_price.toLocaleString()}</span>
                        </div>
                        <div class="pl-row">
                            <span class="stat-label">Valuation</span>
                            <strong>₹${item.current_value.toLocaleString()}</strong>
                        </div>
                        <div class="pl-row">
                            <span class="stat-label">Gain / Loss</span>
                            <span class="pl-val" style="color: ${plColor}">${isProfit ? '+' : ''}₹${item.p_l.toLocaleString()}</span>
                        </div>
                    </div>
                `;
                portfolioGrid.appendChild(card);
            });

            // Update Global Summary
            updateSummary(summary);
        } else if (!unpriced.length) {
            portfolioGrid.innerHTML = `
                <div class="empty-state">
                    <h3>No assets detected.</h3>
                    <p>Add stocks from the WEALTH sense dashboard to begin tracking your portfolio.</p>
                </div>
            `;
        } else {
            portfolioGrid.replaceChildren();
        }
        if (unpriced.length) {
            const warning = document.createElement('div');
            warning.className = 'error-state';
            warning.textContent = `Prices unavailable for ${unpriced.join(', ')}. Totals exclude these holdings.`;
            portfolioGrid.prepend(warning);
        }
    } catch (error) {
        console.error("Portfolio sync error:", error);
        portfolioGrid.innerHTML = `<div class="error-state">Failed to establish connection with Wealth API.</div>`;
    }
}

function updateSummary(summary) {
    document.getElementById('port-total-invested').innerText = `₹${summary.total_invested.toLocaleString()}`;
    document.getElementById('port-total-current').innerText = `₹${summary.total_current.toLocaleString()}`;
    
    const plEl = document.getElementById('port-total-pl');
    const pctEl = document.getElementById('port-total-pl-pct');
    const isProfit = summary.total_p_l >= 0;
    
    plEl.innerText = `${isProfit ? '+' : ''}₹${summary.total_p_l.toLocaleString()}`;
    pctEl.innerText = `(${isProfit ? '+' : ''}${summary.total_p_l_pct}%)`;
    plEl.style.color = isProfit ? 'var(--color-buy)' : 'var(--color-sell)';
    pctEl.style.color = isProfit ? 'var(--color-buy)' : 'var(--color-sell)';
}

async function removeFromPortfolio(ticker) {
    if (!confirm(`Remove ${ticker} from your manual tracker? This does not place a broker order.`)) return;

    try {
        const response = await fetch(`/api/portfolio/remove/${encodeURIComponent(ticker)}`, {
            method: 'DELETE', headers: {'X-Requested-With': 'XMLHttpRequest'}
        });
        if (response.ok) fetchPortfolio();
    } catch (error) {
        alert("Transaction failed.");
    }
}
