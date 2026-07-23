// 2026-06-01T23:16:00Z - Created main application logic for GCM Web UI
// 2026-07-23: Added auth_method and api_key support to profile form handling

/**
 * Main Application Logic
 */

// Global state
let currentProfiles = [];
let activeProfile = null;

// Initialize application
document.addEventListener('DOMContentLoaded', () => {
    initializeEventListeners();
    loadDashboard();
    checkAPIHealth();
});

// Initialize event listeners
function initializeEventListeners() {
    // Navigation tabs
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.addEventListener('click', (e) => {
            const page = e.target.dataset.page;
            switchToPage(page);
        });
    });
    
    // Profile form submission
    document.getElementById('profileForm').addEventListener('submit', handleProfileSubmit);
    
    // Refresh button
    document.getElementById('refreshBtn').addEventListener('click', () => {
        const currentPage = document.querySelector('.nav-tab.active').dataset.page;
        switchToPage(currentPage);
        showToast('Data refreshed', 'success');
    });
}

// Check API health
async function checkAPIHealth() {
    const statusElement = document.getElementById('apiStatus');
    try {
        const healthy = await api.healthCheck();
        statusElement.textContent = healthy ? 'Online' : 'Offline';
        statusElement.className = healthy ? 'stat-value text-success' : 'stat-value text-danger';
    } catch (error) {
        statusElement.textContent = 'Offline';
        statusElement.className = 'stat-value text-danger';
    }
}

// Load dashboard
async function loadDashboard() {
    try {
        // Load profiles data
        const profilesData = await api.getProfiles();
        currentProfiles = profilesData.profiles;
        activeProfile = currentProfiles.find(p => p.is_active);
        
        // Update stats
        document.getElementById('totalProfiles').textContent = profilesData.total;
        document.getElementById('activeProfileName').textContent = activeProfile ? activeProfile.name : 'None';
        
        // Update header badge
        updateActiveProfileBadge(activeProfile?.name);
        
        // Update auth status
        if (activeProfile) {
            document.getElementById('authStatus').textContent = 'Ready';
            document.getElementById('authStatus').className = 'stat-value text-success';
        } else {
            document.getElementById('authStatus').textContent = 'No Profile';
            document.getElementById('authStatus').className = 'stat-value text-warning';
        }
        
        // Create chart data
        if (currentProfiles.length > 0) {
            const chartLabels = currentProfiles.map(p => p.name);
            const chartData = currentProfiles.map(() => 1); // Equal distribution for now
            initializeChart(chartLabels, chartData);
        } else {
            initializeChart(['No Profiles'], [1]);
        }
        
    } catch (error) {
        console.error('Error loading dashboard:', error);
        showToast(error.message || 'Failed to load dashboard', 'error');
    }
}

// Load profiles page
async function loadProfiles() {
    try {
        const profilesData = await api.getProfiles();
        currentProfiles = profilesData.profiles;
        activeProfile = currentProfiles.find(p => p.is_active);
        
        const profilesList = document.getElementById('profilesList');
        
        if (currentProfiles.length === 0) {
            profilesList.innerHTML = '<p class="text-muted">No profiles yet. Create your first profile above.</p>';
        } else {
            profilesList.innerHTML = currentProfiles.map(profile => createProfileCard(profile)).join('');
        }
        
        // Update header badge
        updateActiveProfileBadge(activeProfile?.name);
        
    } catch (error) {
        console.error('Error loading profiles:', error);
        showToast(error.message || 'Failed to load profiles', 'error');
    }
}

// Handle profile form submission
async function handleProfileSubmit(e) {
    e.preventDefault();
    
    const submitBtn = e.target.querySelector('button[type="submit"]');
    setButtonLoading(submitBtn, true);
    
    try {
        const profileId = document.getElementById('profileId').value;
        const authMethod = document.getElementById('authMethod').value;
        const profileData = {
            name: document.getElementById('profileName').value,
            description: document.getElementById('profileDescription').value || null,
            app_uri: document.getElementById('appUri').value,
            oidc_uri: authMethod === 'api_key' ? null : document.getElementById('oidcUri').value,
            realm: document.getElementById('realm').value,
            auth_method: authMethod,
            client_id: document.getElementById('clientId').value || null,
            client_secret: document.getElementById('clientSecret').value || null,
            username: document.getElementById('username').value || null,
            password: document.getElementById('password').value || null,
            api_key: document.getElementById('apiKey').value || null,
            tenant_id: document.getElementById('tenantId').value || null,
            timeout: parseFloat(document.getElementById('timeout').value),
            user_agent: document.getElementById('userAgent').value,
            insecure: document.getElementById('insecure').checked
        };
        
        if (profileId) {
            // Update existing profile
            await api.updateProfile(profileId, profileData);
            showToast('Profile updated successfully', 'success');
        } else {
            // Create new profile
            await api.createProfile(profileData);
            showToast('Profile created successfully', 'success');
        }
        
        resetProfileForm();
        loadProfiles();
        
    } catch (error) {
        console.error('Error saving profile:', error);
        showToast(error.message || 'Failed to save profile', 'error');
    } finally {
        setButtonLoading(submitBtn, false);
    }
}

