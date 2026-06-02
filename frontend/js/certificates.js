// 2026-06-02T00:02:00Z - Created certificate management functions for GCM Web UI

/**
 * Certificate Management Functions
 */

// Global state for certificates
let currentCertificates = [];
let currentPage = 1;
let totalPages = 1;
let currentFilters = {};

// Load certificates page
async function loadCertificates() {
    try {
        // Load statistics
        await loadCertificateStats();
        
        // Load certificates list
        await loadCertificatesList();
        
        // Setup event listeners
        setupCertificateEventListeners();
        
    } catch (error) {
        console.error('Error loading certificates:', error);
        showToast(error.message || 'Failed to load certificates', 'error');
    }
}

// Setup event listeners for certificate page
function setupCertificateEventListeners() {
    // Search input
    const searchInput = document.getElementById('certSearch');
    if (searchInput && !searchInput.dataset.listenerAdded) {
        searchInput.addEventListener('input', debounce(() => {
            currentPage = 1;
            loadCertificatesList();
        }, 500));
        searchInput.dataset.listenerAdded = 'true';
    }
    
    // Filter select
    const filterSelect = document.getElementById('certFilter');
    if (filterSelect && !filterSelect.dataset.listenerAdded) {
        filterSelect.addEventListener('change', () => {
            currentPage = 1;
            loadCertificatesList();
        });
        filterSelect.dataset.listenerAdded = 'true';
    }
    
    // Pagination buttons
    const prevBtn = document.getElementById('certPrevPage');
    const nextBtn = document.getElementById('certNextPage');
    
    if (prevBtn && !prevBtn.dataset.listenerAdded) {
        prevBtn.addEventListener('click', () => {
            if (currentPage > 1) {
                currentPage--;
                loadCertificatesList();
            }
        });
        prevBtn.dataset.listenerAdded = 'true';
    }
    
    if (nextBtn && !nextBtn.dataset.listenerAdded) {
        nextBtn.addEventListener('click', () => {
            if (currentPage < totalPages) {
                currentPage++;
                loadCertificatesList();
            }
        });
        nextBtn.dataset.listenerAdded = 'true';
    }
    
    // Upload form
    const uploadForm = document.getElementById('uploadCertForm');
    if (uploadForm && !uploadForm.dataset.listenerAdded) {
        uploadForm.addEventListener('submit', handleCertificateUpload);
        uploadForm.dataset.listenerAdded = 'true';
    }
}

// Debounce helper
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Load certificate statistics
async function loadCertificateStats() {
    try {
        const stats = await api.getCertificateStats();
        
        document.getElementById('totalCertificates').textContent = stats.total_certificates;
        document.getElementById('validCertificates').textContent = 
            stats.total_certificates - stats.expired_certificates - stats.expiring_soon;
        document.getElementById('expiringSoonCertificates').textContent = stats.expiring_soon;
        document.getElementById('expiredCertificates').textContent = stats.expired_certificates;
        
    } catch (error) {
        console.error('Error loading certificate stats:', error);
        // Don't show error toast for stats, just log it
    }
}

// Load certificates list
async function loadCertificatesList() {
    try {
        // Build filters
        const filters = {
            page: currentPage,
            page_size: 10,
            sort_by: 'created_at',
            sort_order: 'desc'
        };
        
        // Add search
        const searchValue = document.getElementById('certSearch')?.value;
        if (searchValue) {
            filters.search = searchValue;
        }
        
        // Add filter
        const filterValue = document.getElementById('certFilter')?.value;
        if (filterValue === 'expired') {
            filters.is_expired = true;
        } else if (filterValue === 'expiring') {
            filters.expiring_days = 30;
        } else if (filterValue === 'valid') {
            filters.is_expired = false;
        }
        
        currentFilters = filters;
        
        // Fetch certificates
        const data = await api.getCertificates(filters);
        currentCertificates = data.certificates;
        totalPages = data.total_pages;
        
        // Render table
        renderCertificatesTable(data.certificates);
        
        // Update pagination
        updatePagination(data.page, data.total_pages, data.total);
        
    } catch (error) {
        console.error('Error loading certificates list:', error);
        showToast(error.message || 'Failed to load certificates', 'error');
    }
}

