/* JARVIS runtime adapter for the uploaded SVG HUD. Keep jarvis_hud.html artwork untouched. */
(() => {
  'use strict';
  if (window.__jarvisHudRuntimeAdapterLoaded) return;
  const artwork = document.getElementById('m');
  if (!artwork) {
    console.warn('JARVIS runtime adapter: SVG artwork #m was not found.');
    return;
  }
  window.__jarvisHudRuntimeAdapterLoaded = true;

  const byId = id => document.getElementById(id);
  const api = () => window.pywebview && window.pywebview.api;
  const put = (id, value, fallback = 'N/A') => {
    const node = byId(id);
    if (node) node.textContent = value == null || value === '' ? fallback : String(value);
  };
  const putAt = (x, y, value, fallback = 'N/A') => {
    const node = artwork.querySelector('text[x="' + x + '"][y="' + y + '"]');
    if (node) node.textContent = value == null || value === '' ? fallback : String(value);
  };
  const number = value => {
    const parsed = Number.parseFloat(value);
    return Number.isFinite(parsed) ? parsed : null;
  };

  const style = document.createElement('style');
  style.textContent = '\
    #m.jx-listening .core{animation:jx-listening-pulse 1.35s ease-in-out infinite}\
    #m.jx-thinking .core{animation:jx-thinking-pulse .7s ease-in-out infinite}\
    @keyframes jx-listening-pulse{0%,100%{transform:scale(1)}50%{transform:scale(1.12)}}\
    @keyframes jx-thinking-pulse{0%,100%{transform:scale(1)}50%{transform:scale(1.2)}}\
  ';
  document.head.appendChild(style);

  let dashboardBusy = false;
  let runtimeBusy = false;
  let refreshTimer = null;
  let readinessTimer = null;

  async function refreshDashboard() {
    const bridge = api();
    if (!bridge || typeof bridge.get_dashboard !== 'function' || dashboardBusy) return;
    dashboardBusy = true;
    try {
      const data = await bridge.get_dashboard();
      if (!data || typeof data !== 'object') return;

      put('v-cpu', data.cpu);
      put('v-ram', data.ram);
      put('v-gpu', data.gpu);
      put('v-os', data.os);
      put('v-arch', data.architecture);
      put('v-up', data.uptime);
      put('v-sr', '- RAM : ' + (data.memory || 'N/A'));
      putAt(942, 724, '- CPU : ' + (data.cpu || 'N/A'));
      putAt(942, 757, '- DISK : ' + (data.disk_percent || 'N/A'));
      put('v-wifi', 'Wi-Fi ' + (data.network || 'N/A'));

      putAt(929, 616, data.temperature);
      putAt(779, 724, '- ISP : ' + (data.isp || 'N/A'));
      putAt(779, 740, '- IP : ' + (data.ip || 'N/A'));
      putAt(124, 253, 'Full Capacity: ' + (data.disk_total || 'N/A'));
      putAt(124, 291, 'Free Capacity: ' + (data.disk_free || 'N/A'));
      putAt(117, 571, 'System: ' + (data.os || 'N/A') + ' · ' + (data.architecture || 'N/A'));

      const battery = byId('bat');
      if (battery) {
        battery.textContent = data.battery || 'N/A';
        battery.setAttribute('aria-label', 'Battery ' + (data.battery || 'unavailable'));
        battery.setAttribute('title', 'Battery ' + (data.battery || 'unavailable'));
      }

      const cpuNode = byId('v-cpu');
      if (cpuNode) cpuNode.setAttribute('title', 'CPU usage ' + (data.cpu || 'unavailable') + '; ' + (data.cpuName || 'processor name unavailable'));

      const storageFill = artwork.querySelector('rect[x="85"][y="316"][width="94"]');
      const diskPercent = number(data.disk_percent_value);
      if (storageFill && diskPercent !== null) {
        storageFill.setAttribute('width', String(185 * Math.max(0, Math.min(100, diskPercent)) / 100));
      }
      if (data.status) document.title = 'J.A.R.V.I.S. | ' + data.status;
    } catch (error) {
      console.warn('JARVIS dashboard bridge refresh failed', error);
    } finally {
      dashboardBusy = false;
    }
  }

  async function refreshRuntimeState() {
    const bridge = api();
    if (!bridge || typeof bridge.get_runtime_state !== 'function' || runtimeBusy) return;
    runtimeBusy = true;
    try {
      const state = await bridge.get_runtime_state();
      const listening = Boolean(state && state.listening);
      const thinking = Boolean(state && state.busy);
      artwork.classList.toggle('jx-listening', listening);
      artwork.classList.toggle('jx-thinking', thinking && !listening);
      artwork.setAttribute('aria-label', listening ? 'JARVIS listening' : thinking ? 'JARVIS processing' : 'JARVIS HUD');
    } catch (error) {
      console.warn('JARVIS runtime state refresh failed', error);
    } finally {
      runtimeBusy = false;
    }
  }

  function callBridge(name, ...args) {
    const bridge = api();
    if (!bridge || typeof bridge[name] !== 'function') {
      console.warn('JARVIS action unavailable until desktop bridge is ready:', name);
      return;
    }
    Promise.resolve(bridge[name](...args)).then(result => {
      if (result === false) console.warn('JARVIS action was not accepted:', name);
    }).catch(error => console.warn('JARVIS action failed:', name, error));
  }

  function svgPoint(event, svg) {
    try {
      const point = svg.createSVGPoint();
      point.x = event.clientX;
      point.y = event.clientY;
      const matrix = svg.getScreenCTM();
      if (!matrix) return null;
      const local = point.matrixTransform(matrix.inverse());
      return { x: local.x, y: local.y };
    } catch (_) {
      return null;
    }
  }

  function handleHudClick(event) {
    const svg = event.target && event.target.closest && event.target.closest('svg');
    if (!svg || !svg.matches('.scene, .row svg, .stack svg')) return;
    const point = svgPoint(event, svg);
    if (!point) return;
    const { x, y } = point;

    if (x >= 1440 && x <= 1510 && y >= 10 && y <= 80) {
      callBridge('close_window');
      return;
    }
    if (x >= 402 && x <= 455 && y >= 355 && y <= 415) {
      callBridge('open_settings');
      return;
    }
    if (x >= 620 && x <= 775 && y >= 710 && y <= 785) {
      if (y < 732) callBridge('open_system_tool', 'control_panel');
      else if (y < 749) callBridge('open_system_tool', 'device_manager');
      else if (y < 765) callBridge('open_system_tool', 'task_manager');
      else callBridge('open_system_tool', 'run');
      return;
    }
    if (x >= 105 && x <= 255 && y >= 600 && y <= 740) {
      if (y < 640) callBridge('open_folder', 'Documents');
      else if (y < 673) callBridge('open_folder', 'Pictures');
      else if (y < 706) callBridge('open_folder', 'Music');
      else callBridge('open_folder', 'Videos');
      return;
    }
    if (x >= 470 && x <= 585 && y >= 400 && y <= 575) {
      if (y < 460) callBridge('open_folder', 'This PC');
      else if (y < 520) callBridge('open_folder', 'Network');
      else callBridge('open_folder', 'Recycle Bin');
      return;
    }
    if (x >= 410 && x <= 565 && y >= 40 && y <= 325) {
      if (y < 120) callBridge('open_folder', 'Pictures');
      else if (y < 235) callBridge('open_folder', 'Downloads');
      else callBridge('open_folder', 'This PC');
    }
  }

  document.addEventListener('click', handleHudClick, true);
  document.addEventListener('keydown', event => {
    if (!event.ctrlKey || !event.shiftKey || event.altKey || event.metaKey) return;
    const key = event.key.toLowerCase();
    if (key === 'j') {
      event.preventDefault();
      callBridge('toggle_voice');
    } else if (key === 's') {
      event.preventDefault();
      callBridge('open_settings');
    } else if (key === 'k') {
      event.preventDefault();
      const command = window.prompt('Enter a command for JARVIS:');
      if (command && command.trim()) callBridge('send_command', command.trim());
    }
  });

  function startBridgeRefresh() {
    if (refreshTimer || !api()) return;
    if (readinessTimer) {
      clearInterval(readinessTimer);
      readinessTimer = null;
    }
    refreshDashboard();
    refreshRuntimeState();
    refreshTimer = window.setInterval(() => {
      refreshDashboard();
      refreshRuntimeState();
    }, 5000);
    window.setInterval(refreshRuntimeState, 1000);
  }

  window.addEventListener('pywebviewready', startBridgeRefresh);
  if (api()) startBridgeRefresh();
  else {
    let attempts = 0;
    readinessTimer = window.setInterval(() => {
      attempts += 1;
      if (api()) startBridgeRefresh();
      else if (attempts >= 120) {
        clearInterval(readinessTimer);
        readinessTimer = null;
        console.warn('JARVIS desktop bridge did not become ready within 30 seconds.');
      }
    }, 250);
  }
  window.addEventListener('beforeunload', () => {
    if (refreshTimer) clearInterval(refreshTimer);
    if (readinessTimer) clearInterval(readinessTimer);
  }, { once: true });
})();