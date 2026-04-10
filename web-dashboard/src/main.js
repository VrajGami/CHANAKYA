// state.js / configuration
const marketPulseState = new Map();
const feedContainer = document.getElementById('agent-feed');
const watchlistBody = document.getElementById('watchlist-body');
const ledgerBody = document.getElementById('ledger-body');
const netLiqEl = document.getElementById('net-liquidation');
const pnlEl = document.getElementById('total-pnl');
const regimeStatusEl = document.getElementById('regime-status');
const logCountEl = document.getElementById('log-count');

// Feature Diags
const diagZ = document.getElementById('diag-zscore');
const diagRSI = document.getElementById('diag-rsi');
const diagSent = document.getElementById('diag-sentiment');
const diagVol = document.getElementById('diag-vol');

// Metrics Elements
const systemClockEl = document.getElementById('system-clock');
const cagrEl = document.getElementById('metric-cagr');
const sharpeEl = document.getElementById('metric-sharpe');
const winrateEl = document.getElementById('metric-winrate');
const ddEl = document.getElementById('metric-drawdown');

// State
let currentSimDate = null;
let totalLogs = 0;
let isPaused = false;

// Utils
const formatMoney = (val) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(val);

// Chart Instances
let portfolioChart;
const maxPoints = 500;

function initCharts() {
    const ctx1 = document.getElementById('portfolioChart').getContext('2d');
    portfolioChart = new Chart(ctx1, {
        type: 'line',
        data: { labels: [], datasets: [{
            label: 'Net Liquidation ($)', data: [],
            borderColor: '#10b981', backgroundColor: 'rgba(16, 185, 129, 0.05)',
            borderWidth: 1.5, fill: true, tension: 0.1, pointRadius: 0
        }]},
        options: {
            responsive: true, maintainAspectRatio: false,
            animation: { duration: 0 },
            scales: {
                x: { 
                    grid: { color: 'rgba(255,255,255,0.02)' }, 
                    ticks: { 
                        color: '#64748b', 
                        maxTicksLimit: 12, 
                        font: { family: 'JetBrains Mono', size: 9 },
                        autoSkip: true
                    } 
                },
                y: { 
                    grid: { color: 'rgba(255,255,255,0.02)' }, 
                    suggestedMin: 90,
                    suggestedMax: 110,
                    ticks: { 
                        color: '#64748b', 
                        font: { family: 'JetBrains Mono', size: 9 },
                        callback: (v) => '$' + v
                    } 
                }
            },
            plugins: { 
                legend: { display: false },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    backgroundColor: 'rgba(15, 23, 42, 0.9)',
                    titleFont: { family: 'JetBrains Mono' },
                    bodyFont: { family: 'JetBrains Mono' }
                }
            }
        }
    });
}
initCharts();

// ─── TOOLTIP LOGIC ───────────────────────────────────────────────────────────
const tooltip = document.getElementById('global-tooltip');
document.addEventListener('mouseover', (e) => {
    if (e.target.classList.contains('info-trigger')) {
        const info = e.target.getAttribute('data-info');
        tooltip.innerHTML = `<strong>EXPLAINER:</strong><br/>${info}`;
        tooltip.style.display = 'block';
        tooltip.style.left = `${e.pageX + 10}px`;
        tooltip.style.top = `${e.pageY + 10}px`;
    }
});
document.addEventListener('mouseout', (e) => {
    if (e.target.classList.contains('info-trigger')) tooltip.style.display = 'none';
});

// ─── CONTROL BAR LOGIC ───────────────────────────────────────────────────────
const ws = new WebSocket('ws://127.0.0.1:8000/ws/dashboard');

function sendCommand(cmd, value = null) {
    if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "control_command", command: cmd, value: value }));
    }
}

document.getElementById('ctrl-pause').onclick = () => {
    isPaused = true;
    document.getElementById('ctrl-pause').classList.add('active');
    document.getElementById('ctrl-play').classList.remove('active');
    sendCommand("pause");
};
document.getElementById('ctrl-play').onclick = () => {
    isPaused = false;
    document.getElementById('ctrl-play').classList.add('active');
    document.getElementById('ctrl-pause').classList.remove('active');
    sendCommand("play");
};
document.getElementById('spd-1x').onclick = () => {
    document.querySelectorAll('.btn').forEach(b => b.id.startsWith('spd') && b.classList.remove('active'));
    document.getElementById('spd-1x').classList.add('active');
    sendCommand("speed", 1.0);
};
document.getElementById('spd-10x').onclick = () => {
    document.querySelectorAll('.btn').forEach(b => b.id.startsWith('spd') && b.classList.remove('active'));
    document.getElementById('spd-10x').classList.add('active');
    sendCommand("speed", 0.05);
};
document.getElementById('spd-warp').onclick = () => {
    document.querySelectorAll('.btn').forEach(b => b.id.startsWith('spd') && b.classList.remove('active'));
    document.getElementById('spd-warp').classList.add('active');
    sendCommand("speed", 0.001);
};

