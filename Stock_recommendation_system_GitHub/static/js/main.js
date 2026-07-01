const API_URL = "/api";
let currentData = [];
let currentMode = "daily";
let activeTab = 'recommendations';
let stockChartInstance = null;
let currentChartDetails = null;
let currentFetchAbortController = null;

document.addEventListener("DOMContentLoaded", () => {
    // Auth Check
    if (!localStorage.getItem('masterPredictorAuth') && window.location.pathname.includes('dashboard')) {
        window.location.href = '/login';
    }

    const updateDates = () => {
        const now = new Date();
        const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
        const dateStr = now.toLocaleDateString('en-US', options).toUpperCase();
        
        const el1 = document.getElementById('headerDate');
        const el2 = document.getElementById('currentDateFooter');
        
        if (el1) el1.innerText = dateStr;
        if (el2) el2.innerText = dateStr;
    };
    updateDates();

    // Profile Dropdown Toggle (click-based, reliable)
    const userAvatar = document.getElementById('userAvatar');
    const profileDropdown = document.getElementById('profileDropdown');
    if (userAvatar && profileDropdown) {
        userAvatar.addEventListener('click', (e) => {
            e.stopPropagation();
            profileDropdown.classList.toggle('open');
        });
        // Close dropdown when clicking anywhere outside
        document.addEventListener('click', () => {
            profileDropdown.classList.remove('open');
        });
        profileDropdown.addEventListener('click', (e) => e.stopPropagation());
    }

    // Logout Handler
    const logoutBtn = document.getElementById('userLogout');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', async () => {
            try {
                const res = await fetch(`${API_URL}/logout`, { method: 'POST' });
                if (res.ok) {
                    localStorage.removeItem('masterPredictorAuth');
                    window.location.href = '/login';
                } else {
                    // Force redirect even if API fails
                    localStorage.removeItem('masterPredictorAuth');
                    window.location.href = '/login';
                }
            } catch (err) {
                console.error("Logout failed", err);
                localStorage.removeItem('masterPredictorAuth');
                window.location.href = '/login';
            }
        });
    }

    // Theme Toggle Handler
    const themeBtn = document.getElementById('themeToggle');
    const themeIcon = document.getElementById('themeIcon');
    const themeText = document.getElementById('themeText');

    // Check initial
    if (document.documentElement.classList.contains('dark-mode')) {
        if (themeIcon) setSunIcon(themeIcon);
        if (themeText) themeText.innerText = "Morning Edition";
    } else {
        if (themeIcon) setMoonIcon(themeIcon);
        if (themeText) themeText.innerText = "Evening Edition";
    }

    if (themeBtn) {
        themeBtn.addEventListener('click', () => {
            document.documentElement.classList.toggle('dark-mode');

            if (document.documentElement.classList.contains('dark-mode')) {
                localStorage.setItem('theme', 'dark');
                setSunIcon(themeIcon);
                themeText.innerText = "Morning Edition";
            } else {
                localStorage.setItem('theme', 'light');
                setMoonIcon(themeIcon);
                themeText.innerText = "Evening Edition";
            }

            if (currentChartDetails) {
                renderChart(currentChartDetails);
            }
        });
    }

    if (document.getElementById('stat-total')) {
        fetchSummary();
        fetchRecommendations();
        fetchIndices();
        setupFilters();
        
        // Auto-refresh summary and indices every 60 seconds
        setInterval(fetchSummary, 60000);
        setInterval(fetchIndices, 60000);

        // Mode Toggle Handler
        const modeDaily = document.getElementById('modeDaily');
        const modeIntraday = document.getElementById('modeIntraday');

        if (modeDaily && modeIntraday) {
            const handleModeChange = (mode) => {
                if (currentMode === mode) return;
                currentMode = mode;
                
                // Update UI
                modeDaily.classList.toggle('active', mode === 'daily');
                modeIntraday.classList.toggle('active', mode === 'intraday');

                // Refresh Data
                fetchSummary();
                fetchRecommendations();

                // Update Modal Text if open
                const predictLabel = document.querySelector('.price-container .price-block:last-child .price-label');
                if (predictLabel) {
                    predictLabel.innerText = mode === 'intraday' ? 'Projected Index for the next hour' : 'Projected Index for the next day';
                }
            };

            modeDaily.addEventListener('click', () => handleModeChange('daily'));
            modeIntraday.addEventListener('click', () => handleModeChange('intraday'));
        }
    }

    // Add to Portfolio Handler
    const addToPortfolioBtn = document.getElementById('addToPortfolioBtn');
    const portfolioInputs = document.getElementById('portfolioInputs');
    if (addToPortfolioBtn) {
        addToPortfolioBtn.addEventListener('click', () => {
            if (portfolioInputs.style.display === 'none') {
                // First click: show inputs
                portfolioInputs.style.display = 'flex';
                addToPortfolioBtn.innerHTML = '<svg viewBox="0 0 24 24" class="icon" style="margin-right: 4px;"><path d="M5 12h14" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"></path></svg> Confirm Addition';
            } else {
                // Second click: perform add
                const ticker = document.getElementById('detailTicker').innerText;
                const qty = document.getElementById('portfolioQty').value;
                const price = document.getElementById('portfolioPrice').value;
                addToPortfolio(ticker, qty, price);
            }
        });
    }

    // Chart Expansion Handler
    const expandBtn = document.getElementById('expandChartBtn');
    const chartWrapper = document.getElementById('chartWrapper');
    if (expandBtn && chartWrapper) {
        expandBtn.addEventListener('click', () => {
            chartWrapper.classList.toggle('expanded');
            if (stockChartInstance) {
                // Must resize after CSS transition/class toggle
                setTimeout(() => stockChartInstance.resize(), 10);
            }
        });
    }

    // Modal Close Handler
    const closeModalBtn = document.getElementById('modalCloseBtn');
    if (closeModalBtn) {
        closeModalBtn.addEventListener('click', () => {
            document.getElementById('stockModal').style.display = 'none';
            if (portfolioInputs) {
                portfolioInputs.style.display = 'none'; // Reset inputs
                const btn = document.getElementById('addToPortfolioBtn');
                if (btn) btn.innerHTML = '<svg viewBox="0 0 24 24" class="icon" style="margin-right: 4px;"><path d="M12 5v14M5 12h14" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"></path></svg> Add to Portfolio';
            }
            if (currentFetchAbortController) {
                currentFetchAbortController.abort();
            }
            if (stockChartInstance) {
                stockChartInstance.destroy();
                stockChartInstance = null;
            }
        });
    }
});

