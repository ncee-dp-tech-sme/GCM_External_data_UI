/**
 * Scanner module for GCM Web UI
 * Handles target generation, SSL certificate scanning, and certificate import from CSV
 *
 * Created: 2026-06-02
 * Last Modified: 2026-06-02 - Initial implementation
 * Last Modified: 2026-07-25 - Added Step 2 scan functionality (run-scan endpoint)
 * Last Modified: 2026-07-25 - Show generated-targets banner on Step 2; file upload is now optional override
 * Last Modified: 2026-07-25 - SSE streaming scan with real-time progress bar, stop button, and enriched
 *                              results table (service type, TLS version, cipher, SSH host-key info)
 * Last Modified: 2026-07-25 - Added findings badges in results table (EXPIRED, LEGACY_TLS, WEAK_CIPHER,
 *                              WEAK_KEY, SELF_SIGNED, SHA1_SIGNATURE, WEAK_SSH_HOSTKEY)
 * Last Modified: 2026-07-25 - SSH column always renders when service=ssh (even without key type); algorithm
 *                              list shown cleanly; progress panel made more prominent
 * Last Modified: 2026-07-25 - Fix #scan-results staying hidden after scan completes (display:block in finalizeScanResultsTable)
 * Last Modified: 2026-07-25 - Fix Host:Port column showing "?" for default ports by passing host/port directly from SSE event
 * Last Modified: 2026-07-25 - Add handleIngestAll() to import certs + SSH keys + TLS protocols; wire ingest-all-btn;
 *                              populate ingest-from-scan panel on Step 3 with object counts
 */

// Scanner state
const scannerState = {
    currentStep: 1,
    generatedCSV: null,
    generatedFilename: null,
    targetCount: 0,
    scannedCSV: null,
    scannedFilename: null,
    // SSE / streaming scan state
    activeScanId: null,
    scanResults: [],
};

// Service label → badge colour
const SERVICE_COLORS = {
    tls:         '#3b82d4',
    ssh:         '#7c5cd8',
    ftp:         '#f59e0b',
    smtp:        '#f59e0b',
    smtps:       '#f59e0b',
    pop3:        '#f59e0b',
    imap:        '#f59e0b',
    http:        '#6b7280',
    'http-alt':  '#6b7280',
    mysql:       '#e8720c',
    postgresql:  '#336791',
    redis:       '#dc382d',
    mongodb:     '#4caf50',
    amqp:        '#ff6600',
    unknown:     '#9ca3af',
};

/**
 * Initialize scanner module
 */
function initScanner() {
    console.log('Initializing scanner module...');
    setupScannerEventListeners();
    showScannerStep(1);
}

/**
 * Set up event listeners for scanner
 */
function setupScannerEventListeners() {
    // Step 1: Generate targets
    const generateBtn = document.getElementById('generate-targets-btn');
    if (generateBtn) {
        generateBtn.addEventListener('click', handleGenerateTargets);
    }

    // Step 1 → Step 2
    const nextStepBtn = document.getElementById('next-step-btn');
    if (nextStepBtn) {
        nextStepBtn.addEventListener('click', () => showScannerStep(2));
    }

    // Download generated targets CSV
    const downloadBtn = document.getElementById('download-csv-btn');
    if (downloadBtn) {
        downloadBtn.addEventListener('click', downloadGeneratedCSV);
    }

    // Step 2: Scan targets
    const runScanBtn = document.getElementById('run-scan-btn');
    if (runScanBtn) {
        runScanBtn.addEventListener('click', handleRunScan);
    }

    // Stop scan
    const stopScanBtn = document.getElementById('stop-scan-btn');
    if (stopScanBtn) {
        stopScanBtn.addEventListener('click', handleStopScan);
    }

    const prevScanBtn = document.getElementById('prev-scan-btn');
    if (prevScanBtn) {
        prevScanBtn.addEventListener('click', () => showScannerStep(1));
    }

    // Step 3: Import CSV (certificates-only manual path)
    const importBtn = document.getElementById('import-csv-btn');
    if (importBtn) {
        importBtn.addEventListener('click', handleImportCSV);
    }

    // Step 3: Import All (keys + protocols + certs from scan)
    const ingestAllBtn = document.getElementById('ingest-all-btn');
    if (ingestAllBtn) {
        ingestAllBtn.addEventListener('click', handleIngestAll);
    }

    // CSV file input (step 3) — validate on select
    const csvFileInput = document.getElementById('csv-file-input');
    if (csvFileInput) {
        csvFileInput.addEventListener('change', handleCSVFileSelect);
    }

    // Step 3 ← Step 2
    const prevStepBtn = document.getElementById('prev-step-btn');
    if (prevStepBtn) {
        prevStepBtn.addEventListener('click', () => showScannerStep(2));
    }
}