// ─── SEQUENTIAL BOOTSTRAP ────────────────────────────────────────────────────
// 1. Portfolio History
fetch('http://127.0.0.1:8000/api/portfolio-history')
    .then(r => r.json())
    .then(data => {
        const snapshots = data.snapshots || [];
        if (snapshots.length > 0) {
            updateUIWithMetrics(snapshots[snapshots.length - 1]);
            let lastLabel = "";
            for (const snap of snapshots) {
                const ts = new Date(snap.timestamp);
                const monthYear = ts.toLocaleDateString('en-CA', { month: 'short', year: '2-digit' });
                const label = monthYear !== lastLabel ? monthYear : "";
                lastLabel = monthYear;
                portfolioChart.data.labels.push(label);
                portfolioChart.data.datasets[0].data.push(snap.net_liquidation);
            }
            portfolioChart.update();
        }
    });

// 2. Recent Trades
fetch('http://127.0.0.1:8000/api/recent-trades')
    .then(r => r.json())
    .then(data => {
        const trades = data.trades || [];
        if (trades.length > 0) {
            ledgerBody.innerHTML = '';
            trades.forEach(t => addTradeToLedger(t));
        }
    });

ws.onopen = () => addLog("Neural link established. Syncing flight data...", "system");

ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    
    if (msg.type === 'system_time_update') {
        currentSimDate = msg.data.date;
        systemClockEl.textContent = `⏱ MISSION DATE: ${currentSimDate}`;
    }
    else if (msg.type === 'portfolio_update') {
        updateUIWithMetrics({
            net_liquidation: msg.data.net_liquidation,
            available_funds: msg.data.available_funds,
            positions_json: JSON.stringify({
                metrics: msg.data.metrics,
                positions: Object.entries(msg.data.positions || {}).map(([k,v]) => ({ticker: k, ...v}))
            })
        });

        const ts = new Date(currentSimDate || new Date());
        const monthYear = ts.toLocaleDateString('en-CA', { month: 'short', year: '2-digit' });
        let label = "";
        const labels = portfolioChart.data.labels;
        const lastFullLabel = labels.filter(l => l !== "").pop();
        if (monthYear !== lastFullLabel) label = monthYear;

        portfolioChart.data.labels.push(label);
        portfolioChart.data.datasets[0].data.push(msg.data.net_liquidation);
        if (portfolioChart.data.labels.length > maxPoints) {
            portfolioChart.data.labels.shift();
            portfolioChart.data.datasets[0].data.shift();
        }
        portfolioChart.update();
    } 
    else if (msg.type === 'market_pulse') {
        for (const [ticker, metrics] of Object.entries(msg.data)) {
            marketPulseState.set(ticker, { ...marketPulseState.get(ticker), ...metrics });
            if (ticker === "TD.TO" || ticker === "SHOP.TO") {
                diagZ.textContent = metrics.z_score?.toFixed(2) || '--';
                diagRSI.textContent = metrics.rsi?.toFixed(0) || '--';
                diagVol.textContent = (metrics.volatility || 0.02).toFixed(3);
                diagSent.textContent = (metrics.sentiment || 0.5).toFixed(2);
            }
        }
        renderWatchlist();
    }
    else if (msg.type === 'agent_log') {
        addLog(`<strong>${msg.data.ticker} Analyst:</strong> ${msg.data.decision.rationale}`, "agent");
    }
    else if (msg.type === 'trade_alert') {
        addLog(`🚀 <strong>EXECUTION:</strong> ${msg.data.action} ${msg.data.shares.toFixed(2)} ${msg.data.ticker}`, msg.data.action.toLowerCase());
        addTradeToLedger({
            timestamp: currentSimDate || new Date().toISOString(),
            ticker: msg.data.ticker,
            action: msg.data.action,
            quantity: msg.data.shares,
            price: marketPulseState.get(msg.data.ticker)?.price || 0,
            rationale: "Execution confirmed."
        }, true);
    }
    else if (msg.type === 'learning_metrics') {
        const bar = document.getElementById('xp-progress');
        const count = document.getElementById('xp-counter');
        if (bar) {
            const pct = (msg.data.total_memories / msg.data.target_memories) * 100;
            bar.style.width = `${Math.min(pct, 100)}%`;
            count.textContent = `${msg.data.total_memories} / ${msg.data.target_memories} XP`;
        }
    }
};