function setSunIcon(svg) {
    svg.innerHTML = `<circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>`;
}

function setMoonIcon(svg) {
    svg.innerHTML = `<path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"></path>`;
}

function refreshDashboard() {
    fetchSummary();
    fetchRecommendations();
}

function switchTab(tab) {
    activeTab = tab;
    
    // Update button states
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    const activeBtn = document.querySelector(`button[onclick="switchTab('${tab}')"]`);
    if (activeBtn) activeBtn.classList.add('active');

    // Show/Hide sections
    const recSec = document.getElementById('recommendationsSection');
    const alphaSec = document.getElementById('tradingAlphaSection');
    const riskSec = document.getElementById('riskMonitorSection');
    const valSec = document.getElementById('validationSection');

    if (recSec) recSec.style.display = (tab === 'recommendations' || tab === 'intraday') ? 'block' : 'none';
    if (alphaSec) alphaSec.style.display = (tab === 'trading-alpha') ? 'block' : 'none';
    if (riskSec) riskSec.style.display = (tab === 'risk-monitor') ? 'block' : 'none';
    if (valSec) valSec.style.display = (tab === 'validation') ? 'block' : 'none';

    if (tab === 'trading-alpha' || tab === 'risk-monitor') {
        fetchTradingAlpha();
    } else if (tab === 'validation') {
        fetchPaperTrading();
    } else {
        currentMode = (tab === 'intraday') ? 'intraday' : 'daily';
        refreshDashboard();
    }
}

async function fetchPaperTrading() {
    const tableBody = document.getElementById('paperTradesBody');
    const positionsBody = document.getElementById('paperPositionsBody');
    
    if (tableBody) tableBody.innerHTML = '<tr><td colspan="5" style="text-align:center">Fetching shadow data...</td></tr>';
    if (positionsBody) positionsBody.innerHTML = '<tr><td colspan="6" style="text-align:center">Fetching shadow positions...</td></tr>';

    try {
        const response = await fetch('/api/paper-trading');
        const data = await response.json();
        
        const capital = data.capital || 1000000;
        const latestEquity = data.equity_history[data.equity_history.length - 1];
        const totalPL = ((latestEquity.equity - capital) / capital * 100).toFixed(2);
        const plClass = totalPL >= 0 ? 'BUY' : 'SELL';

        document.getElementById('startingCapital').innerText = `₹${capital.toLocaleString()}`;
        document.getElementById('paperEquity').innerText = `₹${latestEquity.equity.toLocaleString()}`;
        document.getElementById('paperCash').innerText = `₹${data.cash.toLocaleString()}`;
        document.getElementById('paperTotalPL').innerText = `${totalPL}%`;
        document.getElementById('paperTotalPL').className = `stat-val ${plClass}`;
        
        // 1. Render Positions
        if (positionsBody) {
            positionsBody.innerHTML = '';
            const positions = data.positions || {};
            const tickers = Object.keys(positions);
            
            if (tickers.length === 0) {
                positionsBody.innerHTML = '<tr><td colspan="6" style="text-align:center">No active positions.</td></tr>';
            } else {
                tickers.forEach(ticker => {
                    const pos = positions[ticker];
                    const entryPrice = pos.entry_price || 0;
                    
                    // Try to find current price from recommendation data
                    const liveData = currentData.find(s => (s.Stock || s.ticker) === ticker);
                    const currentPrice = liveData ? (liveData.Price || liveData.price || entryPrice) : entryPrice;
                    
                    const currentVal = (pos.qty * currentPrice);
                    const plPct = entryPrice > 0 ? ((currentPrice - entryPrice) / entryPrice * 100).toFixed(2) : "0.00";
                    const plClass = parseFloat(plPct) >= 0 ? 'BUY' : 'SELL';
                    
                    const row = document.createElement('tr');
                    row.innerHTML = `
                        <td><strong>${ticker}</strong></td>
                        <td><span class="classic-badge ${pos.side}">${pos.side}</span></td>
                        <td>${pos.qty}</td>
                        <td>₹${entryPrice.toFixed(2)}</td>
                        <td>₹${currentVal.toFixed(2)}</td>
                        <td><span class="classic-badge ${plClass}">${plPct}%</span></td>
                    `;
                    positionsBody.appendChild(row);
                });
            }
        }

        // 2. Render Trades
        if (tableBody) {
            tableBody.innerHTML = '';
            const trades = data.trades || [];
            if (trades.length === 0) {
                tableBody.innerHTML = '<tr><td colspan="5" style="text-align:center">No trade history.</td></tr>';
            } else {
                [...trades].reverse().forEach(t => {
                    const row = document.createElement('tr');
                    row.innerHTML = `
                        <td style="font-size: 11px;">${t.timestamp}</td>
                        <td><strong>${t.ticker}</strong></td>
                        <td><span class="classic-badge ${t.type}">${t.type}</span></td>
                        <td>₹${t.price.toFixed(2)}</td>
                        <td>₹${t.cash_remaining.toLocaleString()}</td>
                    `;
                    tableBody.appendChild(row);
                });
            }
        }
    } catch (error) {
        console.error("Paper Error:", error);
        if (tableBody) tableBody.innerHTML = '<tr><td colspan="5" style="text-align:center">Error loading paper data.</td></tr>';
    }
}