/**
 * Show specific scanner step
 */
function showScannerStep(step) {
    scannerState.currentStep = step;

    document.querySelectorAll('.scanner-step').forEach(el => {
        el.style.display = 'none';
    });

    const currentStepEl = document.getElementById(`scanner-step-${step}`);
    if (currentStepEl) {
        currentStepEl.style.display = 'block';
    }

    document.querySelectorAll('.step-indicator').forEach((el, idx) => {
        if (idx + 1 === step) {
            el.classList.add('active');
            el.classList.remove('completed');
        } else if (idx + 1 < step) {
            el.classList.add('completed');
            el.classList.remove('active');
        } else {
            el.classList.remove('active', 'completed');
        }
    });

    // When landing on step 2, show/hide the generated-targets banner
    if (step === 2) {
        const banner = document.getElementById('generated-targets-banner');
        if (banner) {
            if (scannerState.generatedCSV) {
                document.getElementById('banner-target-count').textContent = scannerState.targetCount;
                document.getElementById('banner-filename').textContent = scannerState.generatedFilename || 'scan_targets.csv';
                banner.style.display = 'block';
            } else {
                banner.style.display = 'none';
            }
        }
    }

    // When landing on step 3, populate the ingest-from-scan panel
    if (step === 3) {
        const panel = document.getElementById('ingest-from-scan-panel');
        const summary = document.getElementById('ingest-scan-summary');
        const importBtn = document.getElementById('import-csv-btn');

        const hasResults = scannerState.scanResults && scannerState.scanResults.length > 0;
        if (panel) panel.style.display = hasResults ? 'block' : 'none';

        if (hasResults && summary) {
            const certs = scannerState.scanResults.filter(r => r.success && r.cert_b64).length;
            const keys  = scannerState.scanResults.filter(r => r.service === 'ssh' && r.ssh_host_key_type && r.success).length;
            const tls   = scannerState.scanResults.filter(r => r.service === 'tls' && r.tls_version && r.success).length;
            summary.textContent = `${certs} certificate(s), ${keys} SSH host key(s), ${tls} TLS protocol(s) ready to import.`;
        }

        if (importBtn && scannerState.scannedCSV) importBtn.disabled = false;
    }
}

/**
 * Handle target generation (Step 1)
 */
async function handleGenerateTargets() {
    const ipRanges = document.getElementById('ip-ranges').value.trim();
    const hosts = document.getElementById('hosts').value.trim();
    const ports = document.getElementById('ports').value.trim();
    const aliasPrefix = document.getElementById('alias-prefix').value.trim();

    if (!ipRanges && !hosts) {
        showNotification('Please provide either IP ranges or hosts', 'error');
        return;
    }

    if (!ports) {
        showNotification('Please provide ports', 'error');
        return;
    }

    const generateBtn = document.getElementById('generate-targets-btn');
    const originalText = generateBtn.textContent;
    generateBtn.disabled = true;
    generateBtn.textContent = 'Generating...';

    try {
        const response = await api.request('/scanner/generate-targets', {
            method: 'POST',
            body: JSON.stringify({
                ip_ranges: ipRanges || null,
                hosts: hosts || null,
                ports: ports,
                alias_prefix: aliasPrefix || ''
            })
        });

        if (response.target_count === 0) {
            showNotification('No targets generated. Check your inputs.', 'warning');
            return;
        }

        scannerState.generatedCSV = response.csv_content;
        scannerState.generatedFilename = response.filename;
        scannerState.targetCount = response.target_count;

        document.getElementById('target-count').textContent = response.target_count;
        document.getElementById('generated-filename').textContent = response.filename;
        document.getElementById('generation-result').style.display = 'block';
        document.getElementById('next-step-btn').disabled = false;

        showNotification(`Generated ${response.target_count} targets successfully`, 'success');

    } catch (error) {
        console.error('Failed to generate targets:', error);
        showNotification(error.message || 'Failed to generate targets', 'error');
    } finally {
        generateBtn.disabled = false;
        generateBtn.textContent = originalText;
    }
}

