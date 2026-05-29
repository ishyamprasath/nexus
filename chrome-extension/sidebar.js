// Nexus Sidebar - Main UI Controller
// NOTE: This runs inside an iframe (web-accessible resource), so chrome.* APIs are NOT available.
// All extension API calls go through postMessage to the content script.
(function() {
  const BACKEND_URL = 'http://localhost:8001';

  // DOM Elements
  const messagesEl = document.getElementById('messages');
  const taskInput = document.getElementById('task-input');
  const btnSend = document.getElementById('btn-send');
  const btnClose = document.getElementById('btn-close');
  const btnDashboard = document.getElementById('btn-dashboard');
  const btnImage = document.getElementById('btn-image');
  const btnGraph = document.getElementById('btn-graph');
  const btnThinking = document.getElementById('btn-thinking');
  const imageUpload = document.getElementById('image-upload');
  const statusIndicator = document.getElementById('status-indicator');
  const connectionStatus = document.getElementById('connection-status');
  const dashboardPanel = document.getElementById('dashboard-panel');
  const graphPanel = document.getElementById('graph-panel');
  const thinkingPanel = document.getElementById('thinking-panel');
  const chatSection = document.getElementById('chat-section');

  // State
  let currentImage = null;
  let activeExecutionId = null;
  let wsConnection = null;
  let isConnected = false;

  // Initialize
  document.addEventListener('DOMContentLoaded', () => {
    checkConnection();
    setInterval(checkConnection, 10000);
  });

  // Listen for messages from content script (chrome API proxy)
  window.addEventListener('message', (event) => {
    if (event.data.type === 'NEXUS_TAB_INFO') {
      // Tab info received from content script - stored for use by getCurrentTabUrl
    }
  });

  // Event Listeners
  btnSend.addEventListener('click', sendTask);
  taskInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendTask();
    }
  });

  btnClose.addEventListener('click', () => {
    window.parent.postMessage({ type: 'NEXUS_CLOSE_SIDEBAR' }, '*');
  });

  btnDashboard.addEventListener('click', toggleDashboard);
  btnGraph.addEventListener('click', toggleGraph);
  btnThinking.addEventListener('click', toggleThinking);

  btnImage.addEventListener('click', () => imageUpload.click());
  imageUpload.addEventListener('change', handleImageUpload);

  // Functions
  async function checkConnection() {
    try {
      const response = await fetch(`${BACKEND_URL}/`, { method: 'GET' });
      if (response.ok) {
        isConnected = true;
        connectionStatus.textContent = 'Connected';
        connectionStatus.classList.add('connected');
      }
    } catch {
      isConnected = false;
      connectionStatus.textContent = 'Disconnected';
      connectionStatus.classList.remove('connected');
    }
  }

  function setStatus(status, text) {
    const dot = statusIndicator.querySelector('.status-dot');
    const textEl = statusIndicator.querySelector('.status-text');
    dot.className = `status-dot ${status}`;
    textEl.textContent = text;
  }

  async function sendTask() {
    const task = taskInput.value.trim();
    if (!task && !currentImage) return;

    // Add user message
    addMessage('user', task, currentImage);
    taskInput.value = '';

    // Clear image
    const preview = document.querySelector('.image-preview');
    if (preview) preview.remove();
    currentImage = null;

    setStatus('thinking', 'Planning...');

    try {
      // Get current tab URL via content script (iframe can't use chrome.tabs)
      const currentUrl = await new Promise((resolve) => {
        window.parent.postMessage({ type: 'NEXUS_GET_TAB_INFO' }, '*');
        const handler = (event) => {
          if (event.data.type === 'NEXUS_TAB_INFO') {
            window.removeEventListener('message', handler);
            resolve(event.data.data?.url || '');
          }
        };
        window.addEventListener('message', handler);
        setTimeout(() => { window.removeEventListener('message', handler); resolve(''); }, 2000);
      });

      const response = await fetch(`${BACKEND_URL}/api/agent`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          task: task,
          image: currentImage,
          current_url: currentUrl
        })
      });

      const result = await response.json();
      activeExecutionId = result.execution_id;

      addMessage('system', `Agent started (ID: ${result.execution_id}). Processing...`);
      setStatus('active', 'Executing...');

      // Poll for completion
      pollExecution(result.execution_id);

    } catch (err) {
      addMessage('system', `Error: ${err.message}`);
      setStatus('error', 'Error');
    }
  }

  async function pollExecution(execId) {
    let attempts = 0;
    const maxAttempts = 60; // 5 minutes max
    const interval = setInterval(async () => {
      attempts++;
      try {
        const resp = await fetch(`${BACKEND_URL}/api/execution/${execId}`);
        if (resp.ok) {
          const data = await resp.json();
          if (data.status === 'completed') {
            clearInterval(interval);
            addMessage('assistant', data.final_result || 'Task completed');
            setStatus('idle', 'Ready');
          } else if (data.status === 'failed') {
            clearInterval(interval);
            addMessage('system', `Task failed: ${data.error || 'Unknown error'}`);
            setStatus('error', 'Failed');
          }
        }
      } catch {
        // Ignore poll errors
      }
      if (attempts >= maxAttempts) {
        clearInterval(interval);
        addMessage('system', 'Task timed out');
        setStatus('error', 'Timeout');
      }
    }, 5000);
  }

  function connectWebSocket(executionId) {
    if (wsConnection) {
      wsConnection.close();
    }

    const wsUrl = `ws://localhost:8001/api/ws/agent/${executionId}`;
    wsConnection = new WebSocket(wsUrl);

    wsConnection.onopen = () => {
      console.log('[Nexus] WebSocket connected');
    };

    wsConnection.onmessage = (event) => {
      const data = JSON.parse(event.data);
      handleWebSocketMessage(data);
    };

    wsConnection.onclose = () => {
      console.log('[Nexus] WebSocket disconnected');
    };
  }

  function handleWebSocketMessage(data) {
    if (data.type === 'execution_state') {
      // Update thinking traces
      if (data.sub_tasks) {
        updateThinkingPanel(data.sub_tasks);
      }
      // Update status
      if (data.status === 'in_progress') {
        setStatus('active', 'Executing...');
      } else if (data.status === 'completed') {
        setStatus('idle', 'Ready');
      }
    }
  }

  function addMessage(role, text, image = null) {
    const msg = document.createElement('div');
    msg.className = `message ${role}`;

    const header = document.createElement('div');
    header.className = 'message-header';
    const roleLabel = role === 'user' ? 'You' : role === 'assistant' ? 'Nexus' : 'System';
    const icon = role === 'user' ? '&#128100;' : role === 'assistant' ? '&#129302;' : '&#9888;';
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    header.innerHTML = `${icon} ${roleLabel} <span class="message-timestamp">${time}</span>`;
    msg.appendChild(header);

    const content = document.createElement('div');
    content.textContent = text;
    msg.appendChild(content);

    if (image) {
      const preview = document.createElement('div');
      preview.className = 'image-preview';
      const img = document.createElement('img');
      img.src = image;
      preview.appendChild(img);
      msg.appendChild(preview);
    }

    messagesEl.appendChild(msg);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function addTaskCard(task) {
    const card = document.createElement('div');
    card.className = 'task-card';
    card.id = `task-${task.id}`;

    const header = document.createElement('div');
    header.className = 'task-card-header';

    const role = document.createElement('span');
    role.className = 'task-role';
    role.textContent = task.agent_role;

    const status = document.createElement('span');
    status.className = `task-status ${task.status}`;
    status.textContent = task.status;

    header.appendChild(role);
    header.appendChild(status);

    const desc = document.createElement('div');
    desc.textContent = task.description;
    desc.style.fontSize = '11px';
    desc.style.color = '#888';

    card.appendChild(header);
    card.appendChild(desc);
    messagesEl.appendChild(card);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function handleImageUpload(e) {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      currentImage = event.target.result;

      // Show preview
      const preview = document.createElement('div');
      preview.className = 'image-preview';
      const img = document.createElement('img');
      img.src = currentImage;
      preview.appendChild(img);
      taskInput.parentElement.insertBefore(preview, taskInput);
    };
    reader.readAsDataURL(file);
  }

  // Panel Toggles
  function hideAllPanels() {
    dashboardPanel.classList.add('hidden');
    graphPanel.classList.add('hidden');
    thinkingPanel.classList.add('hidden');
    chatSection.classList.add('hidden');
    document.querySelectorAll('.toolbar-btn').forEach(b => b.classList.remove('active'));
  }

  function toggleDashboard() {
    if (!dashboardPanel.classList.contains('hidden')) {
      hideAllPanels();
      chatSection.classList.remove('hidden');
      return;
    }
    hideAllPanels();
    dashboardPanel.classList.remove('hidden');
    btnDashboard.classList.add('active');
    loadDashboard();
  }

  function toggleGraph() {
    if (!graphPanel.classList.contains('hidden')) {
      hideAllPanels();
      chatSection.classList.remove('hidden');
      return;
    }
    hideAllPanels();
    graphPanel.classList.remove('hidden');
    btnGraph.classList.add('active');
    if (activeExecutionId) {
      loadGraph(activeExecutionId);
    }
  }

  function toggleThinking() {
    if (!thinkingPanel.classList.contains('hidden')) {
      hideAllPanels();
      chatSection.classList.remove('hidden');
      return;
    }
    hideAllPanels();
    thinkingPanel.classList.remove('hidden');
    btnThinking.classList.add('active');
  }

  async function loadDashboard() {
    try {
      const response = await fetch(`${BACKEND_URL}/api/dashboard`);
      const data = await response.json();

      // Stats
      const statsGrid = document.getElementById('stats-grid');
      statsGrid.innerHTML = `
        <div class="stat-card"><div class="stat-value">${data.total_executions || 0}</div><div class="stat-label">Total</div></div>
        <div class="stat-card"><div class="stat-value">${data.active_executions || 0}</div><div class="stat-label">Active</div></div>
        <div class="stat-card"><div class="stat-value">${data.completed_executions || 0}</div><div class="stat-label">Completed</div></div>
        <div class="stat-card"><div class="stat-value">${data.blocked_actions || 0}</div><div class="stat-label">Blocked</div></div>
      `;

      // Safety events
      const safetyEvents = document.getElementById('safety-events');
      if (data.recent_events) {
        safetyEvents.innerHTML = data.recent_events.slice(0, 10).map(e => `
          <div class="safety-event ${e.allowed ? 'allowed' : 'blocked'}">
            <strong>${e.tool}</strong> - ${e.allowed ? 'Allowed' : 'Blocked'}<br>
            <span style="opacity:0.6">${e.reason}</span>
          </div>
        `).join('');
      }

      // Active executions
      const activeExecs = document.getElementById('active-executions');
      if (data.active_executions_detail && data.active_executions_detail.length > 0) {
        activeExecs.innerHTML = data.active_executions_detail.map(e => `
          <div class="task-card">
            <div class="task-card-header">
              <span class="task-role">${e.task.substring(0, 30)}</span>
              <span class="task-status ${e.status}">${e.status}</span>
            </div>
            <div style="font-size:10px;color:#666;margin-top:4px;">
              Current: ${e.current_task || 'None'} | Next: ${e.next_task || 'None'}
            </div>
          </div>
        `).join('');
      } else {
        activeExecs.innerHTML = '<div style="opacity:0.5;font-size:11px;text-align:center;">No active executions</div>';
      }
    } catch (err) {
      console.error('Dashboard load error:', err);
    }
  }

  async function loadGraph(executionId) {
    try {
      const response = await fetch(`${BACKEND_URL}/api/execution/${executionId}/graph`);
      const data = await response.json();

      // Simple canvas-based graph rendering
      const canvas = document.getElementById('graph-canvas-el');
      const ctx = canvas.getContext('2d');
      canvas.width = canvas.parentElement.clientWidth;
      canvas.height = 300;

      ctx.fillStyle = '#0a0a0a';
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      if (data.nodes && data.nodes.length > 0) {
        // Draw nodes
        const centerX = canvas.width / 2;
        const centerY = canvas.height / 2;

        data.nodes.forEach((node, i) => {
          const angle = (i / data.nodes.length) * Math.PI * 2;
          const radius = 80;
          const x = centerX + Math.cos(angle) * radius;
          const y = centerY + Math.sin(angle) * radius;

          // Node circle
          ctx.beginPath();
          ctx.arc(x, y, 20, 0, Math.PI * 2);
          ctx.fillStyle = node.type === 'execution' ? 'rgba(0,212,255,0.3)' :
                           node.type === 'agent' ? 'rgba(123,47,247,0.3)' :
                           'rgba(255,255,255,0.1)';
          ctx.fill();
          ctx.strokeStyle = node.type === 'execution' ? '#00d4ff' :
                            node.type === 'agent' ? '#7b2ff7' : '#666';
          ctx.lineWidth = 1;
          ctx.stroke();

          // Label
          ctx.fillStyle = '#e0e0e0';
          ctx.font = '10px sans-serif';
          ctx.textAlign = 'center';
          ctx.fillText(node.label, x, y + 35);
        });

        // Draw edges
        if (data.edges) {
          data.edges.forEach(edge => {
            // Simple line between nodes (would need proper positioning)
          });
        }
      }

      // Task queue
      const taskQueue = document.getElementById('task-queue');
      taskQueue.innerHTML = '<div style="opacity:0.5;font-size:11px;">Graph visualization active</div>';
    } catch (err) {
      console.error('Graph load error:', err);
    }
  }

  function updateThinkingPanel(subTasks) {
    const thinkingList = document.getElementById('thinking-list');
    thinkingList.innerHTML = '';

    subTasks.forEach(task => {
      if (task.thinking_trace && task.thinking_trace.length > 0) {
        task.thinking_trace.forEach(step => {
          const stepEl = document.createElement('div');
          stepEl.className = 'thinking-step';
          stepEl.innerHTML = `
            <div class="thinking-step-header">
              <div class="thinking-step-number">${step.step}</div>
              <span>${task.agent_role || 'Agent'}</span>
            </div>
            <div>${step.thought}</div>
          `;
          thinkingList.appendChild(stepEl);
        });
      }
    });
  }
})();
