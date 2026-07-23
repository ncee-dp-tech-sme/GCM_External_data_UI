// 2026-06-02T01:41:00Z - Created IT asset management functions for GCM Web UI
// 2026-07-25T00:00:00Z - Expanded viewAssetDetails() to show all GCM fields: asset_id,
//   discovery_sources, contains_classified_data, is_encrypted, total_violation,
//   total_pqc_violation, pqc_readiness_flag, exploitability_score, is_exception.

/**
 * IT Asset Management Functions
 */

// Global state for assets
let currentAssets = [];
let currentAssetPage = 1;
let totalAssetPages = 1;
let currentAssetFilters = {};

// Load assets page
async function loadAssets() {
    console.log('loadAssets() called - initializing assets page');
    try {
        // Load statistics
        console.log('Loading asset stats...');
        await loadAssetStats();
        
        // Load assets list
        console.log('Loading assets list...');
        await loadAssetsList();
        
        // Setup event listeners
        console.log('Setting up event listeners...');
        setupAssetEventListeners();
        
        console.log('Assets page loaded successfully');
    } catch (error) {
        console.error('Error loading assets:', error);
        showToast(error.message || 'Failed to load assets', 'error');
    }
}

// Setup event listeners for asset page
function setupAssetEventListeners() {
    // Search input
    const searchInput = document.getElementById('assetSearch');
    if (searchInput && !searchInput.dataset.listenerAdded) {
        searchInput.addEventListener('input', debounceAsset(() => {
            currentAssetPage = 1;
            loadAssetsList();
        }, 500));
        searchInput.dataset.listenerAdded = 'true';
    }
    
    // Filter selects
    const typeFilter = document.getElementById('assetTypeFilter');
    const envFilter = document.getElementById('assetEnvFilter');
    
    if (typeFilter && !typeFilter.dataset.listenerAdded) {
        typeFilter.addEventListener('change', () => {
            currentAssetPage = 1;
            loadAssetsList();
        });
        typeFilter.dataset.listenerAdded = 'true';
    }
    
    if (envFilter && !envFilter.dataset.listenerAdded) {
        envFilter.addEventListener('change', () => {
            currentAssetPage = 1;
            loadAssetsList();
        });
        envFilter.dataset.listenerAdded = 'true';
    }
    
    // Pagination buttons
    const prevBtn = document.getElementById('assetPrevPage');
    const nextBtn = document.getElementById('assetNextPage');
    
    if (prevBtn && !prevBtn.dataset.listenerAdded) {
        prevBtn.addEventListener('click', () => {
            if (currentAssetPage > 1) {
                currentAssetPage--;
                loadAssetsList();
            }
        });
        prevBtn.dataset.listenerAdded = 'true';
    }
    
    if (nextBtn && !nextBtn.dataset.listenerAdded) {
        nextBtn.addEventListener('click', () => {
            if (currentAssetPage < totalAssetPages) {
                currentAssetPage++;
                loadAssetsList();
            }
        });
        nextBtn.dataset.listenerAdded = 'true';
    }
    
    // Create asset form
    const createForm = document.getElementById('createAssetForm');
    if (createForm && !createForm.dataset.listenerAdded) {
        createForm.addEventListener('submit', handleAssetCreate);
        createForm.dataset.listenerAdded = 'true';
    }
}