/**
 * Download generated targets CSV
 */
function downloadGeneratedCSV() {
    if (!scannerState.generatedCSV) {
        showNotification('No CSV to download', 'error');
        return;
    }

    const blob = new Blob([scannerState.generatedCSV], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = scannerState.generatedFilename || 'scan_targets.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);

    showNotification('CSV downloaded successfully', 'success');
}

// -----------------------------------------------------------------------
// Streaming scan (Step 2) — SSE-based with progress bar + stop button
// -----------------------------------------------------------------------

/**
 * Generate a simple UUID for the scan job.
 */
function generateScanId() {
    return 'scan-' + Date.now() + '-' + Math.random().toString(36).slice(2, 9);
}

/**
 * Update the progress bar and label.
 */
function updateScanProgress(index, total, host, port) {
    const pct = total > 0 ? Math.round((index / total) * 100) : 0;
    document.getElementById('scan-progress-bar').style.width = `${pct}%`;
    document.getElementById('scan-progress-counter').textContent = `${index} / ${total}`;
    document.getElementById('scan-progress-label').textContent =
        index < total ? `Scanning…` : `Finalising…`;
    if (host) {
        document.getElementById('scan-current-target').textContent =
            `▶ ${host}:${port}`;
    }
}

/**
 * Handle the SSL certificate scan (Step 2) — streaming via SSE.
 */
async function handleRunScan() {
    const fileInput = document.getElementById('scan-targets-file');
    const file = fileInput ? fileInput.files[0] : null;

    let targetsCsv = null;
    if (file) {
        try {
            targetsCsv = await readFileAsText(file);
        } catch {
            showNotification('Failed to read the targets file', 'error');
            return;
        }
    } else if (scannerState.generatedCSV) {
        targetsCsv = scannerState.generatedCSV;
    } else {
        showNotification('Please generate targets in Step 1 or upload a targets CSV file', 'error');
        return;
    }

    const timeout = parseFloat(document.getElementById('scan-timeout').value) || 5.0;
    const insecure = document.getElementById('scan-insecure').checked;

    const runBtn    = document.getElementById('run-scan-btn');
    const stopBtn   = document.getElementById('stop-scan-btn');
    const progressPanel = document.getElementById('scan-progress-panel');
    const scanResultsDiv = document.getElementById('scan-results');

    // Reset UI — clear previous scan results completely
    runBtn.disabled = true;
    stopBtn.style.display = 'inline-flex';
    progressPanel.style.display = 'block';
    if (scanResultsDiv) {
        scanResultsDiv.style.display = 'none';
        scanResultsDiv.innerHTML = '';  // remove old table and action bar
    }

    document.getElementById('scan-progress-bar').style.width = '0%';
    document.getElementById('scan-progress-counter').textContent = '0 / ?';
    document.getElementById('scan-progress-label').textContent = 'Connecting…';
    document.getElementById('scan-current-target').textContent = '';

    const scanId = generateScanId();
    scannerState.activeScanId = scanId;
    scannerState.scanResults = [];

    try {
        const response = await fetch(`${api.baseURL}/scanner/run-scan-stream`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                targets_csv: targetsCsv,
                timeout: timeout,
                insecure: insecure,
                scan_id: scanId,
            }),
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || 'Scan failed');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop(); // keep incomplete line

            for (const line of lines) {
                if (!line.startsWith('data:')) continue;
                const raw = line.slice(5).trim();
                if (!raw) continue;

                let event;
                try { event = JSON.parse(raw); } catch { continue; }

                if (event.type === 'scanning') {
                    updateScanProgress(event.index, event.total, event.host, event.port);
                } else if (event.type === 'progress') {
                    updateScanProgress(event.index, event.total, event.host, event.port);
                    if (event.result) {
                        scannerState.scanResults.push(event.result);
                        updateLiveResultsTable(event.result, event.host, event.port);
                    }
                } else if (event.type === 'done') {
                    handleScanDone(event);
                    break;
                }
            }
        }

    } catch (error) {
        console.error('Scan failed:', error);
        showNotification(error.message || 'Scan failed', 'error');
    } finally {
        scannerState.activeScanId = null;
        runBtn.disabled = false;
        stopBtn.style.display = 'none';
    }
}

