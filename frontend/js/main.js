// --- State Management ---
const state = {
    token: localStorage.getItem('token'),
    username: localStorage.getItem('username'),
    ws: null,
    currentSection: 'overview',
    guilds: [],
    selectedGuildId: null,
    logs: [],
    stats: {
        servers: 0,
        messages: 0,
        uptime: '00:00:00'
    }
};

// --- Initialization ---
document.addEventListener('DOMContentLoaded', () => {
    if (!state.token) {
        window.location.href = 'login.html';
        return;
    }

    initNavigation();
    initWebSocket();
    fetchInitialData();
    initTerminal();
});

// --- Navigation ---
function initNavigation() {
    const navLinks = document.querySelectorAll('.nav-links li[data-section]');
    navLinks.forEach(link => {
        link.addEventListener('click', () => {
            const section = link.getAttribute('data-section');
            switchSection(section);
        });
    });

    document.getElementById('logout-btn').addEventListener('click', () => {
        localStorage.clear();
        window.location.href = 'login.html';
    });

    // Modal Close
    document.querySelector('.close').onclick = () => {
        document.getElementById('server-control-panel').style.display = 'none';
    };
}

function switchSection(sectionId) {
    state.currentSection = sectionId;
    
    // Update UI
    document.querySelectorAll('.dashboard-section').forEach(s => s.classList.remove('active'));
    document.getElementById(sectionId).classList.add('active');
    
    document.querySelectorAll('.nav-links li').forEach(l => l.classList.remove('active'));
    document.querySelector(`.nav-links li[data-section="${sectionId}"]`).classList.add('active');
    
    document.getElementById('section-title').innerText = sectionId.charAt(0).toUpperCase() + sectionId.slice(1);
    
    if (sectionId === 'servers') renderServers();
    if (sectionId === 'analytics') renderCharts();
}

// --- WebSocket ---
function initWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    
    state.ws = new WebSocket(wsUrl);

    state.ws.onopen = () => {
        document.getElementById('ws-status').className = 'status online';
        document.getElementById('ws-status').innerText = 'WS: Connected';
        console.log('WS Connected');
    };

    state.ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        handleWsMessage(msg);
    };

    state.ws.onclose = () => {
        document.getElementById('ws-status').className = 'status offline';
        document.getElementById('ws-status').innerText = 'WS: Disconnected';
        setTimeout(initWebSocket, 5000); // Reconnect
    };
}

function handleWsMessage(msg) {
    switch (msg.type) {
        case 'bot_log':
            appendLog(msg.data);
            break;
        case 'bot_status':
            updateBotStatus(msg.status);
            break;
        case 'terminal_output':
            appendTerminal(msg.data);
            break;
        case 'stats_update':
            updateStats(msg.data);
            break;
    }
}

// --- Data Fetching ---
async function fetchInitialData() {
    try {
        const [guildsRes, statsRes] = await Promise.all([
            fetch('/api/guilds'),
            fetch('/api/stats/global')
        ]);
        
        state.guilds = await guildsRes.json();
        const globalStats = await statsRes.json();
        
        updateStats({
            servers: state.guilds.length,
            messages: globalStats.total_messages
        });
        
        if (state.currentSection === 'servers') renderServers();
    } catch (err) {
        console.error('Error fetching data:', err);
    }
}

// --- UI Rendering ---
function updateStats(data) {
    if (data.servers !== undefined) document.getElementById('stat-servers').innerText = data.servers;
    if (data.messages !== undefined) document.getElementById('stat-messages').innerText = data.messages;
    if (data.uptime !== undefined) document.getElementById('stat-uptime').innerText = data.uptime;
}

function updateBotStatus(status) {
    const el = document.getElementById('bot-status');
    el.className = `status ${status.toLowerCase()}`;
    el.innerText = `Bot: ${status}`;
}

function appendLog(log) {
    const container = document.getElementById('log-stream');
    const div = document.createElement('div');
    div.className = 'log-entry';
    const time = new Date().toLocaleTimeString();
    div.innerHTML = `<span class="log-time">[${time}]</span> <span class="log-info">${log}</span>`;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    
    // Limit log entries
    if (container.children.length > 100) container.removeChild(container.firstChild);
}

function renderServers() {
    const grid = document.getElementById('server-grid');
    grid.innerHTML = '';
    
    state.guilds.forEach(guild => {
        const card = document.createElement('div');
        card.className = 'server-card';
        card.innerHTML = `
            <h3>${guild.name}</h3>
            <p>ID: ${guild.guild_id}</p>
            <p>Members: ${guild.member_count}</p>
        `;
        card.onclick = () => openServerControl(guild);
        grid.appendChild(card);
    });
}

async function openServerControl(guild) {
    state.selectedGuildId = guild.guild_id;
    document.getElementById('current-server-name').innerText = guild.name;
    document.getElementById('server-control-panel').style.display = 'block';
    
    // Fetch cogs for this server
    try {
        const res = await fetch(`/api/guilds/${guild.guild_id}/cogs`);
        const cogs = await res.json();
        renderCogs(cogs);
    } catch (err) {
        console.error('Error fetching cogs:', err);
    }
}

function renderCogs(cogs) {
    const list = document.getElementById('cog-list');
    list.innerHTML = '';
    
    Object.entries(cogs).forEach(([name, enabled]) => {
        const item = document.createElement('div');
        item.className = 'cog-item';
        item.innerHTML = `
            <span>${name}</span>
            <input type="checkbox" ${enabled ? 'checked' : ''} onchange="toggleCog('${name}', this.checked)">
        `;
        list.appendChild(item);
    });
}

async function toggleCog(cogName, enabled) {
    try {
        await fetch('/api/guilds/cogs/toggle', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                guild_id: state.selectedGuildId,
                cog_name: cogName,
                enabled: enabled
            })
        });
    } catch (err) {
        console.error('Error toggling cog:', err);
    }
}

// --- Terminal ---
function initTerminal() {
    const input = document.getElementById('terminal-input');
    input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            const cmd = input.value;
            if (cmd.trim()) {
                state.ws.send(JSON.stringify({
                    type: 'terminal_command',
                    data: cmd
                }));
                appendTerminal(`> ${cmd}`, 'input');
                input.value = '';
            }
        }
    });
}

function appendTerminal(text, type = 'output') {
    const box = document.getElementById('terminal-output');
    const div = document.createElement('div');
    div.className = type === 'input' ? 'term-input' : 'term-output';
    div.innerText = text;
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
}

// --- Charts ---
function renderCharts() {
    const ctx = document.getElementById('activityChart').getContext('2d');
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
            datasets: [{
                label: 'Messages',
                data: [12, 19, 3, 5, 2, 3, 7],
                borderColor: '#00ff41',
                tension: 0.1
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: { beginAtZero: true, grid: { color: '#333' } },
                x: { grid: { color: '#333' } }
            }
        }
    });
}