// Render certificates table
function renderCertificatesTable(certificates) {
    const tbody = document.getElementById('certificatesTableBody');
    
    if (certificates.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="9" class="text-center">
                    <p class="placeholder">No certificates found. Try adjusting your filters or sync from GCM.</p>
                </td>
            </tr>
        `;
        return;
    }
    
    tbody.innerHTML = certificates.map(cert => {
        const status = getCertificateStatus(cert);
        const statusBadge = `<span class="badge ${status.class}">${status.text}</span>`;
        
        return `
            <tr>
                <td><input type="checkbox" class="cert-checkbox" data-id="${cert.id}"></td>
                <td>${cert.alias || 'N/A'}</td>
                <td>${truncate(cert.subject_cn || cert.subject || 'N/A', 30)}</td>
                <td>${truncate(cert.issuer_cn || cert.issuer || 'N/A', 30)}</td>
                <td>${truncate(cert.uri || 'N/A', 40)}</td>
                <td>${formatDate(cert.valid_from)}</td>
                <td>${formatDate(cert.valid_to)}</td>
                <td>${statusBadge}</td>
                <td>
                    <button class="btn btn-sm btn-primary" onclick="viewCertificateDetails('${cert.crypto_id || cert.id}')">
                        👁️ View
                    </button>
                    <button class="btn btn-sm btn-danger" onclick="deleteSingleCertificate(${cert.id})">
                        🗑️
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

// Get certificate status
function getCertificateStatus(cert) {
    if (cert.is_expired) {
        return { text: 'Expired', class: 'badge-danger' };
    }
    if (cert.days_until_expiry !== null && cert.days_until_expiry <= 30) {
        return { text: `Expiring in ${cert.days_until_expiry} days`, class: 'badge-warning' };
    }
    return { text: 'Valid', class: 'badge-success' };
}

// Format date
function formatDate(dateString) {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleDateString();
}

// Update pagination
function updatePagination(page, total, count) {
    document.getElementById('certPageInfo').textContent = `Page ${page} of ${total} (${count} total)`;
    document.getElementById('certPrevPage').disabled = page <= 1;
    document.getElementById('certNextPage').disabled = page >= total;
}

// Sync certificates from GCM
async function syncCertificates() {
    const btn = event?.target;
    if (btn) setButtonLoading(btn, true);
    
    try {
        showToast('Syncing certificates from GCM...', 'info');
        const result = await api.syncCertificates(1, 300);
        
        showToast(`Synced ${result.synced} certificates successfully!`, 'success');
        
        // Reload the page
        await loadCertificates();
        
    } catch (error) {
        console.error('Error syncing certificates:', error);
        showToast(error.message || 'Failed to sync certificates', 'error');
    } finally {
        if (btn) setButtonLoading(btn, false);
    }
}

// Show upload certificate modal
function showUploadCertModal() {
    document.getElementById('uploadCertModal').style.display = 'flex';
    document.getElementById('uploadCertForm').reset();
}

// Close upload certificate modal
function closeUploadCertModal() {
    document.getElementById('uploadCertModal').style.display = 'none';
}

// Handle certificate upload
async function handleCertificateUpload(event) {
    event.preventDefault();
    
    const submitBtn = event.target.querySelector('button[type="submit"]');
    setButtonLoading(submitBtn, true);
    
    try {
        const fileInput = document.getElementById('certFile');
        const uri = document.getElementById('certUri').value;
        const alias = document.getElementById('certAlias').value;
        
        if (!fileInput.files[0]) {
            throw new Error('Please select a certificate file');
        }
        
        // Read file as base64
        const file = fileInput.files[0];
        const base64 = await fileToBase64(file);
        
        // Upload certificate
        const certData = {
            cert_file_base64: base64,
            uri: uri,
            alias: alias || undefined
        };
        
        await api.uploadCertificate(certData);
        
        showToast('Certificate uploaded successfully!', 'success');
        closeUploadCertModal();
        
        // Reload certificates
        await loadCertificatesList();
        await loadCertificateStats();
        
    } catch (error) {
        console.error('Error uploading certificate:', error);
        showToast(error.message || 'Failed to upload certificate', 'error');
    } finally {
        setButtonLoading(submitBtn, false);
    }
}

// Convert file to base64
function fileToBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.readAsDataURL(file);
        reader.onload = () => {
            // Remove data:*/*;base64, prefix
            const base64 = reader.result.split(',')[1];
            resolve(base64);
        };
        reader.onerror = error => reject(error);
    });
}