/**
 * Signal the backend to stop the current scan.
 */
async function handleStopScan() {
    const scanId = scannerState.activeScanId;
    if (!scanId) return;

    try {
        await fetch(`${api.baseURL}/scanner/stop-scan/${scanId}`, { method: 'DELETE' });
        showNotification('Stop signal sent — finishing current target…', 'warning');
    } catch (e) {
        console.error('Failed to send stop signal:', e);
    }
}

/**
 * Called when the SSE stream emits a "done" event.
 */
function handleScanDone(event) {
    const progressPanel = document.getElementById('scan-progress-panel');

    // Finalize the progress bar
    document.getElementById('scan-progress-bar').style.width = '100%';
    document.getElementById('scan-progress-counter').textContent =
        `${event.scanned + event.failed} / ${event.total}`;
    document.getElementById('scan-progress-label').textContent =
        event.stopped ? 'Scan stopped.' : 'Scan complete.';
    document.getElementById('scan-current-target').textContent = '';

    // Persist scan CSV for Step 3
    scannerState.scannedCSV = event.certificates_csv;
    scannerState.scannedFilename = event.filename;

    const label = event.stopped
        ? `Scan stopped — ${event.scanned} certificates found (${event.failed} failed)`
        : `${event.scanned} of ${event.total} targets yielded certificates`;

    showNotification(label, event.failed > 0 ? 'warning' : 'success');

    // Finalize results table (add actions header)
    finalizeScanResultsTable(event);
}

// -----------------------------------------------------------------------
// Live results table helpers
// -----------------------------------------------------------------------

/**
 * Return a coloured service badge HTML string.
 */
function serviceBadge(service) {
    if (!service) return '<span style="color:#9ca3af; font-size:11px;">—</span>';
    const color = SERVICE_COLORS[service] || SERVICE_COLORS.unknown;
    return `<span style="display:inline-block; padding:2px 7px; border-radius:10px;
        background:${color}22; color:${color}; border:1px solid ${color}55;
        font-size:11px; font-weight:600; text-transform:uppercase;">${escapeHtml(service)}</span>`;
}

// Finding → display label + severity colour
const FINDING_META = {
    'EXPIRED':              { label: 'EXPIRED',         color: '#dc2626' },
    'EXPIRING_SOON':        { label: 'EXPIRING SOON',   color: '#f59e0b' },
    'SELF_SIGNED':          { label: 'SELF-SIGNED',     color: '#f59e0b' },
    'SHA1_SIGNATURE':       { label: 'SHA-1 CERT',      color: '#dc2626' },
    'LEGACY_TLS':           { label: 'LEGACY TLS',      color: '#dc2626' },
    'WEAK_CIPHER':          { label: 'WEAK CIPHER',     color: '#dc2626' },
    'WEAK_KEY':             { label: 'WEAK KEY',        color: '#dc2626' },
    'WEAK_SSH_HOSTKEY':     { label: 'WEAK SSH KEY',    color: '#dc2626' },
    'LEGACY_SSH_KEX':       { label: 'LEGACY SSH KEX',  color: '#f59e0b' },
};

/**
 * Render an array of finding strings as coloured badge HTML.
 */
function findingsBadges(findings) {
    if (!findings || findings.length === 0) {
        return '<span style="color:#16a34a; font-size:11px;">✓ Clean</span>';
    }
    return findings.map(f => {
        // Match prefix before ':' to look up meta
        const key = Object.keys(FINDING_META).find(k => f.startsWith(k)) || '';
        const meta = FINDING_META[key] || { label: f.split(':')[0], color: '#7c5cd8' };
        const detail = f.includes(':') ? f.split(':').slice(1).join(':') : '';
        const title = detail ? escapeHtml(detail) : '';
        const displayLabel = meta.label + (detail ? '' : '');
        return `<span title="${title}" style="display:inline-block; margin:1px 2px; padding:2px 6px;
            border-radius:10px; background:${meta.color}18; color:${meta.color};
            border:1px solid ${meta.color}44; font-size:10px; font-weight:700;
            white-space:nowrap; cursor:default;">${escapeHtml(displayLabel)}</span>`;
    }).join('');
}

/**
 * Create or get the scan live-results table container inside #scan-results.
 */