// Toggle visibility of OIDC vs API key fields based on selected auth method
function toggleAuthFields() {
    const method = document.getElementById('authMethod').value;
    const oidcFields = document.getElementById('oidcFields');
    const apiKeyFields = document.getElementById('apiKeyFields');
    const oidcUri = document.getElementById('oidcUri');

    if (method === 'api_key') {
        oidcFields.style.display = 'none';
        apiKeyFields.style.display = '';
        oidcUri.removeAttribute('required');
    } else {
        oidcFields.style.display = '';
        apiKeyFields.style.display = 'none';
        oidcUri.setAttribute('required', 'required');
    }
}

// Reset profile form
function resetProfileForm() {
    document.getElementById('profileForm').reset();
    document.getElementById('profileId').value = '';
    document.getElementById('formTitle').textContent = 'Create New Profile';
    document.getElementById('authMethod').value = 'oidc';
    document.getElementById('realm').value = 'gcmrealm';
    document.getElementById('timeout').value = '30';
    document.getElementById('userAgent').value = 'gcm-webui/1.0';
    toggleAuthFields();
}

// Edit profile
async function editProfile(profileId) {
    try {
        const profile = await api.getProfile(profileId);
        
        // Populate form
        document.getElementById('profileId').value = profile.id;
        document.getElementById('profileName').value = profile.name;
        document.getElementById('profileDescription').value = profile.description || '';
        document.getElementById('appUri').value = profile.app_uri;
        document.getElementById('oidcUri').value = profile.oidc_uri || '';
        document.getElementById('realm').value = profile.realm;
        document.getElementById('authMethod').value = profile.auth_method || 'oidc';
        document.getElementById('clientId').value = profile.client_id || '';
        document.getElementById('tenantId').value = profile.tenant_id || '';
        document.getElementById('timeout').value = profile.timeout;
        document.getElementById('userAgent').value = profile.user_agent;
        document.getElementById('insecure').checked = profile.insecure;
        
        // Clear sensitive fields (they won't be returned from API)
        document.getElementById('clientSecret').value = '';
        document.getElementById('username').value = '';
        document.getElementById('password').value = '';
        document.getElementById('apiKey').value = '';
        
        document.getElementById('formTitle').textContent = 'Edit Profile';
        toggleAuthFields();
        
        // Scroll to form
        document.querySelector('.form-section').scrollIntoView({ behavior: 'smooth' });
        
    } catch (error) {
        console.error('Error loading profile:', error);
        showToast(error.message || 'Failed to load profile', 'error');
    }
}

// Delete profile
async function deleteProfile(profileId) {
    const profile = currentProfiles.find(p => p.id === profileId);
    
    if (!confirmAction(`Are you sure you want to delete the profile "${profile.name}"?`)) {
        return;
    }
    
    try {
        await api.deleteProfile(profileId);
        showToast('Profile deleted successfully', 'success');
        loadProfiles();
    } catch (error) {
        console.error('Error deleting profile:', error);
        showToast(error.message || 'Failed to delete profile', 'error');
    }
}

// Activate profile
async function activateProfile(profileId) {
    try {
        await api.activateProfile(profileId);
        showToast('Profile activated successfully', 'success');
        loadProfiles();
        loadDashboard();
    } catch (error) {
        console.error('Error activating profile:', error);
        showToast(error.message || 'Failed to activate profile', 'error');
    }
}

// Load auth page
async function loadAuthPage() {
    try {
        // Get active profile
        const profile = await api.getActiveProfile();
        activeProfile = profile;
        
        document.getElementById('authActiveProfile').textContent = profile.name;
        document.getElementById('authActiveProfile').className = 'status-value text-success';
        
        // Update header badge
        updateActiveProfileBadge(profile.name);
        
    } catch (error) {
        console.error('Error loading auth page:', error);
        document.getElementById('authActiveProfile').textContent = 'None';
        document.getElementById('authActiveProfile').className = 'status-value text-danger';
        
        if (error.status === 404) {
            showToast('No active profile. Please create and activate a profile first.', 'warning');
        }
    }
}

