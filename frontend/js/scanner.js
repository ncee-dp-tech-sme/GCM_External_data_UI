/**
 * Scanner module for GCM Web UI
 * Handles target generation and certificate import from CSV
 * 
 * Created: 2026-06-02
 * Last Modified: 2026-06-02
 */

// Scanner state
const scannerState = {
    currentStep: 1,
    generatedCSV: null,
    generatedFilename: null,
    targetCount: 0
};

/**
 * Initialize scanner module
 */
function initScanner() {
    console.log('Initializing scanner module...');
    
    // Set up event listeners
    setupScannerEventListeners();
    
    // Show step 1 by default
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
    
    // Step 2: Import CSV
    const importBtn = document.getElementById('import-csv-btn');
    if (importBtn) {
        importBtn.addEventListener('click', handleImportCSV);
    }
    
    // CSV file input
    const csvFileInput = document.getElementById('csv-file-input');
    if (csvFileInput) {
        csvFileInput.addEventListener('change', handleCSVFileSelect);
    }
    
    // Download generated CSV
    const downloadBtn = document.getElementById('download-csv-btn');
    if (downloadBtn) {
        downloadBtn.addEventListener('click', downloadGeneratedCSV);
    }
    
    // Navigation buttons
    const nextStepBtn = document.getElementById('next-step-btn');
    if (nextStepBtn) {
        nextStepBtn.addEventListener('click', () => showScannerStep(2));
    }
    
    const prevStepBtn = document.getElementById('prev-step-btn');
    if (prevStepBtn) {
        prevStepBtn.addEventListener('click', () => showScannerStep(1));
    }
}

/**
 * Show specific scanner step
 */
function showScannerStep(step) {
    scannerState.currentStep = step;
    
    // Hide all steps
    document.querySelectorAll('.scanner-step').forEach(el => {
        el.style.display = 'none';
    });
    
    // Show current step
    const currentStepEl = document.getElementById(`scanner-step-${step}`);
    if (currentStepEl) {
        currentStepEl.style.display = 'block';
    }
    
    // Update step indicators
    document.querySelectorAll('.step-indicator').forEach((el, idx) => {
        if (idx + 1 === step) {
            el.classList.add('active');
        } else if (idx + 1 < step) {
            el.classList.add('completed');
            el.classList.remove('active');
        } else {
            el.classList.remove('active', 'completed');
        }
    });
}

/**
 * Handle target generation
 */
async function handleGenerateTargets() {
    const ipRanges = document.getElementById('ip-ranges').value.trim();
    const hosts = document.getElementById('hosts').value.trim();
    const ports = document.getElementById('ports').value.trim();
    const aliasPrefix = document.getElementById('alias-prefix').value.trim();
    
    // Validate inputs
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
        
        // Store generated CSV
        scannerState.generatedCSV = response.csv_content;
        scannerState.generatedFilename = response.filename;
        scannerState.targetCount = response.target_count;
        
        // Update UI
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
 * Download generated CSV
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
 * Handle CSV file selection
 */
async function handleCSVFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    // Validate CSV using file upload
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
        
        // Display validation results
        displayValidationResults(result);
        
        // Enable import button if there are valid rows
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
 * Display CSV validation results
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
        // Show first few validation errors
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
 * Handle CSV import
 */
async function handleImportCSV() {
    const fileInput = document.getElementById('csv-file-input');
    const file = fileInput.files[0];
    
    if (!file) {
        showNotification('Please select a CSV file', 'error');
        return;
    }
    
    const importBtn = document.getElementById('import-csv-btn');
    const originalText = importBtn.textContent;
    importBtn.disabled = true;
    importBtn.textContent = 'Importing...';
    
    try {
        // Import certificates using file upload
        const formData = new FormData();
        formData.append('file', file);
        
        const response = await fetch(`${api.baseURL}/scanner/import-csv`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to import certificates');
        }
        
        const result = await response.json();
        
        // Display import results
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
 * Display import results
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
        reader.onerror = (e) => reject(new Error('Failed to read file'));
        reader.readAsText(file);
    });
}

// Export functions
window.scannerModule = {
    init: initScanner,
    showStep: showScannerStep
};

// Made with Bob