function ensureLiveScanTable() {
    const div = document.getElementById('scan-results');
    if (!div) return null;
    div.style.display = 'block';

    let table = document.getElementById('scan-live-table');
    if (!table) {
        const wrapper = document.createElement('div');
        wrapper.id = 'scan-live-table-wrapper';
        wrapper.style.cssText = 'overflow-x:auto; margin-top: 8px;';
        wrapper.innerHTML = `
        <table id="scan-live-table" style="width:100%; border-collapse:collapse; font-size:13px;">
            <thead>
                <tr style="background:#f7f8fa;">
                    <th style="text-align:left; padding:6px 10px; border-bottom:2px solid #e5e7eb;">Alias</th>
                    <th style="text-align:left; padding:6px 10px; border-bottom:2px solid #e5e7eb;">Host : Port</th>
                    <th style="text-align:left; padding:6px 10px; border-bottom:2px solid #e5e7eb;">Service</th>
                    <th style="text-align:left; padding:6px 10px; border-bottom:2px solid #e5e7eb;">TLS / Protocol</th>
                    <th style="text-align:left; padding:6px 10px; border-bottom:2px solid #e5e7eb;">Subject / Key Info</th>
                    <th style="text-align:left; padding:6px 10px; border-bottom:2px solid #e5e7eb;">Expires</th>
                    <th style="text-align:left; padding:6px 10px; border-bottom:2px solid #e5e7eb;">Findings</th>
                    <th style="text-align:left; padding:6px 10px; border-bottom:2px solid #e5e7eb;">Status</th>
                </tr>
            </thead>
            <tbody id="scan-live-tbody"></tbody>
        </table>`;
        div.appendChild(wrapper);
        table = document.getElementById('scan-live-table');
    }
    return table;
}

/**
 * Append a single result row to the live table.
 * host/port are passed directly from the SSE event to avoid URL.port returning ""
 * for default ports (e.g. 443 on https://).
 */
function updateLiveResultsTable(r, host, port) {
    ensureLiveScanTable();
    const tbody = document.getElementById('scan-live-tbody');
    if (!tbody) return;

    // Prefer explicit host/port from SSE event; fall back to parsing the URI
    let hostPort;
    if (host && port) {
        hostPort = `${escapeHtml(host)}:${port}`;
    } else {
        const parsed = tryParseUri(r.uri);
        hostPort = parsed ? `${parsed.hostname}:${parsed.port || '?'}` : escapeHtml(r.uri);
    }

    let subjectInfo = '—';
    if (r.service === 'tls' && r.cert_subject) {
        subjectInfo = `<span title="${escapeHtml(r.cert_subject)}">${escapeHtml(shortDN(r.cert_subject))}</span>`;
    } else if (r.service === 'ssh') {
        // Show host key type (e.g. ssh-ed25519) and algorithm list
        const keyLine = r.ssh_host_key_type
            ? `<span style="font-family:monospace; font-size:12px; font-weight:600; color:#7c5cd8;">${escapeHtml(r.ssh_host_key_type)}</span>`
            : `<span style="font-size:11px; color:#6b7280;">${escapeHtml(r.service_banner || 'SSH detected')}</span>`;
        const algLine = r.ssh_host_key_fingerprint
            ? `<br><span style="font-family:monospace; font-size:10px; color:#6b7280;" title="Advertised key algorithms: ${escapeHtml(r.ssh_host_key_fingerprint)}">${escapeHtml(r.ssh_host_key_fingerprint.slice(0, 52))}${r.ssh_host_key_fingerprint.length > 52 ? '…' : ''}</span>`
            : '';
        subjectInfo = keyLine + algLine;
    } else if (r.service_banner) {
        subjectInfo = `<span style="font-family:monospace; font-size:11px; color:#6b7280;">${escapeHtml(r.service_banner.slice(0, 60))}</span>`;
    }

    let tlsInfo = '—';
    if (r.tls_version) {
        tlsInfo = `${escapeHtml(r.tls_version)}`;
        if (r.cipher_suite) tlsInfo += `<br><span style="font-size:11px; color:#6b7280;">${escapeHtml(r.cipher_suite)}</span>`;
    }

    const statusHtml = r.success
        ? `<span style="color:#16a34a; font-weight:600;">✓ OK</span>`
        : `<span style="color:#dc2626;" title="${escapeHtml(r.error || '')}">✗ ${escapeHtml((r.error || 'Failed').slice(0, 32))}</span>`;

    const expiry = r.cert_not_after ? escapeHtml(r.cert_not_after) : '—';

    // Colour the row background if there are high-severity findings
    const findings = r.findings || [];
    const hasCritical = findings.some(f =>
        f.startsWith('EXPIRED') || f.startsWith('WEAK_CIPHER') ||
        f.startsWith('WEAK_KEY') || f.startsWith('SHA1') || f.startsWith('LEGACY_TLS'));
    const hasWarn = !hasCritical && findings.some(f =>
        f.startsWith('EXPIRING_SOON') || f.startsWith('SELF_SIGNED') || f.startsWith('LEGACY_SSH'));

    const tr = document.createElement('tr');
    tr.style.borderBottom = '1px solid #f3f4f6';
    if (hasCritical) tr.style.background = '#fef2f2';
    else if (hasWarn)  tr.style.background = '#fffbeb';

    tr.innerHTML = `
        <td style="padding:6px 10px; font-family:monospace; font-size:12px;">${escapeHtml(r.alias)}</td>
        <td style="padding:6px 10px; font-family:monospace; font-size:12px;">${hostPort}</td>
        <td style="padding:6px 10px;">${serviceBadge(r.service)}</td>
        <td style="padding:6px 10px; font-size:12px;">${tlsInfo}</td>
        <td style="padding:6px 10px; font-size:12px; max-width:200px; overflow:hidden; text-overflow:ellipsis;">${subjectInfo}</td>
        <td style="padding:6px 10px; font-size:12px; white-space:nowrap;">${expiry}</td>
        <td style="padding:6px 10px; line-height:1.8;">${findingsBadges(findings)}</td>
        <td style="padding:6px 10px;">${statusHtml}</td>`;
    tbody.appendChild(tr);
}

