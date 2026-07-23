// 2026-06-01T23:15:00Z - Created API client for GCM Web UI backend communication

/**
 * API client for communicating with the FastAPI backend
 */
class APIClient {
    constructor() {
        this.baseURL = '/api/v1';
    }

    /**
     * Make an HTTP request to the API
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        };

        try {
            const response = await fetch(url, config);
            const data = await response.json();

            if (!response.ok) {
                throw {
                    status: response.status,
                    message: data.detail || 'Request failed',
                    data: data
                };
            }

            return data;
        } catch (error) {
            if (error.status) {
                throw error;
            }
            throw {
                status: 0,
                message: 'Network error or server unavailable',
                data: null
            };
        }
    }

    // Profile endpoints
    async getProfiles() {
        return this.request('/profiles/');
    }

    async getProfile(profileId) {
        return this.request(`/profiles/${profileId}`);
    }

    async createProfile(profileData) {
        return this.request('/profiles/', {
            method: 'POST',
            body: JSON.stringify(profileData)
        });
    }

    async updateProfile(profileId, profileData) {
        return this.request(`/profiles/${profileId}`, {
            method: 'PUT',
            body: JSON.stringify(profileData)
        });
    }

    async deleteProfile(profileId) {
        return this.request(`/profiles/${profileId}`, {
            method: 'DELETE'
        });
    }

    async activateProfile(profileId) {
        return this.request(`/profiles/${profileId}/activate`, {
            method: 'POST'
        });
    }

    async getActiveProfile() {
        return this.request('/profiles/active/current');
    }

    // Auth endpoints
    async login() {
        return this.request('/auth/login', {
            method: 'POST'
        });
    }

    async getToken() {
        return this.request('/auth/token');
    }

    async authorize(tenantId = null) {
        const params = tenantId ? `?tenant_id=${tenantId}` : '';
        return this.request(`/auth/authorize${params}`, {
            method: 'POST'
        });
    }

    // Certificate endpoints
    async syncCertificates(pageNumber = 1, pageSize = 100) {
        return this.request(`/certificates/sync?page_number=${pageNumber}&page_size=${pageSize}`, {
            method: 'POST'
        });
    }

    async syncAllCertificates(pageSize = 100) {
        return this.request(`/certificates/sync/all?page_size=${pageSize}`, {
            method: 'POST'
        });
    }

    async getCertificates(filters = {}) {
        const params = new URLSearchParams();
        if (filters.search) params.append('search', filters.search);
        if (filters.uri) params.append('uri', filters.uri);
        if (filters.issuer_cn) params.append('issuer_cn', filters.issuer_cn);
        if (filters.is_expired !== undefined) params.append('is_expired', filters.is_expired);
        if (filters.expiring_days) params.append('expiring_days', filters.expiring_days);
        if (filters.object_type) params.append('object_type', filters.object_type);
        if (filters.page) params.append('page', filters.page);
        if (filters.page_size) params.append('page_size', filters.page_size);
        if (filters.sort_by) params.append('sort_by', filters.sort_by);
        if (filters.sort_order) params.append('sort_order', filters.sort_order);
        
        const queryString = params.toString();
        return this.request(`/certificates/${queryString ? '?' + queryString : ''}`);
    }

    async getCertificate(certificateId) {
        return this.request(`/certificates/${certificateId}`);
    }

    async uploadCertificate(certData) {
        return this.request('/certificates/', {
            method: 'POST',
            body: JSON.stringify(certData)
        });
    }

    async deleteCertificates(deleteData) {
        return this.request('/certificates/', {
            method: 'DELETE',
            body: JSON.stringify(deleteData)
        });
    }

    async getCertificateStats() {
        return this.request('/certificates/stats/summary');
    }

    // IT Asset endpoints
    async syncAssets(data) {
        return this.request('/assets/sync', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    async listAssets(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        return this.request(`/assets/?${queryString}`);
    }

    async getAsset(assetId) {
        return this.request(`/assets/${assetId}`);
    }

    async createAsset(assetData) {
        return this.request('/assets/', {
            method: 'POST',
            body: JSON.stringify(assetData)
        });
    }

    async updateAsset(assetId, assetData) {
        return this.request(`/assets/${assetId}`, {
            method: 'PUT',
            body: JSON.stringify(assetData)
        });
    }

    async deleteAssets(assetIds) {
        return this.request('/assets/', {
            method: 'DELETE',
            body: JSON.stringify(assetIds)
        });
    }

    async getAssetStats() {
        return this.request('/assets/stats');
    }

    async getAssetTypes() {
        return this.request('/assets/types/list');
    }

    // Health check
    async healthCheck() {
        try {
            const response = await fetch('/health');
            return response.ok;
        } catch {
            return false;
        }
    }
}

// Create global API client instance
const api = new APIClient();

// Made with Bob
