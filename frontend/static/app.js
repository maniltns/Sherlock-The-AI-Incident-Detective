// frontend/static/app.js
(() => {
  const sendBtn = document.getElementById('sendBtn');
  const sampleBtn = document.getElementById('sampleBtn');
  const queryEl = document.getElementById('query');
  const timeWindowEl = document.getElementById('timeWindow');
  const scenarioEl = document.getElementById('scenario');
  const resultSec = document.getElementById('result');
  const summaryDiv = document.getElementById('summary');
  const evidenceDiv = document.getElementById('evidence');
  const actionsDiv = document.getElementById('actions');
  const rawJsonPre = document.getElementById('rawJson');
  const backendUrlSpan = document.getElementById('backendUrl');

  // Backend base computed from page host: frontend served at <host>:3000; backend assumed at same host port 8000
  const BACKEND_BASE = `${window.location.protocol}//${window.location.hostname}:8000`;
  backendUrlSpan.textContent = `${BACKEND_BASE}/triage`;

  function setLoading(loading) {
    sendBtn.disabled = loading;
    sampleBtn.disabled = loading;
    sendBtn.textContent = loading ? 'Working…' : 'Send';
  }

  function renderResult(obj) {
    resultSec.classList.remove('hidden');
    // summary
    const conf = obj.confidence ?? 0;
    summaryDiv.innerHTML = `
      <h2>Hypothesis</h2>
      <p><strong>${escapeHtml(obj.hypothesis || 'No hypothesis')}</strong></p>
      <div class="confidence">
        Confidence: ${conf}%
        <progress value="${conf}" max="100"></progress>
      </div>
    `;

    // evidence
    const evmap = obj.evidence_map || {};
    let evidenceHtml = '<h3>Evidence</h3>';
    if (Object.keys(evmap).length === 0) {
      evidenceHtml += `<p class="small muted">No evidence included</p>`;
    } else {
      for (const [id, excerpt] of Object.entries(evmap)) {
        evidenceHtml += `<div class="evidence-item"><strong>${id}</strong><div class="small">${escapeHtml(excerpt)}</div></div>`;
      }
    }
    evidenceDiv.innerHTML = evidenceHtml;

    // suggested actions
    let actionsHtml = '<h3>Suggested actions</h3>';
    const actions = obj.suggested_actions || [];
    if (actions.length === 0) actionsHtml += `<p class="small muted">No actions suggested</p>`;
    else {
      actionsHtml += '<ul>';
      for (const a of actions) {
        actionsHtml += `<li><strong>${escapeHtml(a.action)}</strong> <span class="small muted"> (risk: ${escapeHtml(a.risk || 'unknown')})</span></li>`;
      }
      actionsHtml += '</ul>';
    }
    actionsDiv.innerHTML = actionsHtml;

    // raw JSON
    rawJsonPre.textContent = JSON.stringify(obj, null, 2);
    window.scrollTo({top:0, behavior:'smooth'});
  }

  function escapeHtml(s) {
    if (!s && s !== 0) return '';
    return String(s)
      .replaceAll('&','&')
      .replaceAll('<','<')
      .replaceAll('>','>')
      .replaceAll('"','"')
      .replaceAll("'",'&#39;');
  }

  async function callTriage(query, minutes) {
    setLoading(true);
    try {
      const url = `${BACKEND_BASE}/triage`;
      const res = await fetch(url, {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({query: query, time_window_minutes: Number(minutes)})
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

  async function callGenerateSample() {
    setLoading(true);
    try {
      const url = `${BACKEND_BASE}/generate_sample`;
      const res = await fetch(url, {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({scenario: scenarioEl.value, count:12})
      });
      if (!res.ok) throw new Error(`Generate sample failed: ${res.statusText}`);
      const out = await res.json();
      alert(`Generated ${out.generated} logs (scenario=${out.scenario}). Now run triage.`);
    } catch (err) {
      alert('Error: ' + err.message);
    } finally {
      setLoading(false);
    }
  }

  sendBtn.addEventListener('click', () => {
    const q = queryEl.value.trim();
    if (!q) { alert('Enter a query'); return; }
    callTriage(q, timeWindowEl.value || 30);
  });

  sampleBtn.addEventListener('click', () => {
    if (!confirm('Generate synthetic logs and a deploy stub for demo?')) return;
    callGenerateSample();
  });

  // initial sample hint
  queryEl.value = "connection pool exhausted api-prod-01 500 errors";
})();