// View certificate details
async function viewCertificateDetails(certificateId) {
    try {
        const cert = await api.getCertificate(certificateId);
        
        const modal = document.getElementById('certDetailsModal');
        const content = document.getElementById('certDetailsContent');
        
        content.innerHTML = `
            <div class="cert-details">
                <div class="detail-section">
                    <h4>Basic Information</h4>
                    <div class="detail-grid">
                        <div class="detail-item">
                            <span class="detail-label">Alias:</span>
                            <span class="detail-value">${cert.alias || 'N/A'}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Serial Number:</span>
                            <span class="detail-value">${cert.serial_number || 'N/A'}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Crypto ID:</span>
                            <span class="detail-value">${cert.crypto_id || 'N/A'}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">URI:</span>
                            <span class="detail-value">${cert.uri || 'N/A'}</span>
                        </div>
                    </div>
                </div>
                
                <div class="detail-section">
                    <h4>Subject & Issuer</h4>
                    <div class="detail-grid">
                        <div class="detail-item">
                            <span class="detail-label">Subject:</span>
                            <span class="detail-value">${cert.subject || 'N/A'}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Subject CN:</span>
                            <span class="detail-value">${cert.subject_cn || 'N/A'}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Issuer:</span>
                            <span class="detail-value">${cert.issuer || 'N/A'}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Issuer CN:</span>
                            <span class="detail-value">${cert.issuer_cn || 'N/A'}</span>
                        </div>
                    </div>
                </div>
                
                <div class="detail-section">
                    <h4>Validity</h4>
                    <div class="detail-grid">
                        <div class="detail-item">
                            <span class="detail-label">Valid From:</span>
                            <span class="detail-value">${formatDateTime(cert.valid_from)}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Valid To:</span>
                            <span class="detail-value">${formatDateTime(cert.valid_to)}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Status:</span>
                            <span class="detail-value">${getCertificateStatus(cert).text}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Days Until Expiry:</span>
                            <span class="detail-value">${cert.days_until_expiry !== null ? cert.days_until_expiry : 'N/A'}</span>
                        </div>
                    </div>
                </div>
                
                <div class="detail-section">
                    <h4>Cryptographic Details</h4>
                    <div class="detail-grid">
                        <div class="detail-item">
                            <span class="detail-label">Public Key Algorithm:</span>
                            <span class="detail-value">${cert.public_key_algorithm || 'N/A'}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Signature Algorithm:</span>
                            <span class="detail-value">${cert.signature_algorithm || 'N/A'}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Key Size:</span>
                            <span class="detail-value">${cert.key_size || 'N/A'}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Version:</span>
                            <span class="detail-value">${cert.version || 'N/A'}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Fingerprint (SHA256):</span>
                            <span class="detail-value" style="word-break: break-all;">${truncate(cert.fingerprint_sha256 || 'N/A', 40)}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">CA Certificate:</span>
                            <span class="detail-value">${cert.is_ca_certificate ? 'Yes' : 'No'}</span>
                        </div>
                    </div>
                </div>
                
                ${cert.pqc_readiness_flag || cert.total_violation || cert.exploitability_score ? `
                <div class="detail-section">
                    <h4>Security & Compliance</h4>
                    <div class="detail-grid">
                        ${cert.pqc_readiness_flag ? `
                        <div class="detail-item">
                            <span class="detail-label">PQC Readiness:</span>
                            <span class="detail-value badge ${cert.pqc_readiness_flag === 'PQC_SAFE' ? 'badge-success' : 'badge-warning'}">${cert.pqc_readiness_flag}</span>
                        </div>
                        ` : ''}
                        ${cert.total_violation !== null && cert.total_violation !== undefined ? `
                        <div class="detail-item">
                            <span class="detail-label">Total Violations:</span>
                            <span class="detail-value">${cert.total_violation}</span>
                        </div>
                        ` : ''}
                        ${cert.total_pqc_violation !== null && cert.total_pqc_violation !== undefined ? `
                        <div class="detail-item">
                            <span class="detail-label">PQC Violations:</span>
                            <span class="detail-value">${cert.total_pqc_violation}</span>
                        </div>
                        ` : ''}
                        ${cert.exploitability_score !== null && cert.exploitability_score !== undefined ? `
                        <div class="detail-item">
                            <span class="detail-label">Exploitability Score:</span>
                            <span class="detail-value">${cert.exploitability_score.toFixed(2)}</span>
                        </div>
                        ` : ''}
                        ${cert.certificate_status ? `
                        <div class="detail-item">
                            <span class="detail-label">Certificate Status:</span>
                            <span class="detail-value">${cert.certificate_status}</span>
                        </div>
                        ` : ''}
                        ${cert.object_status ? `
                        <div class="detail-item">
                            <span class="detail-label">Object Status:</span>
                            <span class="detail-value">${cert.object_status}</span>
                        </div>
                        ` : ''}
                    </div>
                </div>
                ` : ''}
                
                ${cert.first_seen || cert.last_seen || cert.auto_renewal_status ? `
                <div class="detail-section">
                    <h4>Tracking & Management</h4>
                    <div class="detail-grid">
                        ${cert.first_seen ? `
                        <div class="detail-item">
                            <span class="detail-label">First Seen:</span>
                            <span class="detail-value">${formatDateTime(cert.first_seen)}</span>
                        </div>
                        ` : ''}
                        ${cert.last_seen ? `
                        <div class="detail-item">
                            <span class="detail-label">Last Seen:</span>
                            <span class="detail-value">${formatDateTime(cert.last_seen)}</span>
                        </div>
                        ` : ''}
                        ${cert.auto_renewal_status ? `
                        <div class="detail-item">
                            <span class="detail-label">Auto Renewal:</span>
                            <span class="detail-value">${cert.auto_renewal_status}</span>
                        </div>
                        ` : ''}
                        ${cert.is_revoked ? `
                        <div class="detail-item">
                            <span class="detail-label">Revoked:</span>
                            <span class="detail-value badge badge-danger">Yes</span>
                        </div>
                        ` : ''}
                    </div>
                </div>
                ` : ''}
            </div>
        `;
        
        modal.style.display = 'flex';
        
    } catch (error) {
        console.error('Error loading certificate details:', error);
        showToast(error.message || 'Failed to load certificate details', 'error');
    }
}

// Close certificate details modal
function closeCertDetailsModal() {
    document.getElementById('certDetailsModal').style.display = 'none';
}

// Delete single certificate
async function deleteSingleCertificate(certificateId) {
    if (!confirmAction('Are you sure you want to delete this certificate?')) {
        return;
    }
    
    try {
        await api.deleteCertificates({ certificate_ids: [certificateId] });
        showToast('Certificate deleted successfully!', 'success');
        
        // Reload certificates
        await loadCertificatesList();
        await loadCertificateStats();
        
    } catch (error) {
        console.error('Error deleting certificate:', error);
        showToast(error.message || 'Failed to delete certificate', 'error');
    }
}

// Close modals when clicking outside
window.addEventListener('click', (event) => {
    const uploadModal = document.getElementById('uploadCertModal');
    const detailsModal = document.getElementById('certDetailsModal');
    
    if (event.target === uploadModal) {
        closeUploadCertModal();
    }
    if (event.target === detailsModal) {
        closeCertDetailsModal();
    }
});

// Made with Bob