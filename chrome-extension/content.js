// Nexus Agent - Content Script: Injects sidebar into every page
(function() {
  let sidebarIframe = null;
  let sidebarVisible = false;

  // Listen for toggle messages
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.type === 'TOGGLE_SIDEBAR') {
      toggleSidebar();
    }
  });

  function toggleSidebar() {
    if (sidebarIframe && sidebarVisible) {
      sidebarIframe.style.transform = 'translateX(100%)';
      sidebarIframe.style.opacity = '0';
      setTimeout(() => {
        if (sidebarIframe) sidebarIframe.style.display = 'none';
      }, 300);
      sidebarVisible = false;
      // Restore page margin
      document.body.style.marginRight = '0';
    } else {
      if (!sidebarIframe) {
        createSidebar();
      }
      sidebarIframe.style.display = 'block';
      requestAnimationFrame(() => {
        sidebarIframe.style.transform = 'translateX(0)';
        sidebarIframe.style.opacity = '1';
      });
      sidebarVisible = true;
      // Shift page content
      document.body.style.marginRight = '400px';
    }
  }

  function createSidebar() {
    sidebarIframe = document.createElement('iframe');
    sidebarIframe.id = 'nexus-sidebar';
    sidebarIframe.src = chrome.runtime.getURL('sidebar.html');
    sidebarIframe.style.cssText = `
      position: fixed;
      top: 0;
      right: 0;
      width: 400px;
      height: 100vh;
      border: none;
      z-index: 2147483647;
      background: #0a0a0a;
      transform: translateX(100%);
      opacity: 0;
      transition: transform 0.3s ease, opacity 0.3s ease;
      box-shadow: -4px 0 20px rgba(0,0,0,0.5);
    `;
    document.body.appendChild(sidebarIframe);
  }

  // Listen for messages from sidebar iframe
  window.addEventListener('message', (event) => {
    if (event.data.type === 'NEXUS_CLOSE_SIDEBAR') {
      toggleSidebar();
    }
    if (event.data.type === 'NEXUS_GET_TAB_INFO') {
      // Sidebar iframe can't use chrome.tabs, so we proxy it here
      chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        const tab = tabs[0];
        sidebarIframe?.contentWindow?.postMessage({
          type: 'NEXUS_TAB_INFO',
          data: { url: tab?.url || '', title: tab?.title || '' }
        }, '*');
      });
    }
  });
})();
