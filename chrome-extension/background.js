// Nexus Agent - Background Service Worker
const BACKEND_URL = 'http://localhost:8001';

// Handle extension icon click
chrome.action.onClicked.addListener(async (tab) => {
  chrome.tabs.sendMessage(tab.id, { type: 'TOGGLE_SIDEBAR' });
});

// Handle keyboard shortcut
chrome.commands.onCommand.addListener(async (command, tab) => {
  if (command === 'toggle-sidebar') {
    chrome.tabs.sendMessage(tab.id, { type: 'TOGGLE_SIDEBAR' });
  }
});

// Handle messages from content script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type === 'AGENT_TASK') {
    handleAgentTask(request.data, sendResponse);
    return true; // Keep channel open for async
  }
  if (request.type === 'VISION_ANALYZE') {
    handleVision(request.data, sendResponse);
    return true;
  }
  if (request.type === 'GET_DASHBOARD') {
    fetchDashboard(sendResponse);
    return true;
  }
  if (request.type === 'GET_EXECUTION') {
    fetchExecution(request.executionId, sendResponse);
    return true;
  }
  if (request.type === 'GET_SAFETY') {
    fetchSafety(sendResponse);
    return true;
  }
});

async function handleAgentTask(data, sendResponse) {
  try {
    const response = await fetch(`${BACKEND_URL}/api/agent`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        task: data.task,
        image: data.image,
        current_url: data.currentUrl,
        user_id: data.userId
      })
    });
    const result = await response.json();
    sendResponse({ success: true, data: result });
  } catch (err) {
    sendResponse({ success: false, error: err.message });
  }
}

async function handleVision(data, sendResponse) {
  try {
    const response = await fetch(`${BACKEND_URL}/api/vision`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        image: data.image,
        prompt: data.prompt
      })
    });
    const result = await response.json();
    sendResponse({ success: true, data: result });
  } catch (err) {
    sendResponse({ success: false, error: err.message });
  }
}

async function fetchDashboard(sendResponse) {
  try {
    const response = await fetch(`${BACKEND_URL}/api/dashboard`);
    const result = await response.json();
    sendResponse({ success: true, data: result });
  } catch (err) {
    sendResponse({ success: false, error: err.message });
  }
}

async function fetchExecution(executionId, sendResponse) {
  try {
    const response = await fetch(`${BACKEND_URL}/api/execution/${executionId}`);
    const result = await response.json();
    sendResponse({ success: true, data: result });
  } catch (err) {
    sendResponse({ success: false, error: err.message });
  }
}

async function fetchSafety(sendResponse) {
  try {
    const response = await fetch(`${BACKEND_URL}/api/safety/events`);
    const result = await response.json();
    sendResponse({ success: true, data: result });
  } catch (err) {
    sendResponse({ success: false, error: err.message });
  }
}
