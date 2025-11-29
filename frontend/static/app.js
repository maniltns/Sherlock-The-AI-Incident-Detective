(() => {
  const sendBtn = document.getElementById('sendBtn');
  const sampleBtn = document.getElementById('sampleBtn');
  const credsBtn = document.getElementById('credsBtn');
  const validateBtn = document.getElementById('validateBtn');
  const queryEl = document.getElementById('query');
  const timeWindowEl = document.getElementById('timeWindow');
  const scenarioEl = document.getElementById('scenario');
  const resultSec = document.getElementById('result');
  const summaryDiv = document.getElementById('summary');
  const evidenceDiv = document.getElementById('evidence');
  const actionsDiv = document.getElementById('actions');
  const metricsPanel = document.getElementById('metricsPanel');
  const rawJsonPre = document.getElementById('rawJson');
  const backendUrlSpan = document.getElementById('backendUrl');
  const topKEl = document.getElementById('topK');
  const srcLogs = document.getElementById('src_logs');
  const srcDeploys = document.getElementById('src_deploys');
  const srcMetrics = document.getElementById('src_metrics');
  const copyBtn = document.getElementById('copyJson');
  const downloadBtn = document.getElementById('downloadJson');
  const debugDiv = document.getElementById('debug');

  const BACKEND_BASE = `${window.location.protocol}//${window.location.hostname}:8000`;
  backendUrlSpan.textContent = `${BACKEND_BASE}/triage`;

  function setLoading(loading) {
    sendBtn.disabled = loading;
    sampleBtn.disabled = loading;
    credsBtn.disabled = loading;
    validateBtn.disabled = loading;
    sendBtn.textContent = loading ? 'Working…' : 'Send';
  }

  function escapeHtml(s) {
    if (s === null || s === undefined) return '';
    return String(s)
      .replaceAll('&','&amp;')
      .replaceAll('<','&lt;')
      .replaceAll('>','&gt;')
      .replaceAll('"','&quot;')
      .replaceAll("'",'&#39;');
  }

  function renderResult(obj) {
    resultSec.classList.remove('hidden');

    // Summary/hypothesis
    const conf = obj.confidence ?? 0;
    const impact = obj.impact || '';
    summaryDiv.innerHTML = `
      <h2>Hypothesis</h2>
      <p><strong>${escapeHtml(obj.hypothesis || 'No hypothesis')}</strong></p>
      <div class="confidence">Impact: ${escapeHtml(impact)}<br/>Confidence: ${conf}% <progress value="${conf}" max="100"></progress></div>
    `;

    // Metrics mini-panel (extract metric evidence ids)
    const evmap = obj.evidence_map || {};
    // detect metric entries
    const metricEntries = Object.entries(evmap).filter(([id, txt]) => id.startsWith('metric#'));
    let metricsHtml = '<h3>Metrics Snapshot</h3>';
    if (metricEntries.length === 0) {
      metricsHtml += `<p class="small muted">No metrics in evidence</p>`;
    } else {
      metricsHtml += '<div class="metrics-grid">';
      metricEntries.slice(0,6).forEach(([id, txt]) => {
        metricsHtml += `<div class="metric-card"><strong>${escapeHtml(id)}</strong><div class="small">${escapeHtml(txt)}</div></div>`;
      });
      metricsHtml += '</div>';
    }
    metricsPanel.innerHTML = metricsHtml;

    // Evidence timeline
    let evHtml = '<h3>Evidence</h3>';
    if (Object.keys(evmap).length === 0) {
      evHtml += `<p class="small muted">No evidence included</p>`;
    } else {
      evHtml += '<div class="timeline">';
      Object.entries(evmap).forEach(([id, excerpt]) => {
        let badge = 'log';
        if (id.startsWith('git#')) badge = 'deploy';
        if (id.startsWith('metric#')) badge = 'metric';
        evHtml += `<div class="entry"><div class="entry-head"><span class="badge ${badge}">${escapeHtml(badge)}</span><strong>${escapeHtml(id)}</strong></div><div class="entry-body small">${escapeHtml(excerpt)}</div></div>`;
      });
      evHtml += '</div>';
    }
    evidenceDiv.innerHTML = evHtml;

    // Suggested actions
    let actionsHtml = '<h3>Suggested actions</h3>';
    const actions = obj.suggested_actions || [];
    if (actions.length === 0) actionsHtml += `<p class="small muted">No actions suggested</p>`;
    else {
      actionsHtml += '<ol>';
      actions.forEach(a => {
        const rclass = a.risk === 'high' ? 'risk-high' : a.risk === 'medium' ? 'risk-med' : 'risk-low';
        actionsHtml += `<li><strong>${escapeHtml(a.action)}</strong> <span class="small muted">(${escapeHtml(a.type || '')}, risk: <span class="${rclass}">${escapeHtml(a.risk || '')}</span>${a.eta_minutes ? ', ETA: '+a.eta_minutes+'m' : ''})</span>`;
        if (a.rollback_plan) actionsHtml += `<div class="small">Rollback plan: ${escapeHtml(a.rollback_plan)}</div>`;
        actionsHtml += '</li>';
      });
      actionsHtml += '</ol>';
    }
    actionsDiv.innerHTML = actionsHtml;

    rawJsonPre.textContent = JSON.stringify(obj, null, 2);
    window.scrollTo({top:0, behavior:'smooth'});
  }

  async function callTriage(query, minutes, topK, sources) {
    setLoading(true);
    try {
      const url = `${BACKEND_BASE}/triage`;
      // include sources as suggestion (backend currently defaults to all if not present)
      const res = await fetch(url, {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({query: query, time_window_minutes: Number(minutes), max_evidence: Number(topK), sources: sources})
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(`Backend error ${res.status}: ${text}`);
      }
      const data = await res.json();
      renderResult(data);
    } catch (err) {
      alert('Error: ' + err.message);
    } finally {
      setLoading(false);
    }
  }

  async function callGenerateSample(scenario) {
    setLoading(true);
    try {
      const url = `${BACKEND_BASE}/generate_sample`;
      const res = await fetch(url, {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({scenario: scenario, count:12})
      });
      if (!res.ok) throw new Error(`Generate sample failed: ${res.statusText}`);
      const out = await res.json();
      alert(`Generated ${out.generated} logs, metrics and a deploy stub (scenario=${out.scenario}). Run triage now.`);
    } catch (err) {
      alert('Error: ' + err.message);
    } finally {
      setLoading(false);
    }
  }

  async function showCredentials() {
    setLoading(true);
    try {
      const url = `${BACKEND_BASE}/debug/credentials`;
      const res = await fetch(url);
      const data = await res.json();
      debugDiv.classList.remove('hidden');
      debugDiv.textContent = JSON.stringify(data, null, 2);
    } catch (err) {
      debugDiv.classList.remove('hidden');
      debugDiv.textContent = `Error fetching credentials: ${err.message}`;
    } finally {
      setLoading(false);
    }
  }

  async function validateCredentials() {
    setLoading(true);
    try {
      const url = `${BACKEND_BASE}/debug/validate_credentials`;
      const res = await fetch(url);
      const data = await res.json();
      debugDiv.classList.remove('hidden');
      debugDiv.textContent = JSON.stringify(data, null, 2);
    } catch (err) {
      debugDiv.classList.remove('hidden');
      debugDiv.textContent = `Error validating credentials: ${err.message}`;
    } finally {
      setLoading(false);
    }
  }

  sendBtn.addEventListener('click', () => {
    const q = queryEl.value.trim();
    if (!q) { alert('Enter a query'); return; }
    const sources = [];
    if (srcLogs.checked) sources.push('logs');
    if (srcDeploys.checked) sources.push('deploys');
    if (srcMetrics.checked) sources.push('metrics');
    callTriage(q, timeWindowEl.value || 30, topKEl.value || 6, sources);
  });

  sampleBtn.addEventListener('click', () => {
    if (!confirm('Generate synthetic logs, metrics and a deploy stub for demo?')) return;
    callGenerateSample(scenarioEl.value);
  });

  credsBtn.addEventListener('click', () => { showCredentials(); });
  validateBtn.addEventListener('click', () => { validateCredentials(); });

  copyBtn.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(rawJsonPre.textContent || '');
      alert('JSON copied to clipboard');
    } catch (e) {
      alert('Copy failed: ' + e.message);
    }
  });

  downloadBtn.addEventListener('click', () => {
    const data = rawJsonPre.textContent || '{}';
    const blob = new Blob([data], {type: 'application/json'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'sherlock-triage.json';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  });

  queryEl.value = "connection pool exhausted api-prod-01 500 errors";
  backendUrlSpan.textContent = `${BACKEND_BASE}/triage`;
})();