/**
 * Add the action buttons row above the table once the scan is done.
 */
function finalizeScanResultsTable(event) {
    const div = document.getElementById('scan-results');
    if (!div) return;
    div.style.display = 'block';

    // Remove old action bar if present
    const old = document.getElementById('scan-actions-bar');
    if (old) old.remove();

    const bar = document.createElement('div');
    bar.id = 'scan-actions-bar';
    bar.style.cssText = 'margin-bottom: 16px;';
    bar.innerHTML = `
        <div class="result-stats" style="margin-bottom: 10px;">
            <p><strong>Total Targets:</strong> ${event.total}
               &nbsp;|&nbsp; <strong style="color:var(--success-color,green)">Succeeded:</strong> ${event.scanned}
               &nbsp;|&nbsp; <strong style="color:#dc2626;">Failed:</strong> ${event.failed}
               ${event.stopped ? '&nbsp;|&nbsp; <em style="color:#f59e0b;">Stopped early</em>' : ''}
            </p>
        </div>
        <div class="result-actions">
            <button class="btn btn-success" onclick="downloadScannedCSV()">⬇️ Download Certificates CSV</button>
            <button class="btn btn-primary" onclick="showScannerStep(3)">Next: Import Certificates →</button>
        </div>`;
    div.insertBefore(bar, div.firstChild);
}

// -----------------------------------------------------------------------
// Certificates CSV download (Step 2 → Step 3)
// -----------------------------------------------------------------------

/**
 * Download the certificates CSV produced by the scan
 */
function downloadScannedCSV() {
    if (!scannerState.scannedCSV) {
        showNotification('No scan results to download', 'error');
        return;
    }
    const blob = new Blob([scannerState.scannedCSV], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = scannerState.scannedFilename || 'certificates.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
    showNotification('Certificates CSV downloaded', 'success');
}

// -----------------------------------------------------------------------
// CSV import (Step 3) — unchanged logic
// -----------------------------------------------------------------------

/**
 * Handle CSV file selection for import (Step 3)
 */
async function handleCSVFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;

    try {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch(`${api.baseURL}/scanner/validate-csv`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to validate CSV');
        }

        const result = await response.json();
        displayValidationResults(result);

        const importBtn = document.getElementById('import-csv-btn');
        if (importBtn) {
            importBtn.disabled = result.valid_rows === 0;
        }

    } catch (error) {
        console.error('Failed to validate CSV:', error);
        showNotification(error.message || 'Failed to validate CSV', 'error');
    }
}