async function fetchTradingAlpha() {
    const grid = document.getElementById('alphaSignalsGrid');
    grid.innerHTML = '<div class="loading-state">Performing Cross-Sectional Ranking...</div>';

    try {
        const response = await fetch('/api/trading-alpha');
        const data = await response.json();
        
        document.getElementById('marketRegime').innerText = data.market_regime;
        document.getElementById('marketRegime').style.color = data.market_regime === 'BULL' ? 'var(--color-buy)' : 'var(--color-sell)';
        
        // Update Risk Gauges
        if (data.risk_metrics) {
            const gross = (data.risk_metrics.gross_exposure * 100).toFixed(1);
            const net = (data.risk_metrics.net_exposure * 100).toFixed(1);
            document.getElementById('grossExpBar').style.width = `${Math.min(gross, 100)}%`;
            document.getElementById('grossExpVal').innerText = `${gross}%`;
            document.getElementById('netExpBar').style.width = `${Math.min(Math.abs(net) * 10, 100)}%`; // Scaled for visibility
            document.getElementById('netExpVal').innerText = `${net}%`;
        }

        renderAlphaCards(data.signals);
    } catch (error) {
        console.error("Alpha Error:", error);
        grid.innerHTML = '<div class="error-state">Alpha Intelligence Stream Disrupted.</div>';
    }
}

function renderAlphaCards(signals) {
    const grid = document.getElementById('alphaSignalsGrid');
    grid.innerHTML = '';

    signals.forEach((s, index) => {
        const card = document.createElement('div');
        card.className = `stock-card signal-${s.signal.toLowerCase()}`;
        
        const priceChange = (s.pred_return * 100).toFixed(2);
        const sign = s.pred_return > 0 ? '+' : '';
        
        card.innerHTML = `
            <div class="card-header">
                <span class="ticker">${s.ticker}</span>
                <span class="signal-badge ${s.signal}">${s.signal}</span>
            </div>
            <div class="card-body">
                <div class="pred-return">Exp. 5D Return: <span class="val">${sign}${priceChange}%</span></div>
                <div class="allocation-info">
                    <div class="alloc-row"><span>Allocation:</span> <span class="val">₹${s.allocation.toLocaleString()}</span></div>
                    <div class="alloc-row"><span>Quantity:</span> <span class="val">${s.quantity} units</span></div>
                </div>
            </div>
            <div class="card-footer">
                <div class="weight-bar"><div class="fill" style="width: ${s.weight*200}%"></div></div>
                <span class="weight-label">Risk Weight: ${(s.weight*100).toFixed(1)}%</span>
            </div>
        `;
        grid.appendChild(card);
    });
}

// Fetch summary stats
async function fetchSummary() {
    try {
        const response = await fetch(`${API_URL}/summary?mode=${currentMode}`);
        if (!response.ok) throw new Error("Failed to load summary");

        const data = await response.json();

        document.getElementById("stat-total").innerText = data.total_stocks || 0;
        document.getElementById("stat-buy").innerText = data.buy_signals || 0;
        document.getElementById("stat-sell").innerText = data.sell_signals || 0;
        document.getElementById("stat-date").innerText = data.latest_date || "Unknown";
    } catch (e) {
        console.error("Dashboard error:", e);
    }
}

// Show skeleton loaders in the grid
function showSkeletons() {
    const grid = document.getElementById("recommendationGrid");
    if (!grid) return;
    grid.innerHTML = "";
    for (let i = 0; i < 8; i++) {
        const skeleton = document.createElement("div");
        skeleton.className = "stock-card skeleton-card";
        skeleton.style.pointerEvents = "none";
        skeleton.style.opacity = "1";
        skeleton.innerHTML = `
            <div class="card-header" style="border:none;">
                <div class="skeleton" style="width: 80px; height: 24px;"></div>
                <div class="skeleton" style="width: 40px; height: 16px;"></div>
            </div>
            <div class="metric-row"><div class="skeleton" style="width: 60px; height: 12px;"></div><div class="skeleton" style="width: 40px; height: 12px;"></div></div>
            <div class="metric-row"><div class="skeleton" style="width: 60px; height: 12px;"></div><div class="skeleton" style="width: 40px; height: 12px;"></div></div>
            <div class="prob-container">
                <div class="skeleton" style="width: 100%; height: 6px;"></div>
            </div>
        `;
        grid.appendChild(skeleton);
    }
}