function updateUIWithMetrics(snap) {
    try {
        const meta = JSON.parse(snap.positions_json);
        const m = meta.metrics || {};
        cagrEl.textContent = (m.cagr ?? '0.0') + '%';
        sharpeEl.textContent = (m.sharpe ?? '0.00');
        winrateEl.textContent = (m.win_rate ?? '0.0') + '%';
        ddEl.textContent = (m.drawdown ?? '0.0') + '%';
        const netLiq = snap.net_liquidation || 100;
        netLiqEl.textContent = formatMoney(netLiq);
        updateAllocationBar(meta.positions || [], snap.available_funds, netLiq);
        if (m.cagr > 15) {
            regimeStatusEl.textContent = "Market Regime: AGGRESSIVE BULL";
            regimeStatusEl.className = "regime-badge regime-bull";
        } else if (m.cagr < -5) {
            regimeStatusEl.textContent = "Market Regime: VOLATILE BEAR";
            regimeStatusEl.className = "regime-badge regime-bear";
        } else {
            regimeStatusEl.textContent = "Market Regime: NEUTRAL";
            regimeStatusEl.className = "regime-badge regime-sideways";
        }
    } catch(e) {}
}

function updateAllocationBar(positions, cash, total) {
    const bar = document.getElementById('allocation-bar');
    const labels = document.getElementById('allocation-labels');
    if (!bar || !labels) return;
    bar.innerHTML = ''; labels.innerHTML = '';
    const colors = ['#38bdf8', '#c084fc', '#fbbf24', '#f87171', '#34d399'];
    const cashPct = (cash / total) * 100;
    const cashSeg = document.createElement('div');
    cashSeg.className = 'alloc-segment';
    cashSeg.style.width = `${cashPct}%`;
    cashSeg.style.background = 'rgba(255,255,255,0.1)';
    bar.appendChild(cashSeg);
    labels.innerHTML += `<span>Cash: ${cashPct.toFixed(0)}%</span>`;
    positions.forEach((p, i) => {
        if (p.shares === 0) return;
        const tickerData = marketPulseState.get(p.ticker);
        const price = tickerData?.price || 0;
        const val = Math.abs(p.shares * price);
        const pct = (val / total) * 100;
        if (pct > 1) {
            const seg = document.createElement('div');
            seg.className = 'alloc-segment';
            seg.style.width = `${pct}%`;
            seg.style.background = colors[i % colors.length];
            bar.appendChild(seg);
            labels.innerHTML += `<span style="color:${colors[i % colors.length]}">${p.ticker}: ${pct.toFixed(0)}%</span>`;
        }
    });
}

function addTradeToLedger(t, prepend = false) {
    if (ledgerBody.innerHTML.includes('No trades executed')) ledgerBody.innerHTML = '';
    const tr = document.createElement('tr');
    const date = t.timestamp.includes('T') ? t.timestamp.split('T')[0] : t.timestamp;
    tr.innerHTML = `
        <td style="color:var(--text-muted);">${date}</td>
        <td><strong>${t.ticker}</strong></td>
        <td class="${t.action === 'BUY' ? 'trend-buy' : 'trend-sell'}">${t.action}</td>
        <td>${parseFloat(t.quantity).toFixed(2)}</td>
        <td>$${parseFloat(t.price).toFixed(2)}</td>
        <td style="font-size:0.65rem; color:var(--text-muted); max-width:150px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${t.rationale || '--'}</td>
    `;
    if (prepend) ledgerBody.prepend(tr); else ledgerBody.appendChild(tr);
    if (ledgerBody.children.length > 20) ledgerBody.removeChild(ledgerBody.lastChild);
}

function renderWatchlist() {
    watchlistBody.innerHTML = '';
    marketPulseState.forEach((m, ticker) => {
        const tr = document.createElement('tr');
        const shares = m.shares || 0;
        const pnl = shares * (m.price - (m.avg_cost || m.price));
        tr.innerHTML = `
            <td><strong>${ticker}</strong></td>
            <td>$${m.price?.toFixed(2) || '0.00'}</td>
            <td>${shares.toFixed(2)}</td>
            <td class="${pnl >= 0 ? 'trend-buy' : 'trend-sell'}">$${pnl.toFixed(2)}</td>
            <td><span style="color:#fbbf24; font-weight:bold;">${m.conviction || 0}</span></td>
            <td class="${m.status?.includes('BUY') ? 'trend-buy' : 'trend-sell'}">${m.status || '--'}</td>
        `;
        watchlistBody.appendChild(tr);
    });
}

function addLog(html, type="system") {
    totalLogs++;
    logCountEl.textContent = `${totalLogs} MSG`;
    const div = document.createElement('div');
    div.className = `log ${type}`;
    div.innerHTML = `<span style="color:var(--text-muted); font-size:0.7rem; font-family:JetBrains Mono">${new Date().toLocaleTimeString()}</span><br/>${html}`;
    feedContainer.prepend(div);
    if (feedContainer.children.length > 50) feedContainer.removeChild(feedContainer.lastChild);
}
