// 2026-06-01T23:15:00Z - Created UI helper functions for toast notifications and page navigation

/**
 * UI Helper Functions
 */

// Toast notification system
function showToast(message, type = 'info', title = '') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    const icons = {
        success: '✅',
        error: '❌',
        warning: '⚠️',
        info: 'ℹ️'
    };
    
    const titles = {
        success: title || 'Success',
        error: title || 'Error',
        warning: title || 'Warning',
        info: title || 'Info'
    };
    
    toast.innerHTML = `
        <div class="toast-icon">${icons[type]}</div>
        <div class="toast-content">
            <div class="toast-title">${titles[type]}</div>
            <div class="toast-message">${message}</div>
        </div>
    `;
    
    container.appendChild(toast);
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        toast.style.animation = 'slideIn 0.3s ease reverse';
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}

// Page navigation
function switchToPage(pageName) {
    // Hide all pages
    document.querySelectorAll('.page').forEach(page => {
        page.classList.remove('active');
    });
    
    // Remove active class from all tabs
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Show selected page
    const page = document.getElementById(`${pageName}Page`);
    if (page) {
        page.classList.add('active');
    }
    
    // Activate corresponding tab
    const tab = document.querySelector(`[data-page="${pageName}"]`);
    if (tab) {
        tab.classList.add('active');
    }
    
    // Load page-specific data
    if (pageName === 'dashboard') {
        loadDashboard();
    } else if (pageName === 'profiles') {
        loadProfiles();
    } else if (pageName === 'certificates') {
        loadCertificates();
    } else if (pageName === 'assets') {
        loadAssets();
    } else if (pageName === 'scanner') {
        if (window.scannerModule) {
            window.scannerModule.init();
        }
    } else if (pageName === 'auth') {
        loadAuthPage();
    }
}

// Format date/time
function formatDateTime(dateString) {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleString();
}

// Truncate long strings
function truncate(str, maxLength = 50) {
    if (!str) return '';
    return str.length > maxLength ? str.substring(0, maxLength) + '...' : str;
}

// Show loading state on button
function setButtonLoading(button, loading = true) {
    if (loading) {
        button.disabled = true;
        button.dataset.originalText = button.innerHTML;
        button.innerHTML = '<span class="spinner"></span> Loading...';
    } else {
        button.disabled = false;
        button.innerHTML = button.dataset.originalText || button.innerHTML;
    }
}

// Format JSON for display
function formatJSON(obj) {
    return JSON.stringify(obj, null, 2);
}

// Display response in auth page
function displayAuthResponse(data, success = true) {
    const responseBox = document.getElementById('authResponse');
    responseBox.innerHTML = '';
    
    const pre = document.createElement('pre');
    pre.textContent = formatJSON(data);
    pre.style.color = success ? '#10b981' : '#ef4444';
    
    responseBox.appendChild(pre);
}

// Update active profile badge in header
function updateActiveProfileBadge(profileName) {
    const badge = document.getElementById('activeProfileBadge');
    if (profileName) {
        badge.textContent = `Active: ${profileName}`;
        badge.style.background = 'rgba(16, 185, 129, 0.3)';
    } else {
        badge.textContent = 'No Active Profile';
        badge.style.background = 'rgba(255, 255, 255, 0.2)';
    }
}

// Confirm dialog
function confirmAction(message) {
    return confirm(message);
}

// Create profile card HTML
function createProfileCard(profile) {
    const isActive = profile.is_active;
    const activeClass = isActive ? 'active' : '';
    const activeBadge = isActive ? '<span class="profile-badge">ACTIVE</span>' : '';
    
    return `
        <div class="profile-card ${activeClass}">
            <div class="profile-header">
                <div class="profile-title">${profile.name}</div>
                ${activeBadge}
            </div>
            ${profile.description ? `<p class="text-muted">${profile.description}</p>` : ''}
            <div class="profile-info">
                <div class="profile-info-item">
                    <span class="profile-info-label">GCM URI:</span>
                    <span class="profile-info-value">${truncate(profile.app_uri, 30)}</span>
                </div>
                <div class="profile-info-item">
                    <span class="profile-info-label">OIDC URI:</span>
                    <span class="profile-info-value">${truncate(profile.oidc_uri, 30)}</span>
                </div>
                <div class="profile-info-item">
                    <span class="profile-info-label">Realm:</span>
                    <span class="profile-info-value">${profile.realm}</span>
                </div>
                <div class="profile-info-item">
                    <span class="profile-info-label">Client ID:</span>
                    <span class="profile-info-value">${profile.client_id || 'Not set'}</span>
                </div>
                <div class="profile-info-item">
                    <span class="profile-info-label">Has Credentials:</span>
                    <span class="profile-info-value">${profile.has_username && profile.has_password ? '✅' : '❌'}</span>
                </div>
                <div class="profile-info-item">
                    <span class="profile-info-label">Created:</span>
                    <span class="profile-info-value">${formatDateTime(profile.created_at)}</span>
                </div>
            </div>
            <div class="profile-actions">
                ${!isActive ? `<button class="btn btn-success" onclick="activateProfile(${profile.id})">✅ Activate</button>` : ''}
                <button class="btn btn-primary" onclick="editProfile(${profile.id})">✏️ Edit</button>
                <button class="btn btn-danger" onclick="deleteProfile(${profile.id})" ${isActive ? 'disabled' : ''}>🗑️ Delete</button>
            </div>
        </div>
    `;
}

// Initialize chart
let profileChart = null;

function initializeChart(labels, data) {
    const ctx = document.getElementById('profileChart');
    
    if (profileChart) {
        profileChart.destroy();
    }
    
    profileChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: [
                    '#2563eb',
                    '#10b981',
                    '#f59e0b',
                    '#ef4444',
                    '#8b5cf6'
                ],
                borderWidth: 2,
                borderColor: '#ffffff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        padding: 20,
                        font: {
                            size: 14
                        }
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `${context.label}: ${context.parsed}`;
                        }
                    }
                }
            }
        }
    });
}

// Asset modal functions
function showCreateAssetModal() {
    const modal = document.getElementById('createAssetModal');
    if (modal) {
        modal.style.display = 'flex';
    }
}

function closeCreateAssetModal() {
    const modal = document.getElementById('createAssetModal');
    if (modal) {
        modal.style.display = 'none';
    }
    // Reset form
    const form = document.getElementById('createAssetForm');
    if (form) {
        form.reset();
    }
}

function closeAssetDetailsModal() {
    const modal = document.getElementById('assetDetailsModal');
    if (modal) {
        modal.style.display = 'none';
    }
}

// Made with Bob