// Fetch main grid data
async function fetchRecommendations() {
    const grid = document.getElementById("recommendationGrid");
    if (!grid) return;

    showSkeletons();

    try {
        const response = await fetch(`${API_URL}/recommendations?mode=${currentMode}`);
        if (!response.ok) throw new Error("Failed to load recommendations");

        currentData = await response.json();
        renderGrid(currentData);

        if (currentData.length > 0) {
            loadStockDetail(currentData[0].Stock);
        }
    } catch (e) {
        grid.innerHTML = `<div class="loading-state"><p style="color:var(--color-sell)">Error loading data. Ensure AI model has run today.</p></div>`;
        console.error("Data error:", e);
    }
}

// Render grid from array
function renderGrid(data) {
    const grid = document.getElementById("recommendationGrid");
    grid.innerHTML = "";

    if (data.length === 0) {
        grid.innerHTML = `<p style="grid-column: 1/-1; text-align: center; color: var(--text-secondary); padding: 40px; font-family: 'Merriweather', serif; font-style: italic;">No listings match criteria.</p>`;
        return;
    }

    data.forEach((stock, index) => {
        const ticker = stock.Stock || "N/A";
        const rec = stock.Recommendation || "HOLD";
        const prob = ((stock.Prob_Up || 0) * 100).toFixed(1);

        const rawReturn = (stock.Return || 0) * 100;
        const returnClass = rawReturn >= 0 ? "BUY" : "SELL";
        const returnDisplay = (rawReturn >= 0 ? "+" : "") + rawReturn.toFixed(2) + "%";

        const rsi = (stock.RSI || 0).toFixed(1);

        const card = document.createElement("div");
        card.className = `stock-card ${rec}`;
        card.dataset.ticker = ticker;

        // Setup initial active state for the first item
        if (index === 0) card.classList.add('active-card');

        card.innerHTML = `
            <div class="card-header">
                <span class="ticker">${ticker}</span>
                <span class="classic-badge ${rec}">${rec}</span>
            </div>
            
            <div class="metric-row">
                <span class="metric-label">Daily Return</span>
                <span class="metric-value ${returnClass}">${returnDisplay}</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">RSI Index</span>
                <span class="metric-value">${rsi}</span>
            </div>
            
            <div class="prob-container">
                <div class="prob-label">
                    <span>Upward Propensity</span>
                    <span>${prob}%</span>
                </div>
                <div class="prob-bar-bg">
                    <div class="prob-bar-fill" style="width: 0%"></div>
                </div>
            </div>
        `;

        card.addEventListener('click', () => {
            document.querySelectorAll('.stock-card').forEach(c => c.classList.remove('active-card'));
            card.classList.add('active-card');
            loadStockDetail(ticker);
        });

        grid.appendChild(card);

        setTimeout(() => {
            const fill = card.querySelector('.prob-bar-fill');
            if (fill) fill.style.width = `${prob}%`;
        }, 50);
    });
}

