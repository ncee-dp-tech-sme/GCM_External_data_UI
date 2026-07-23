/**
 * Scanner module for GCM Web UI
 * Handles target generation, SSL certificate scanning, and certificate import from CSV
 *
 * Created: 2026-06-02
 * Last Modified: 2026-06-02 - Initial implementation
 * Last Modified: 2026-07-25 - Added Step 2 scan functionality (run-scan endpoint)
 */

// Scanner state
const scannerState = {
    currentStep: 1,
    generatedCSV: null,
    generatedFilename: null,
    targetCount: 0,
    scannedCSV: null,
    scannedFilename: null,
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

    const prevScanBtn = document.getElementById('prev-scan-btn');
    if (prevScanBtn) {
        prevScanBtn.addEventListener('click', () => showScannerStep(1));
    }

    // Step 3: Import CSV
    const importBtn = document.getElementById('import-csv-btn');
    if (importBtn) {
        importBtn.addEventListener('click', handleImportCSV);
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

    // When landing on step 3 with a scan CSV available, pre-enable import
    if (step === 3 && scannerState.scannedCSV) {
        const importBtn = document.getElementById('import-csv-btn');
        if (importBtn) importBtn.disabled = false;
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

/**
 * Handle the SSL certificate scan (Step 2)
 * Uses either an uploaded targets file or the CSV generated in Step 1.
 */
async function handleRunScan() {
    const fileInput = document.getElementById('scan-targets-file');
    const file = fileInput ? fileInput.files[0] : null;

    // Resolve which CSV to scan
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

    const runBtn = document.getElementById('run-scan-btn');
    const originalText = runBtn.textContent;
    runBtn.disabled = true;
    runBtn.textContent = 'Scanning…';

    // Clear previous scan results
    const scanResultsDiv = document.getElementById('scan-results');
    if (scanResultsDiv) scanResultsDiv.style.display = 'none';

    try {
        const response = await api.request('/scanner/run-scan', {
            method: 'POST',
            body: JSON.stringify({
                targets_csv: targetsCsv,
                timeout: timeout,
                insecure: insecure,
            })
        });

        // Persist certificates CSV for Step 3
        scannerState.scannedCSV = response.certificates_csv;
        scannerState.scannedFilename = response.filename;

        displayScanResults(response);

        const label = `${response.scanned} of ${response.total_targets} targets yielded certificates`;
        showNotification(
            label,
            response.failed > 0 ? 'warning' : 'success'
        );

    } catch (error) {
        console.error('Scan failed:', error);
        showNotification(error.message || 'Scan failed', 'error');
    } finally {
        runBtn.disabled = false;
        runBtn.textContent = originalText;
    }
}

/**
 * Display scan results table and navigation to Step 3
 */
function displayScanResults(result) {
    const div = document.getElementById('scan-results');
    if (!div) return;

    const failedRows = result.results.filter(r => !r.success);
    const successRows = result.results.filter(r => r.success);

    let html = `
        <div class="result-stats" style="margin-bottom: 12px;">
            <p><strong>Total Targets:</strong> ${result.total_targets}</p>
            <p><strong>Certificates Retrieved:</strong> <span style="color: var(--success-color, green);">${result.scanned}</span></p>
            <p><strong>Failed:</strong> <span style="color: var(--danger-color, #c00);">${result.failed}</span></p>
            <p><strong>Output File:</strong> ${result.filename}</p>
        </div>
        <div class="result-actions" style="margin-bottom: 16px;">
            <button class="btn btn-success" onclick="downloadScannedCSV()">⬇️ Download Certificates CSV</button>
            <button class="btn btn-primary" onclick="showScannerStep(3)">Next: Import Certificates →</button>
        </div>
    `;

    if (failedRows.length > 0) {
        html += `<details style="margin-top: 8px;"><summary><strong>Failed targets (${failedRows.length})</strong></summary>
            <table style="width:100%; border-collapse:collapse; margin-top:8px; font-size:13px;">
                <thead><tr>
                    <th style="text-align:left; padding:4px 8px; border-bottom:1px solid #e0e0e0;">Alias</th>
                    <th style="text-align:left; padding:4px 8px; border-bottom:1px solid #e0e0e0;">URI</th>
                    <th style="text-align:left; padding:4px 8px; border-bottom:1px solid #e0e0e0;">Error</th>
                </tr></thead><tbody>`;
        failedRows.forEach(r => {
            html += `<tr>
                <td style="padding:4px 8px;">${escapeHtml(r.alias)}</td>
                <td style="padding:4px 8px;">${escapeHtml(r.uri)}</td>
                <td style="padding:4px 8px; color:#c00;">${escapeHtml(r.error || '')}</td>
            </tr>`;
        });
        html += `</tbody></table></details>`;
    }

    div.innerHTML = html;
    div.style.display = 'block';
}

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
            // Wrap the in-memory CSV as a File object for the multipart upload
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
 * Display import results (Step 3)
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

// Export functions
window.scannerModule = {
    init: initScanner,
    showStep: showScannerStep
};

// Made with Bob