/**
 * Display CSV validation results (Step 3)
 */
function displayValidationResults(results) {
    const resultsDiv = document.getElementById('validation-results');
    if (!resultsDiv) return;

    let html = `
        <div class="validation-summary">
            <p><strong>Total Rows:</strong> ${results.total_rows}</p>
            <p><strong>Valid Rows:</strong> <span class="text-success">${results.valid_rows}</span></p>
            <p><strong>Invalid Rows:</strong> <span class="text-danger">${results.invalid_rows}</span></p>
        </div>
    `;

    if (results.validation_results && results.validation_results.length > 0) {
        const errors = results.validation_results.filter(r => !r.is_valid).slice(0, 5);
        if (errors.length > 0) {
            html += '<div class="validation-errors"><h4>Validation Errors (first 5):</h4><ul>';
            errors.forEach(error => {
                html += `<li>Row ${error.row_number}: ${error.errors.join(', ')}</li>`;
            });
            html += '</ul></div>';
        }
    }

    resultsDiv.innerHTML = html;
    resultsDiv.style.display = 'block';
}

/**
 * Handle certificate CSV import (Step 3)
 * Uses either an uploaded file or the certificates CSV from the scan step.
 */
async function handleImportCSV() {
    const fileInput = document.getElementById('csv-file-input');
    const file = fileInput ? fileInput.files[0] : null;

    const importBtn = document.getElementById('import-csv-btn');
    const originalText = importBtn.textContent;
    importBtn.disabled = true;
    importBtn.textContent = 'Importing...';

    try {
        let formData = new FormData();

        if (file) {
            formData.append('file', file);
        } else if (scannerState.scannedCSV) {
            const blob = new Blob([scannerState.scannedCSV], { type: 'text/csv' });
            formData.append('file', new File([blob], scannerState.scannedFilename || 'certificates.csv', { type: 'text/csv' }));
        } else {
            showNotification('Please select a CSV file or run a scan first', 'error');
            return;
        }

        const response = await fetch(`${api.baseURL}/scanner/import-csv`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to import certificates');
        }

        const result = await response.json();
        displayImportResults(result);

        showNotification(
            `Imported ${result.imported_count} of ${result.total_rows} certificates`,
            result.failed_count > 0 ? 'warning' : 'success'
        );

    } catch (error) {
        console.error('Failed to import CSV:', error);
        showNotification(error.message || 'Failed to import certificates', 'error');
    } finally {
        importBtn.disabled = false;
        importBtn.textContent = originalText;
    }
}

/**
 * Import all scan results to GCM: certificates (CSV) + SSH keys + TLS protocols.
 */
async function handleIngestAll() {
    if (!scannerState.scanResults || scannerState.scanResults.length === 0) {
        showNotification('No scan results in memory. Please run a scan first.', 'error');
        return;
    }

    const btn = document.getElementById('ingest-all-btn');
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Importing…';

    try {
        // 1. Import TLS certificates via existing CSV endpoint
        let certResult = { imported_count: 0, failed_count: 0, total_rows: 0, errors: [] };
        if (scannerState.scannedCSV) {
            const blob = new Blob([scannerState.scannedCSV], { type: 'text/csv' });
            const formData = new FormData();
            formData.append('file', new File([blob], scannerState.scannedFilename || 'certificates.csv', { type: 'text/csv' }));

            const certResp = await fetch(`${api.baseURL}/scanner/import-csv`, {
                method: 'POST',
                body: formData,
            });
            if (certResp.ok) {
                certResult = await certResp.json();
            } else {
                const err = await certResp.json();
                certResult.errors = [err.detail || 'Certificate import failed'];
            }
        }

        // 2. Ingest SSH keys + TLS protocols from scan results
        const ingestResp = await fetch(`${api.baseURL}/scanner/ingest-scan-results`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ results: scannerState.scanResults }),
        });

        let ingestResult = { keys_imported: 0, keys_failed: 0, protocols_imported: 0, protocols_failed: 0, errors: [] };
        if (ingestResp.ok) {
            ingestResult = await ingestResp.json();
        } else {
            const err = await ingestResp.json();
            // err.detail may be a string (HTTPException) or an array (Pydantic 422)
            const detail = Array.isArray(err.detail)
                ? err.detail.map(e => `${e.loc?.join('.')}: ${e.msg}`).join('; ')
                : (err.detail || 'Key/protocol ingest failed');
            ingestResult.errors = [detail];
        }

        displayIngestAllResults(certResult, ingestResult);

        const totalImported = certResult.imported_count + ingestResult.keys_imported + ingestResult.protocols_imported;
        const totalFailed   = certResult.failed_count  + ingestResult.keys_failed  + ingestResult.protocols_failed;
        showNotification(
            `Imported ${totalImported} object(s) to GCM` + (totalFailed > 0 ? ` (${totalFailed} failed)` : ''),
            totalFailed > 0 ? 'warning' : 'success'
        );

    } catch (error) {
        console.error('Ingest all failed:', error);
        showNotification(error.message || 'Import failed', 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = originalText;
    }
}