// API Call for Chart Detail
async function loadStockDetail(ticker, alias = null) {
    const modal = document.getElementById('stockModal');
    if (modal) modal.style.display = 'flex';

    document.getElementById('detailTicker').innerText = alias || ticker;
    
    // Show loading state for chart & news
    const chartLoading = document.getElementById('chartLoadingOverlay');
    if (chartLoading) chartLoading.style.display = 'flex';
    
    const newsContainer = document.getElementById('newsContainer');
    if (newsContainer) {
        newsContainer.innerHTML = `<p class="news-loading"><em>Scanning for recent developments...</em></p>`;
    }
    
    // Cancel any pending fetch to prevent overlapping redrawing
    if (currentFetchAbortController) {
        currentFetchAbortController.abort();
    }
    currentFetchAbortController = new AbortController();
    const signal = currentFetchAbortController.signal;

    try {
        const res = await fetch(`${API_URL}/live/${encodeURIComponent(ticker)}?mode=${currentMode}`, { signal });
        if (!res.ok) throw new Error("Failed to fetch live history");
        const data = await res.json();

        // 1. Update Badges & Prices
        const suggestion = data.suggestion || 'HOLD';
        const badge = document.getElementById('detailBadge');
        if (badge) {
            badge.innerText = suggestion;
            badge.className = `classic-badge ${suggestion}`;
        }

        const currentPr = data.current_price ? Number(data.current_price) : 0;
        const predictPr = data.predicted_price ? Number(data.predicted_price) : currentPr;

        const isIndex = ticker.startsWith('^');
        const currency = isIndex ? "" : "₹"; // Indices are usually points

        document.getElementById('detailCurrent').innerText = currentPr ? `${currency}${currentPr.toLocaleString('en-US', {minimumFractionDigits: 2})}` : "--";
        document.getElementById('detailPredicted').innerText = predictPr ? `${currency}${predictPr.toLocaleString('en-US', {minimumFractionDigits: 2})}` : "--";

        // Set default price in portfolio input
        const priceInput = document.getElementById('portfolioPrice');
        if (priceInput) priceInput.value = currentPr;

        // 2. Update Sentiment
        const sentLabel = data.sentiment_label || 'neutral';
        const sentScore = data.sentiment_score || 0;
        const sentPct   = Math.round(((sentScore + 1) / 2) * 100);
        const sentColor = sentLabel === 'positive' ? 'var(--color-buy)' :
                          sentLabel === 'negative' ? 'var(--color-sell)' : 'var(--color-hold)';

        const dSentBadge = document.getElementById('detailSentimentBadge');
        if (dSentBadge) {
            dSentBadge.innerText = sentLabel;
            dSentBadge.className = `live-sentiment-badge ${sentLabel}`;
        }

        const dSentBar = document.getElementById('detailSentimentBar');
        if (dSentBar) {
            dSentBar.style.width      = `${sentPct}%`;
            dSentBar.style.background = sentColor;
        }

        const dSentScore = document.getElementById('detailSentimentScore');
        if (dSentScore) {
            dSentScore.innerText = `(${sentScore >= 0 ? '+' : ''}${sentScore.toFixed(3)})`;
        }

        // 3. Render Chart
        // The endpoint returns price_history = { dates: [...], prices: [...] }
        const chartDetails = {
            current_price: currentPr,
            predicted_price: predictPr,
            dates: data.price_history?.dates || [],
            prices: data.price_history?.prices || []
        };
        currentChartDetails = chartDetails;
        renderChart(chartDetails);
        
        // Hide chart loading state
        if (chartLoading) chartLoading.style.display = 'none';

        // 4. Update News
        if (newsContainer) {
            const headlines = data.headlines || [];
            newsContainer.innerHTML = "";
            
            if (headlines.length === 0) {
                newsContainer.innerHTML = `<p class="news-loading">No recent intelligence available for this listing.</p>`;
            } else {
                headlines.forEach((h, index) => {
                    newsContainer.innerHTML += `
                        <div class="news-item">
                            <a href="${h.url}" target="_blank" class="news-title">${h.title}</a>
                            <div class="news-meta">
                                <span>${h.source}</span>
                            </div>
                        </div>
                    `;
                });
            }
        }

    } catch (e) {
        if (e.name === 'AbortError') {
            console.log(`Fetch aborted for ${ticker}`);
            return;
        }
        console.error("Live detail error:", e);
        document.getElementById('detailCurrent').innerText = "₹Err";
        document.getElementById('detailPredicted').innerText = "₹Err";
        if (newsContainer) {
            newsContainer.innerHTML = `<p class="news-loading" style="color:var(--color-sell)">Error establishing wire connection.</p>`;
        }
        if (chartLoading) chartLoading.style.display = 'none';
    }
}