// Perform login and automatically authorize
async function performLogin() {
    const btn = event.target;
    setButtonLoading(btn, true);
    
    try {
        // Step 1: Login to get access token
        const loginResult = await api.login();
        
        document.getElementById('authTokenStatus').textContent = 'Authenticated';
        document.getElementById('authTokenStatus').className = 'status-value text-success';
        
        showToast('Login successful, authorizing to GCM...', 'success');
        
        // Step 2: Automatically authorize to GCM
        const authResult = await api.authorize();
        
        if (authResult.authorized) {
            document.getElementById('gcmAuthStatus').textContent = 'Authorized';
            document.getElementById('gcmAuthStatus').className = 'status-value text-success';
            
            displayAuthResponse({
                message: 'Login and authorization successful',
                step_1_login: {
                    access_token: loginResult.access_token.substring(0, 50) + '...',
                    expires_in: loginResult.expires_in,
                    has_refresh_token: !!loginResult.refresh_token
                },
                step_2_authorization: {
                    status_code: authResult.status_code,
                    authorized: authResult.authorized,
                    payload: authResult.payload
                }
            }, true);
            
            showToast('Successfully logged in and authorized to GCM! ✅', 'success');
        } else {
            throw new Error('GCM authorization failed');
        }
        
    } catch (error) {
        console.error('Error during login/authorization:', error);
        document.getElementById('authTokenStatus').textContent = 'Failed';
        document.getElementById('authTokenStatus').className = 'status-value text-danger';
        document.getElementById('gcmAuthStatus').textContent = 'Not Authorized';
        document.getElementById('gcmAuthStatus').className = 'status-value text-danger';
        
        displayAuthResponse({
            error: error.message,
            details: error.data
        }, false);
        
        showToast(error.message || 'Login/authorization failed', 'error');
    } finally {
        setButtonLoading(btn, false);
    }
}

// Get token
async function getToken() {
    const btn = event.target;
    setButtonLoading(btn, true);
    
    try {
        const result = await api.getToken();
        
        document.getElementById('authTokenStatus').textContent = 'Valid Token';
        document.getElementById('authTokenStatus').className = 'status-value text-success';
        
        displayAuthResponse({
            message: 'Token retrieved successfully',
            access_token: result.access_token.substring(0, 50) + '...',
            token_length: result.access_token.length
        }, true);
        
        showToast('Token retrieved successfully', 'success');
        
    } catch (error) {
        console.error('Error getting token:', error);
        document.getElementById('authTokenStatus').textContent = 'No Token';
        document.getElementById('authTokenStatus').className = 'status-value text-danger';
        
        displayAuthResponse({
            error: error.message,
            details: error.data
        }, false);
        
        showToast(error.message || 'Failed to get token', 'error');
    } finally {
        setButtonLoading(btn, false);
    }
}

// Authorize to GCM
async function authorizeGCM() {
    const btn = event.target;
    setButtonLoading(btn, true);
    
    try {
        const result = await api.authorize();
        
        if (result.authorized) {
            document.getElementById('gcmAuthStatus').textContent = 'Authorized';
            document.getElementById('gcmAuthStatus').className = 'status-value text-success';
            
            displayAuthResponse({
                message: 'GCM authorization successful',
                status_code: result.status_code,
                authorized: result.authorized,
                payload: result.payload
            }, true);
            
            showToast('GCM authorization successful', 'success');
        } else {
            throw new Error('Authorization failed');
        }
        
    } catch (error) {
        console.error('Error authorizing to GCM:', error);
        document.getElementById('gcmAuthStatus').textContent = 'Not Authorized';
        document.getElementById('gcmAuthStatus').className = 'status-value text-danger';
        
        displayAuthResponse({
            error: error.message,
            details: error.data
        }, false);
        
        showToast(error.message || 'GCM authorization failed', 'error');
    } finally {
        setButtonLoading(btn, false);
    }
}

// Test connection
async function testConnection() {
    if (!activeProfile) {
        showToast('No active profile. Please activate a profile first.', 'warning');
        return;
    }
    
    try {
        showToast('Testing connection...', 'info');
        
        // Try to get token
        await api.getToken();
        
        // Try to authorize
        const result = await api.authorize();
        
        if (result.authorized) {
            showToast('Connection test successful! ✅', 'success');
        } else {
            showToast('Connection test failed', 'error');
        }
        
    } catch (error) {
        console.error('Connection test failed:', error);
        showToast(error.message || 'Connection test failed', 'error');
    }
}

// Made with Bob