// Debounce helper for assets
function debounceAsset(func, wait) {
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

// Load asset statistics
async function loadAssetStats() {
    try {
        const stats = await api.getAssetStats();
        
        // Update stat cards
        document.getElementById('totalAssets').textContent = stats.total_assets || 0;
        document.getElementById('assetTypes').textContent = Object.keys(stats.by_type || {}).length || 0;
        document.getElementById('internetFacingAssets').textContent = stats.internet_facing_count || 0;
        document.getElementById('missionCriticalAssets').textContent = stats.mission_critical_count || 0;
        
    } catch (error) {
        console.error('Error loading asset stats:', error);
        // Set default values on error
        document.getElementById('totalAssets').textContent = '0';
        document.getElementById('assetTypes').textContent = '0';
        document.getElementById('internetFacingAssets').textContent = '0';
        document.getElementById('missionCriticalAssets').textContent = '0';
    }
}

// Load assets list
async function loadAssetsList() {
    console.log('loadAssetsList() called with page:', currentAssetPage);
    try {
        const searchTerm = document.getElementById('assetSearch')?.value || '';
        const assetType = document.getElementById('assetTypeFilter')?.value || '';
        const environment = document.getElementById('assetEnvFilter')?.value || '';
        
        const params = {
            page: currentAssetPage,
            page_size: 20,
            search: searchTerm,
            asset_type: assetType,
            environment: environment
        };
        
        console.log('Fetching assets with params:', params);
        const response = await api.listAssets(params);
        console.log('API response:', response);
        
        currentAssets = response.assets || [];
        totalAssetPages = response.total_pages || 1;
        
        console.log(`Received ${currentAssets.length} assets out of ${response.total} total`);
        
        renderAssetsList(currentAssets);
        updateAssetPagination();
        
    } catch (error) {
        console.error('Error loading assets list:', error);
        showToast(error.message || 'Failed to load assets', 'error');
        renderAssetsList([]);
    }
}

// Render assets list
function renderAssetsList(assets) {
    const tbody = document.getElementById('assetsTableBody');
    if (!tbody) return;
    
    if (assets.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="text-center">No assets found</td>
            </tr>
        `;
        return;
    }
    
    tbody.innerHTML = assets.map(asset => `
        <tr>
            <td>${escapeHtml(asset.uri || '')}</td>
            <td>${escapeHtml(asset.hostname || '')}</td>
            <td>${escapeHtml(asset.ip || '')}</td>
            <td>${asset.port || ''}</td>
            <td><span class="badge badge-info">${escapeHtml(asset.asset_type || 'Unknown')}</span></td>
            <td><span class="badge badge-secondary">${escapeHtml(asset.environment || 'N/A')}</span></td>
            <td>
                <button class="btn btn-sm btn-primary" onclick="viewAssetDetails(${asset.id})">View</button>
                <button class="btn btn-sm btn-danger" onclick="deleteAsset(${asset.id})">Delete</button>
            </td>
        </tr>
    `).join('');
}

// Update pagination controls
function updateAssetPagination() {
    const pageInfo = document.getElementById('assetPageInfo');
    const prevBtn = document.getElementById('assetPrevPage');
    const nextBtn = document.getElementById('assetNextPage');
    
    if (pageInfo) {
        pageInfo.textContent = `Page ${currentAssetPage} of ${totalAssetPages}`;
    }
    
    if (prevBtn) {
        prevBtn.disabled = currentAssetPage <= 1;
    }
    
    if (nextBtn) {
        nextBtn.disabled = currentAssetPage >= totalAssetPages;
    }
}

// Sync assets from GCM
async function syncAssets() {
    const syncBtn = document.getElementById('syncAssetsBtn');
    if (syncBtn) {
        syncBtn.disabled = true;
        syncBtn.textContent = 'Syncing...';
    }
    
    try {
        const assetType = document.getElementById('syncAssetType')?.value || 'all';
        const result = await api.syncAssets({ asset_type: assetType, page_size: 100 });
        
        showToast(
            `Synced ${result.synced_count} assets (${result.created_count} new, ${result.updated_count} updated)`,
            'success'
        );
        
        if (result.error_count > 0) {
            console.warn('Sync errors:', result.errors);
            showToast(`Warning: ${result.error_count} errors occurred during sync`, 'warning');
        }
        
        // Reset to page 1 and reload stats and list
        currentAssetPage = 1;
        await loadAssetStats();
        await loadAssetsList();
        
    } catch (error) {
        console.error('Error syncing assets:', error);
        showToast(error.message || 'Failed to sync assets', 'error');
    } finally {
        if (syncBtn) {
            syncBtn.disabled = false;
            syncBtn.textContent = 'Sync from GCM';
        }
    }
}

// View asset details
async function viewAssetDetails(assetId) {
    try {
        const asset = await api.getAsset(assetId);
        
        // Populate modal with asset details
        const modalBody = document.getElementById('assetDetailsBody');
        if (!modalBody) return;
        
        modalBody.innerHTML = `
            <div class="asset-details">
                <h5>Basic Information</h5>
                <div class="detail-grid">
                    <div class="detail-item">
                        <strong>URI:</strong>
                        <span>${escapeHtml(asset.uri || '')}</span>
                    </div>
                    <div class="detail-item">
                        <strong>Hostname:</strong>
                        <span>${escapeHtml(asset.hostname || 'N/A')}</span>
                    </div>
                    <div class="detail-item">
                        <strong>IP Address:</strong>
                        <span>${escapeHtml(asset.ip || 'N/A')}</span>
                    </div>
                    <div class="detail-item">
                        <strong>Port:</strong>
                        <span>${asset.port !== null && asset.port !== undefined ? asset.port : 'N/A'}</span>
                    </div>
                    <div class="detail-item">
                        <strong>Protocol:</strong>
                        <span>${escapeHtml(asset.protocol || 'N/A')}</span>
                    </div>
                    ${asset.protocol_version && asset.protocol_version.length > 0 ? `
                    <div class="detail-item">
                        <strong>Protocol Versions:</strong>
                        <span>${asset.protocol_version.map(v => escapeHtml(v)).join(', ')}</span>
                    </div>
                    ` : ''}
                    <div class="detail-item">
                        <strong>Asset Type:</strong>
                        <span class="badge badge-info">${escapeHtml(asset.asset_type || 'Unknown')}</span>
                    </div>
                    ${asset.asset_sub_type ? `
                    <div class="detail-item">
                        <strong>Sub Type:</strong>
                        <span>${escapeHtml(asset.asset_sub_type)}</span>
                    </div>
                    ` : ''}
                    ${asset.asset_id ? `
                    <div class="detail-item">
                        <strong>GCM Asset ID:</strong>
                        <span style="font-family: monospace; font-size: 0.85em;">${escapeHtml(asset.asset_id)}</span>
                    </div>
                    ` : ''}
                </div>

                ${asset.servicename || asset.databasename || asset.databasetype || asset.version || asset.application_id || asset.patch ? `
                <h5 class="mt-4">Service / Application / Database</h5>
                <div class="detail-grid">
                    ${asset.servicename ? `
                    <div class="detail-item">
                        <strong>Service Name:</strong>
                        <span>${escapeHtml(asset.servicename)}</span>
                    </div>
                    ` : ''}
                    ${asset.databasename ? `
                    <div class="detail-item">
                        <strong>Database Name:</strong>
                        <span>${escapeHtml(asset.databasename)}</span>
                    </div>
                    ` : ''}
                    ${asset.databasetype ? `
                    <div class="detail-item">
                        <strong>Database Type:</strong>
                        <span>${escapeHtml(asset.databasetype)}</span>
                    </div>
                    ` : ''}
                    ${asset.version ? `
                    <div class="detail-item">
                        <strong>Version:</strong>
                        <span>${escapeHtml(asset.version)}</span>
                    </div>
                    ` : ''}
                    ${asset.application_id ? `
                    <div class="detail-item">
                        <strong>Application ID:</strong>
                        <span>${escapeHtml(asset.application_id)}</span>
                    </div>
                    ` : ''}
                    ${asset.patch ? `
                    <div class="detail-item">
                        <strong>Patch Level:</strong>
                        <span>${escapeHtml(asset.patch)}</span>
                    </div>
                    ` : ''}
                </div>
                ` : ''}
                
                <h5 class="mt-4">Organizational</h5>
                <div class="detail-grid">
                    ${asset.owner ? `
                    <div class="detail-item">
                        <strong>Owner:</strong>
                        <span>${escapeHtml(asset.owner)}</span>
                    </div>
                    ` : ''}
                    ${asset.environment ? `
                    <div class="detail-item">
                        <strong>Environment:</strong>
                        <span class="badge badge-secondary">${escapeHtml(asset.environment)}</span>
                    </div>
                    ` : ''}
                    ${asset.location ? `
                    <div class="detail-item">
                        <strong>Location:</strong>
                        <span>${escapeHtml(asset.location)}</span>
                    </div>
                    ` : ''}
                    ${asset.network ? `
                    <div class="detail-item">
                        <strong>Network:</strong>
                        <span>${escapeHtml(asset.network)}</span>
                    </div>
                    ` : ''}
                    ${asset.tech_contacts && asset.tech_contacts.length > 0 ? `
                    <div class="detail-item">
                        <strong>Tech Contacts:</strong>
                        <span>${asset.tech_contacts.map(c => escapeHtml(c)).join(', ')}</span>
                    </div>
                    ` : ''}
                    ${asset.discovery_sources && asset.discovery_sources.length > 0 ? `
                    <div class="detail-item">
                        <strong>Discovery Sources:</strong>
                        <span>${asset.discovery_sources.map(s => escapeHtml(s)).join(', ')}</span>
                    </div>
                    ` : ''}
                </div>
                
                <h5 class="mt-4">Security & Compliance</h5>
                <div class="detail-grid">
                    ${asset.mission_criticality !== null && asset.mission_criticality !== undefined ? `
                    <div class="detail-item">
                        <strong>Mission Criticality:</strong>
                        <span class="badge ${asset.mission_criticality >= 7 ? 'badge-danger' : 'badge-warning'}">${asset.mission_criticality}</span>
                    </div>
                    ` : ''}
                    ${asset.internet_facing ? `
                    <div class="detail-item">
                        <strong>Internet Facing:</strong>
                        <span class="badge ${asset.internet_facing === 'TRUE' ? 'badge-warning' : 'badge-success'}">${asset.internet_facing}</span>
                    </div>
                    ` : ''}
                    ${asset.contains_classified_data ? `
                    <div class="detail-item">
                        <strong>Contains Classified Data:</strong>
                        <span class="badge ${asset.contains_classified_data === 'TRUE' ? 'badge-danger' : 'badge-success'}">${asset.contains_classified_data}</span>
                    </div>
                    ` : ''}
                    ${asset.is_encrypted ? `
                    <div class="detail-item">
                        <strong>Is Encrypted:</strong>
                        <span class="badge ${asset.is_encrypted === 'TRUE' ? 'badge-success' : 'badge-warning'}">${asset.is_encrypted}</span>
                    </div>
                    ` : ''}
                    ${asset.is_exception ? `
                    <div class="detail-item">
                        <strong>Is Exception:</strong>
                        <span class="badge ${asset.is_exception === 'TRUE' ? 'badge-warning' : 'badge-success'}">${asset.is_exception}</span>
                    </div>
                    ` : ''}
                    ${asset.pqc_readiness_flag ? `
                    <div class="detail-item">
                        <strong>PQC Readiness:</strong>
                        <span class="badge ${asset.pqc_readiness_flag === 'PQC_SAFE' ? 'badge-success' : 'badge-danger'}">${escapeHtml(asset.pqc_readiness_flag)}</span>
                    </div>
                    ` : ''}
                    ${asset.total_violation !== null && asset.total_violation !== undefined ? `
                    <div class="detail-item">
                        <strong>Total Violations:</strong>
                        <span class="badge ${asset.total_violation > 0 ? 'badge-danger' : 'badge-success'}">${asset.total_violation}</span>
                    </div>
                    ` : ''}
                    ${asset.total_pqc_violation !== null && asset.total_pqc_violation !== undefined ? `
                    <div class="detail-item">
                        <strong>PQC Violations:</strong>
                        <span class="badge ${asset.total_pqc_violation > 0 ? 'badge-danger' : 'badge-success'}">${asset.total_pqc_violation}</span>
                    </div>
                    ` : ''}
                    ${asset.exploitability_score !== null && asset.exploitability_score !== undefined ? `
                    <div class="detail-item">
                        <strong>Exploitability Score:</strong>
                        <span class="badge ${asset.exploitability_score >= 7 ? 'badge-danger' : asset.exploitability_score >= 4 ? 'badge-warning' : 'badge-success'}">${asset.exploitability_score}</span>
                    </div>
                    ` : ''}
                </div>
                
                ${asset.extensions && Object.keys(asset.extensions).length > 0 ? `
                <h5 class="mt-4">Custom Attributes</h5>
                <div class="detail-grid">
                    ${Object.entries(asset.extensions).map(([key, value]) => `
                    <div class="detail-item">
                        <strong>${escapeHtml(key)}:</strong>
                        <span>${escapeHtml(String(value))}</span>
                    </div>
                    `).join('')}
                </div>
                ` : ''}
                
                <h5 class="mt-4">Tracking</h5>
                <div class="detail-grid">
                    ${asset.first_seen ? `
                    <div class="detail-item">
                        <strong>First Seen:</strong>
                        <span>${new Date(asset.first_seen).toLocaleString()}</span>
                    </div>
                    ` : ''}
                    ${asset.last_seen ? `
                    <div class="detail-item">
                        <strong>Last Seen:</strong>
                        <span>${new Date(asset.last_seen).toLocaleString()}</span>
                    </div>
                    ` : ''}
                    ${asset.object_status ? `
                    <div class="detail-item">
                        <strong>Object Status:</strong>
                        <span>${escapeHtml(asset.object_status)}</span>
                    </div>
                    ` : ''}
                    <div class="detail-item">
                        <strong>Created:</strong>
                        <span>${new Date(asset.created_at).toLocaleString()}</span>
                    </div>
                    <div class="detail-item">
                        <strong>Updated:</strong>
                        <span>${new Date(asset.updated_at).toLocaleString()}</span>
                    </div>
                    ${asset.last_synced ? `
                    <div class="detail-item">
                        <strong>Last Synced:</strong>
                        <span>${new Date(asset.last_synced).toLocaleString()}</span>
                    </div>
                    ` : ''}
                </div>
            </div>
        `;
        
        // Show modal using vanilla JS
        const modal = document.getElementById('assetDetailsModal');
        if (modal) {
            modal.style.display = 'block';
            modal.classList.add('show');
        }
        
    } catch (error) {
        console.error('Error loading asset details:', error);
        showToast(error.message || 'Failed to load asset details', 'error');
    }
}

// Handle asset creation
async function handleAssetCreate(event) {
    event.preventDefault();
    
    const form = event.target;
    const submitBtn = form.querySelector('button[type="submit"]');
    
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Creating...';
    }
    
    try {
        const formData = new FormData(form);
        
        const assetData = {
            uri: formData.get('uri'),
            ip: formData.get('ip'),
            hostname: formData.get('hostname'),
            port: parseInt(formData.get('port')),
            asset_type: formData.get('asset_type'),
            protocol: formData.get('protocol') || null,
            asset_sub_type: formData.get('asset_sub_type') || null,
            owner: formData.get('owner') || null,
            environment: formData.get('environment') || null,
            location: formData.get('location') || null,
            network: formData.get('network') || null,
            mission_criticality: formData.get('mission_criticality') ? parseInt(formData.get('mission_criticality')) : null,
            internet_facing: formData.get('internet_facing') || null
        };
        
        // Handle tech contacts (comma-separated)
        const techContacts = formData.get('tech_contacts');
        if (techContacts) {
            assetData.tech_contacts = techContacts.split(',').map(c => c.trim()).filter(c => c);
        }
        
        await api.createAsset(assetData);
        
        showToast('Asset created successfully', 'success');
        
        // Close modal and reload list
        const modal = bootstrap.Modal.getInstance(document.getElementById('createAssetModal'));
        if (modal) modal.hide();
        
        form.reset();
        await loadAssetStats();
        await loadAssetsList();
        
    } catch (error) {
        console.error('Error creating asset:', error);
        showToast(error.message || 'Failed to create asset', 'error');
    } finally {
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Create Asset';
        }
    }
}

// Delete asset
async function deleteAsset(assetId) {
    if (!confirm('Are you sure you want to delete this asset?')) {
        return;
    }
    
    try {
        await api.deleteAssets([assetId]);
        
        showToast('Asset deleted successfully', 'success');
        
        // Reload stats and list
        await loadAssetStats();
        await loadAssetsList();
        
    } catch (error) {
        console.error('Error deleting asset:', error);
        showToast(error.message || 'Failed to delete asset', 'error');
    }
}

// Helper function to escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Made with Bob