// Render Chart.js
function renderChart(details) {
    const ctx = document.getElementById('stockChart').getContext('2d');

    if (stockChartInstance) {
        stockChartInstance.destroy();
    }

    // Fallbacks if data is missing
    const validPrices = details.prices || [];
    const validDates = details.dates || [];
    const currentPr = details.current_price || 0;
    const predictPr = details.predicted_price || currentPr;

    const projectionLabel = currentMode === 'intraday' ? "Projected (H+1)" : "Projected (T+1)";
    const labels = [...validDates, projectionLabel];
    const data = [...validPrices, predictPr];

    const isBuy = predictPr >= currentPr;

    // Read exact Newspaper CSS variables for Chart colors
    const style = getComputedStyle(document.body);
    const textColor = style.getPropertyValue('--text-primary').trim() || '#181818';
    const gridColor = style.getPropertyValue('--chart-grid').trim() || '#dcd6c8';

    const colorLine = textColor; // Newspaper prints with black ink mostly
    const colorBg = style.getPropertyValue('--bg-surface').trim();

    const signalColor = isBuy ?
        (style.getPropertyValue('--color-buy').trim() || '#1c6d36') :
        (style.getPropertyValue('--color-sell').trim() || '#901919');

    // Create Gradient for the line fill
    const gradientBg = ctx.createLinearGradient(0, 0, 0, 320);
    // Convert hex or rgb to a faded rgba based on signal
    const fadeColor = isBuy ? 'rgba(79, 161, 105, 0.4)' : 'rgba(201, 76, 76, 0.4)';
    const fadeTo = isBuy ? 'rgba(79, 161, 105, 0.0)' : 'rgba(201, 76, 76, 0.0)';

    gradientBg.addColorStop(0, fadeColor);
    gradientBg.addColorStop(1, fadeTo);

    stockChartInstance = new Chart(ctx, {
        type: 'line',
        plugins: [{
            id: 'crosshair',
            afterDraw: (chart) => {
                if (chart.tooltip?._active?.length) {
                    const x = chart.tooltip._active[0].element.x;
                    const yAxis = chart.scales.y;
                    const ctx = chart.ctx;
                    ctx.save();
                    ctx.beginPath();
                    ctx.moveTo(x, yAxis.top);
                    ctx.lineTo(x, yAxis.bottom);
                    ctx.lineWidth = 1;
                    ctx.strokeStyle = style.getPropertyValue('--border-light').trim() || '#b0a896';
                    ctx.setLineDash([3, 3]);
                    ctx.stroke();
                    ctx.restore();
                }
            }
        }],
        data: {
            labels: labels,
            datasets: [{
                label: `Relative Index`,
                data: data,
                borderColor: colorLine,
                backgroundColor: gradientBg, // Apply gradient here
                borderWidth: 2,
                pointRadius: 0,
                pointHoverRadius: 5,
                pointBackgroundColor: colorLine,
                pointBorderColor: colorBg,
                pointBorderWidth: 2,
                fill: true,
                tension: 0.2, // Add slight curve for less "picture" feel
                segment: {
                    borderDash: ctx => ctx.p1DataIndex === data.length - 1 ? [4, 4] : undefined,
                    borderColor: ctx => ctx.p1DataIndex === data.length - 1 ? signalColor : colorLine
                }
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: {
                duration: 1000,
                easing: 'easeOutQuart'
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    enabled: true,
                    mode: 'index',
                    intersect: false,
                    backgroundColor: 'rgba(255, 255, 255, 0.9)',
                    titleColor: '#181818',
                    bodyColor: '#181818',
                    borderColor: '#181818',
                    borderWidth: 1,
                    padding: 10,
                    cornerRadius: 0,
                    titleFont: { family: "'Arial', sans-serif", size: 12, weight: 'bold' },
                    bodyFont: { family: "'Merriweather', serif", size: 14 },
                    callbacks: {
                        label: function (context) {
                            const ticker = document.getElementById('detailTicker').innerText;
                            const isIndex = ticker.includes(' ') || ticker.startsWith('^'); // Indices have names or ^
                            const prefix = isIndex ? "" : "₹";
                            return "Value: " + prefix + context.parsed.y.toLocaleString('en-US', {minimumFractionDigits: 2});
                        }
                    }
                }
            },
            interaction: {
                intersect: false,
                mode: 'index',
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: {
                        color: textColor,
                        font: { family: "'Arial', sans-serif", size: 10, weight: 'bold' },
                        maxRotation: 0,
                        autoSkip: true,
                        maxTicksLimit: 6
                    }
                },
                y: {
                    grid: { 
                        color: gridColor,
                        drawBorder: false
                    },
                    ticks: {
                        color: textColor,
                        font: { family: "'Playfair Display', serif", size: 12 },
                        callback: function (value) {
                            const ticker = document.getElementById('detailTicker').innerText;
                            const isIndex = ticker.includes(' ') || ticker.startsWith('^');
                            const prefix = isIndex ? "" : "₹";
                            if (value >= 1000) return prefix + (value / 1000) + 'k';
                            return prefix + value;
                        },
                    }
                }
            }
        }
    });
}

// Setup search & filters
function setupFilters() {
    const searchInput = document.getElementById("searchInput");
    const filterBtns = document.querySelectorAll(".filter-btn");

    let activeFilter = "ALL";
    let searchQuery = "";

    const applyFilters = () => {
        let filtered = currentData;

        if (searchQuery) {
            filtered = filtered.filter(s => s.Stock.toLowerCase().includes(searchQuery));
        }

        if (activeFilter !== "ALL") {
            filtered = filtered.filter(s => s.Recommendation === activeFilter);
        }

        renderGrid(filtered);
    };

    searchInput.addEventListener("input", (e) => {
        searchQuery = e.target.value.toLowerCase();
        applyFilters();
    });

    filterBtns.forEach(btn => {
        btn.addEventListener("click", (e) => {
            filterBtns.forEach(b => b.classList.remove("active"));
            e.target.classList.add("active");
            activeFilter = e.target.dataset.filter;
            applyFilters();
        });
    });
}

// ================================
// MARKET PULSE (GLOBAL INDEXES)
// ================================
async function fetchIndices() {
    const pulseContainer = document.getElementById('pulseContainer');
    if (!pulseContainer) return;

    try {
        const response = await fetch('/api/indices');
        if (!response.ok) throw new Error('Pulse endpoint failure');
        
        const data = await response.json();
        
        if (data && data.length > 0) {
            pulseContainer.innerHTML = '';
            data.forEach((index, i) => {
                const isUp = index.change >= 0;
                const changeClass = isUp ? 'pulse-up' : 'pulse-down';
                const sign = index.change > 0 ? '+' : '';
                
                const item = document.createElement('div');
                item.className = 'pulse-item';
                item.setAttribute('data-ticker', index.ticker);
                item.innerHTML = `
                    <div>
                        <div class="pulse-index-name">${index.name}</div>
                        <div class="pulse-index-val">${index.price.toLocaleString('en-US', { minimumFractionDigits: 2 })}</div>
                        <div class="pulse-index-change ${changeClass}">
                            ${sign}${index.change.toFixed(2)} (${sign}${index.pct_change.toFixed(2)}%)
                        </div>
                    </div>
                    <div class="pulse-sparkline-wrap">
                        <canvas id="sparkline-${i}" class="pulse-sparkline"></canvas>
                    </div>
                `;
                
                item.addEventListener('click', () => loadStockDetail(index.ticker, index.name));
                pulseContainer.appendChild(item);
                
                // Draw sparkline after appending
                if (index.history && index.history.length > 0) {
                    setTimeout(() => drawSparkline(`sparkline-${i}`, index.history, isUp), 10);
                }
            });
        }
    } catch (error) {
        console.error("Pulse failure:", error);
        pulseContainer.innerHTML = `<p class="news-loading" style="color:var(--color-sell)"><em>Global signal lost. Reconnecting...</em></p>`;
    }
}

