// Nexus Popup - Settings and quick actions
document.addEventListener('DOMContentLoaded', async () => {
  const backendUrlInput = document.getElementById('backend-url');
  const backendStatus = document.getElementById('backend-status');
  const backendText = document.getElementById('backend-text');
  const btnToggle = document.getElementById('btn-toggle');
  const btnDashboard = document.getElementById('btn-dashboard');
  const btnClear = document.getElementById('btn-clear');

  // Load saved settings
  const settings = await chrome.storage.local.get(['backendUrl']);
  if (settings.backendUrl) {
    backendUrlInput.value = settings.backendUrl;
  }

  // Check backend status
  await checkBackend();

  // Save backend URL on change
  backendUrlInput.addEventListener('change', async () => {
    await chrome.storage.local.set({ backendUrl: backendUrlInput.value });
    await checkBackend();
  });

  // Toggle sidebar
  btnToggle.addEventListener('click', async () => {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    chrome.tabs.sendMessage(tab.id, { type: 'TOGGLE_SIDEBAR' });
    window.close();
  });

  // Open dashboard
  btnDashboard.addEventListener('click', async () => {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    chrome.tabs.sendMessage(tab.id, { type: 'OPEN_DASHBOARD' });
    window.close();
  });

  // Clear chat history
  btnClear.addEventListener('click', async () => {
    await chrome.storage.local.remove(['chatHistory']);
    backendText.textContent = 'Chat history cleared!';
    setTimeout(() => checkBackend(), 2000);
  });

  async function checkBackend() {
    const url = backendUrlInput.value || 'http://localhost:8001';
    try {
      const response = await fetch(`${url}/`);
      if (response.ok) {
        backendStatus.className = 'status-dot online';
        backendText.textContent = 'Backend connected';
      } else {
        throw new Error('Not OK');
      }
    } catch {
      backendStatus.className = 'status-dot offline';
      backendText.textContent = 'Backend offline';
    }
  }
});