/**
 * Display combined ingest-all results (Step 3)
 */
function displayIngestAllResults(certResult, ingestResult) {
    const resultsDiv = document.getElementById('import-results');
    if (!resultsDiv) return;

    const row = (label, ok, fail) =>
        `<tr>
            <td style="padding:4px 10px;">${label}</td>
            <td style="padding:4px 10px; color:#16a34a; font-weight:600;">${ok}</td>
            <td style="padding:4px 10px; color:${fail > 0 ? '#dc2626' : '#6b7280'};">${fail}</td>
        </tr>`;

    let html = `
        <table style="width:100%; border-collapse:collapse; font-size:13px; margin-bottom:12px;">
            <thead>
                <tr style="background:#f7f8fa; border-bottom:2px solid #e5e7eb;">
                    <th style="text-align:left; padding:6px 10px;">Object type</th>
                    <th style="text-align:left; padding:6px 10px;">Imported</th>
                    <th style="text-align:left; padding:6px 10px;">Failed</th>
                </tr>
            </thead>
            <tbody>
                ${row('Certificates', certResult.imported_count, certResult.failed_count)}
                ${row('SSH Host Keys', ingestResult.keys_imported, ingestResult.keys_failed)}
                ${row('TLS Protocols', ingestResult.protocols_imported, ingestResult.protocols_failed)}
            </tbody>
        </table>`;

    const allErrors = [...(certResult.errors || []), ...(ingestResult.errors || [])];
    if (allErrors.length > 0) {
        html += '<div style="margin-top:8px;"><strong>Errors:</strong><ul style="margin:4px 0 0 16px; font-size:12px;">';
        allErrors.forEach(e => { html += `<li>${escapeHtml(e)}</li>`; });
        html += '</ul></div>';
    }

    resultsDiv.innerHTML = html;
    resultsDiv.style.display = 'block';
}

/**
 * Display import results for the certificates-only CSV path (Step 3)
 */
function displayImportResults(results) {
    const resultsDiv = document.getElementById('import-results');
    if (!resultsDiv) return;

    let html = `
        <div class="import-summary">
            <p><strong>Total Rows:</strong> ${results.total_rows}</p>
            <p><strong>Imported:</strong> <span class="text-success">${results.imported_count}</span></p>
            <p><strong>Failed:</strong> <span class="text-danger">${results.failed_count}</span></p>
        </div>
    `;

    if (results.errors && results.errors.length > 0) {
        html += '<div class="import-errors"><h4>Import Errors:</h4><ul>';
        results.errors.forEach(error => {
            html += `<li>${error}</li>`;
        });
        html += '</ul></div>';
    }

    resultsDiv.innerHTML = html;
    resultsDiv.style.display = 'block';
}

// -----------------------------------------------------------------------
// Utilities
// -----------------------------------------------------------------------

/**
 * Read file as text
 */
function readFileAsText(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = (e) => resolve(e.target.result);
        reader.onerror = () => reject(new Error('Failed to read file'));
        reader.readAsText(file);
    });
}

/**
 * Escape HTML special characters for safe rendering
 */
function escapeHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

/**
 * Try to parse a URI string; return null on failure.
 */
function tryParseUri(uri) {
    try { return new URL(uri); } catch { return null; }
}

/**
 * Extract the CN from a /CN=foo/O=bar style DN string, or return the full string truncated.
 */
function shortDN(dn) {
    const cnMatch = dn.match(/CN=([^/]+)/);
    return cnMatch ? cnMatch[1] : dn.slice(0, 40);
}

// Export functions
window.scannerModule = {
    init: initScanner,
    showStep: showScannerStep
};