// ================================
// PORTFOLIO LOGIC
// ================================

async function fetchPortfolio() {
    const portfolioGrid = document.getElementById('portfolioGrid');
    const summaryBar = document.getElementById('portfolioSummary');
    if (!portfolioGrid) return;

    try {
        const response = await fetch('/api/portfolio');
        if (!response.ok) throw new Error('Portfolio endpoint failure');
        
        const data = await response.json();
        const holdings = data.holdings || [];
        const summary = data.summary || {};
        
        if (holdings.length > 0) {
            portfolioGrid.innerHTML = '';
            holdings.forEach((item) => {
                const isProfit = item.p_l >= 0;
                const plClass = isProfit ? 'pl-positive' : 'pl-negative';
                
                const card = document.createElement('div');
                card.className = 'portfolio-item';
                card.innerHTML = `
                    <div class="ticker">
                        <strong>${item.ticker}</strong>
                        <button class="remove-portfolio-btn" onclick="removeFromPortfolio('${item.ticker}')" title="Remove from Portfolio">
                            <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none"><path d="M18 6L6 18M6 6l12 12"></path></svg>
                        </button>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Holdings</span>
                        <span class="metric-value">${item.quantity} @ ₹${item.purchase_price.toLocaleString()}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Basis / Current</span>
                        <span class="metric-value">₹${item.cost_basis.toLocaleString()} / ₹${item.current_value.toLocaleString()}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Gain / Loss</span>
                        <span class="metric-value ${plClass}">${isProfit ? '+' : ''}₹${item.p_l.toLocaleString()} (${item.p_l_pct}%)</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Est. Value (T+1)</span>
                        <span class="metric-value">₹${item.predicted_value.toLocaleString()}</span>
                    </div>
                `;
                card.addEventListener('click', (e) => {
                    if (!e.target.closest('.remove-portfolio-btn')) {
                        loadStockDetail(item.ticker);
                    }
                });
                portfolioGrid.appendChild(card);
            });

            // Update Summary
            if (summaryBar) {
                summaryBar.style.display = 'grid';
                document.getElementById('port-total-invested').innerText = `₹${summary.total_invested.toLocaleString()}`;
                document.getElementById('port-total-current').innerText = `₹${summary.total_current.toLocaleString()}`;
                document.getElementById('port-total-predicted').innerText = `₹${summary.total_predicted.toLocaleString()}`;
                
                const totalPl = document.getElementById('port-total-pl');
                const totalPlPct = document.getElementById('port-total-pl-pct');
                const isTotalProfit = summary.total_p_l >= 0;
                
                totalPl.innerText = `${isTotalProfit ? '+' : ''}₹${summary.total_p_l.toLocaleString()}`;
                totalPlPct.innerText = `(${isTotalProfit ? '+' : ''}${summary.total_p_l_pct}%)`;
                
                const plWrap = document.getElementById('port-total-pl-wrap');
                plWrap.className = `summary-item ${isTotalProfit ? 'pl-positive' : 'pl-negative'}`;
            }
        } else {
            portfolioGrid.innerHTML = `<p class="news-loading"><em>Your portfolio is currently empty. Add stocks from the "Live Wire" modal.</em></p>`;
            if (summaryBar) summaryBar.style.display = 'none';
        }
    } catch (error) {
        console.error("Portfolio failure:", error);
        portfolioGrid.innerHTML = `<p class="news-loading" style="color:var(--color-sell)"><em>Failed to sync portfolio.</em></p>`;
    }
}

async function addToPortfolio(ticker, quantity, purchase_price) {
    const btn = document.getElementById('addToPortfolioBtn');
    if (btn) btn.disabled = true;

    try {
        const response = await fetch('/api/portfolio/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ticker, quantity, purchase_price })
        });
        
        const result = await response.json();
        if (response.ok) {
            fetchPortfolio(); // Refresh grid
            // Subtle feedback
            const originalHTML = btn.innerHTML;
            btn.style.background = 'var(--color-buy)';
            btn.innerHTML = 'Position Updated!';
            
            // Hide inputs
            document.getElementById('portfolioInputs').style.display = 'none';

            setTimeout(() => {
                btn.style.background = '';
                btn.innerHTML = '<svg viewBox="0 0 24 24" class="icon" style="margin-right: 4px;"><path d="M12 5v14M5 12h14" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"></path></svg> Add to Portfolio';
                btn.disabled = false;
            }, 2000);
        } else {
            alert(result.error || "Failed to add to portfolio");
            if (btn) btn.disabled = false;
        }
    } catch (error) {
        console.error("Add to portfolio error:", error);
        if (btn) btn.disabled = false;
    }
}

async function removeFromPortfolio(ticker) {
    if (!confirm(`Remove ${ticker} from your portfolio?`)) return;

    try {
        const response = await fetch(`/api/portfolio/remove/${encodeURIComponent(ticker)}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            fetchPortfolio();
        } else {
            const result = await response.json();
            alert(result.error || "Failed to remove item");
        }
    } catch (error) {
        console.error("Remove from portfolio error:", error);
    }
}

function drawSparkline(canvasId, data, isPositive) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    const width = canvas.offsetWidth;
    const height = canvas.offsetHeight;
    
    // Scale for Retina
    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);

    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;
    
    ctx.beginPath();
    ctx.lineWidth = 1.5;
    ctx.strokeStyle = isPositive ? '#2ecc71' : '#e74c3c';
    ctx.lineJoin = 'round';
    
    data.forEach((val, i) => {
        const x = (i / (data.length - 1)) * width;
        const y = height - ((val - min) / range) * height;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    });
    
    ctx.stroke();
    
    // Gradient fill
    ctx.lineTo(width, height);
    ctx.lineTo(0, height);
    ctx.closePath();
    const grad = ctx.createLinearGradient(0, 0, 0, height);
    grad.addColorStop(0, isPositive ? 'rgba(46, 204, 113, 0.1)' : 'rgba(231, 76, 60, 0.1)');
    grad.addColorStop(1, 'transparent');
    ctx.fillStyle = grad;
    ctx.fill();
}

// ─────────────────────────────────────────
// LIVE MARKET WIRE
// ─────────────────────────────────────────

function setupLiveWire() {
    const input = document.getElementById('liveTickerInput');
    const btn   = document.getElementById('liveFetchBtn');
    if (!input || !btn) return;

    btn.addEventListener('click', () => {
        const ticker = input.value.trim().toUpperCase();
        if (ticker) fetchLiveData(ticker);
    });

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            const ticker = input.value.trim().toUpperCase();
            if (ticker) fetchLiveData(ticker);
        }
    });
}

async function fetchLiveData(ticker) {
    const card    = document.getElementById('liveResultCard');
    const loading = document.getElementById('liveLoadingState');
    const errBox  = document.getElementById('liveErrorState');

    // Show loading, hide previous states
    card.style.display    = 'none';
    errBox.style.display  = 'none';
    loading.style.display = 'block';

    const btn = document.getElementById('liveFetchBtn');
    if (btn) btn.disabled = true;

    try {
        const res  = await fetch(`${API_URL}/live/${encodeURIComponent(ticker)}`);
        const data = await res.json();
        loading.style.display = 'none';
        if (btn) btn.disabled = false;

        if (!res.ok) {
            errBox.textContent  = `⚠ ${data.error || 'Failed to fetch live data.'}`;
            errBox.style.display = 'block';
            return;
        }

        renderLiveResult(data);

    } catch (err) {
        loading.style.display = 'none';
        if (btn) btn.disabled = false;
        errBox.textContent  = '⚠ Network error. Make sure the server is running.';
        errBox.style.display = 'block';
    }
}

function renderLiveResult(data) {
    const card = document.getElementById('liveResultCard');

    // Ticker name + suggestion badge
    document.getElementById('liveTickerName').innerText = data.ticker || '--';
    const badge = document.getElementById('liveSuggestionBadge');
    badge.innerText  = data.suggestion || '--';
    badge.className  = `classic-badge live-suggestion-badge ${data.suggestion || ''}`;

    // Prices
    const curPrice  = data.current_price   ? `₹${Number(data.current_price).toFixed(2)}`   : '₹--';
    const predPrice = data.predicted_price ? `₹${Number(data.predicted_price).toFixed(2)}` : '₹--';
    document.getElementById('liveCurrentPrice').innerText   = curPrice;
    document.getElementById('livePredictedPrice').innerText = predPrice;

    // Sentiment badge + bar
    const label     = data.sentiment_label || 'neutral';
    const score     = data.sentiment_score || 0;                // -1 to +1
    const barPct    = Math.round(((score + 1) / 2) * 100);     // map to 0–100%
    const barColor  = label === 'positive' ? 'var(--color-buy)' :
                      label === 'negative' ? 'var(--color-sell)' : 'var(--color-hold)';

    const sentBadge = document.getElementById('liveSentimentBadge');
    sentBadge.innerText  = label;
    sentBadge.className  = `live-sentiment-badge ${label}`;

    const sentBar = document.getElementById('liveSentimentBar');
    sentBar.style.width      = `${barPct}%`;
    sentBar.style.background = barColor;

    document.getElementById('liveSentimentScore').innerText = `(${score >= 0 ? '+' : ''}${score.toFixed(3)})`;

    // Headlines
    const list = document.getElementById('liveHeadlinesList');
    list.innerHTML = '';
    const headlines = data.headlines || [];

    if (headlines.length === 0) {
        list.innerHTML = '<li style="font-style:italic;color:var(--text-secondary);font-size:12px;">No recent headlines found.</li>';
    } else {
        headlines.forEach(h => {
            const li = document.createElement('li');
            li.className = 'live-headline-item';
            li.innerHTML = `
                <a href="${h.url}" target="_blank" rel="noopener">${h.title}</a>
                <span class="live-headline-source">— ${h.source}</span>
            `;
            list.appendChild(li);
        });
    }

    card.style.display = 'block';
}
