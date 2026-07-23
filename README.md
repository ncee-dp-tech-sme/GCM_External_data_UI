# GCM Web UI - Distribution Package

**Version:** 1.3.1
**Last Updated:** 2026-07-28

## Overview

This is a distributable package of the GCM (Guardium Cryptography Manager) Web UI application. It provides a complete web-based interface for managing GCM operations including certificate management, IT asset management, profile management, authentication, and disconnected SSL certificate scanning. User management features are planned for a future release.

## What's Included

This package contains:

- **Backend Application**: FastAPI-based REST API server
- **Frontend Application**: Modern web interface with responsive design
- **GCM Integration Modules**: Python modules for GCM API operations
- **Configuration Templates**: Sample configuration files
- **Setup Scripts**: Automated installation and setup tools

## Features

### Currently Available

- 📊 **Dashboard**: Visual overview with charts and statistics
- 👤 **Profile Management**: Create and manage GCM connection profiles
- 🔑 **Authentication**: Secure login with GCM — supports **OIDC (username/password)** and **API key** authentication methods
- 📜 **Certificate Management**: Upload, sync, view, and manage certificates with full field coverage
- 🖥️ **IT Asset Management**: Create, sync, and manage IT assets — all GCM fields captured including security metrics, protocol versions, and service details
- 📈 **Visual Analytics**: Real-time charts and statistics
- 🔒 **Security**: Encrypted credential storage with Fernet encryption
- 🔍 **Disconnected Scanner**: Three-step workflow — generate target lists, scan hosts for SSL certificates, and bulk-import results into GCM

### Coming Soon

- 👥 **User Management**: Keycloak user creation and management *(Future Addition)*

## Prerequisites

Before installing, ensure you have:

- **Python 3.9 or higher** installed
- **pip** package manager
- **Virtual environment** support (venv)
- **Network access** to your GCM instance
- **Modern web browser** (Chrome, Firefox, Safari, or Edge)

### System Requirements

- **Operating System**: Linux, macOS, or Windows
- **RAM**: Minimum 2GB available
- **Disk Space**: 500MB for application and dependencies
- **Network**: HTTPS connectivity to GCM instance

## Installation

### Step 1: Extract the Package

Extract this distribution package to your desired location:

```bash
cd /path/to/installation
unzip gcm-webui-dist.zip
cd dist
```

### Step 2: Backend Setup

Navigate to the backend directory and run the setup script:

```bash
cd backend
chmod +x setup.sh
./setup.sh
```

The setup script will:
1. Create a Python virtual environment
2. Install all required dependencies
3. Generate encryption keys
4. Create the `.env` configuration file
5. Initialize the database

**Manual Setup (if setup.sh fails):**

```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # On Linux/macOS
# OR
.venv\Scripts\activate     # On Windows

# Install dependencies
pip install -r requirements.txt

# Generate encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Create .env file
cp .env.example .env
# Edit .env and add the generated key to SECRET_KEY
```

### Step 3: Configure GCM Connection

Edit the `config.toml` file in the root directory:

```bash
cd ..
cp config.toml.template config.toml
nano config.toml  # or use your preferred editor
```

Update the following settings:

**For OIDC authentication (default):**

```toml
[connection]
app_uri = "https://your-gcm-host:31443"
oidc_uri = "https://your-gcm-host:30443"
realm = "gcmrealm"

[authentication]
auth_method = "oidc"
client_id = ""       # auto-selected if empty
client_secret = ""
# username = ""
# password = ""

[http]
timeout = 30.0
insecure = false  # Set to true only for development/test
```

**For API key authentication:**

```toml
[connection]
app_uri = "https://your-gcm-host:31443"
# oidc_uri is not required for api_key authentication

[authentication]
auth_method = "api_key"
# api_key = ""  # set via GCM_API_KEY env var (recommended)

[http]
timeout = 30.0
insecure = false
```

### Step 4: Configure Backend Environment

Edit the `backend/.env` file:

```bash
cd backend
nano .env
```

Ensure these variables are set:

```env
SECRET_KEY=your-generated-fernet-key
DATABASE_URL=sqlite:///./gcm_webui.db
CORS_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
```

## Running the Application

### Start the Backend Server

From the `backend` directory:

```bash
# Activate virtual environment
source .venv/bin/activate  # On Linux/macOS
# OR
.venv\Scripts\activate     # On Windows

# Start the server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The server will start on `http://localhost:8000`

### Access the Web Interface

Open your web browser and navigate to:

```
http://localhost:8000
```

You should see the GCM Web UI dashboard.

### API Documentation

Interactive API documentation is available at:

- **Swagger UI**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc

## Configuration

### Profile Management

Before using the application, you need to create a GCM connection profile:

1. Navigate to the **Profiles** tab
2. Fill in the profile form:
   - **Profile Name**: Unique identifier (e.g., "Production GCM")
   - **GCM Application URI**: Your GCM server URL
   - **OIDC/Keycloak URI**: Your authentication server URL
   - **Realm**: Keycloak realm (default: `gcmrealm`)
   - **Authentication Method**: Choose `oidc` (default) or `api_key` — see below
   - **Client ID**: OIDC client identifier *(OIDC only)*
   - **Client Secret**: OIDC client secret (will be encrypted) *(OIDC only)*
   - **Username**: Your GCM username (will be encrypted) *(OIDC only)*
   - **Password**: Your GCM password (will be encrypted) *(OIDC only)*
   - **API Key**: Your GCM API key (will be encrypted) *(API key only)*
3. Click **Save Profile**
4. Click **Activate** to set it as the active profile

### Authentication

The application supports two mutually exclusive authentication methods per profile. Set the `auth_method` field when creating or updating a profile.

#### OIDC Authentication (default)

Used when `auth_method = oidc`. The application performs a standard OIDC password grant flow against Keycloak and exchanges the resulting token with GCM. After activating an OIDC profile:

1. Navigate to the **Authentication** tab
2. Click **Login & Authorize**
3. The system authenticates with Keycloak and authorizes with GCM

#### API Key Authentication

Used when `auth_method = api_key`. No OIDC token exchange takes place. The API key is sent verbatim in every outgoing request using two headers:

```
Authorization: <your-api-key>
token_type: api_key
```

When an API key profile is active, the **Login & Authorize** step is not required — the key is used automatically on each request. The `/api/v1/auth/login` endpoint will return a `400` error if called with an API key profile active, since no login step is needed.

> **Security note**: API keys are encrypted at rest using Fernet encryption (same as passwords and tokens).

You're now ready to use all features!

## Usage Guide

### Certificate Management

**Sync Certificates from GCM:**
1. Go to **Certificates** tab
2. Click **Sync from GCM**
3. View synced certificates in the list

> **Sync keeps local data in step with GCM.** After every full sync, any certificate that no longer exists on the remote server is automatically removed from the local database. The sync response includes a `deleted` count alongside `synced` and `updated`.

**Upload a Certificate:**
1. Click **Upload Certificate**
2. Select certificate file (PEM or DER format)
3. Enter URI and optional alias
4. Click **Upload**

**View Certificate Details:**
- Click **View** on any certificate to see comprehensive information
- Includes validity, cryptographic details, and security metrics

### IT Asset Management

**Sync Assets from GCM:**
1. Go to **IT Assets** tab
2. Click **Sync from GCM**
3. View synced assets in the list

> **Sync keeps local data in step with GCM.** After every full sync, any asset that no longer exists on the remote server is automatically removed from the local database. The sync response includes a `deleted_count` alongside `synced_count`, `created_count`, and `updated_count`.

The sync captures all GCM asset fields using the confirmed payload:

| Section | Fields |
|---|---|
| Identity | `uri`, `ip`, `hostname`, `port`, `asset_id` |
| Protocol | `protocol`, `protocol_version` (list, e.g. `["TLSv1.3","TLSv1.2"]`) |
| Classification | `asset_type`, `asset_sub_type` |
| Service/DB | `servicename`, `databasename`, `databasetype`, `version`, `applicationID`, `patch` |
| Organisation | `owner`, `environment`, `location`, `network`, `tech_contacts`, `discovery_sources` |
| Security | `mission_criticality`, `internet_facing`, `total_violation`, `pqc_readiness_flag`, `exploitability_score`, `is_exception` |
| Timestamps | `first_seen`, `last_seen` |

**Create a New Asset:**
1. Click **Create Asset**
2. Fill in asset details (URI, hostname, type, etc.)
3. Click **Create**

**View Asset Details:**
- Click **View** on any asset to see full information
- All sections displayed: Basic Info, Service/Application/Database, Organisational, Security & Compliance, Custom Attributes, Tracking
- Protocol versions shown as comma-separated list
- PQC readiness, violation counts, and exploitability score shown with colour-coded badges

### Disconnected Scanner

The scanner page provides a guided three-step workflow for discovering and importing crypto objects (TLS certificates, SSH host keys, and TLS protocol metadata) from hosts that may not be directly reachable from GCM. Scans run as a **real-time streaming operation** — progress is shown target-by-target and can be stopped at any time.

**Step 1 — Generate Targets (Optional)**
1. Go to the **Scanner** tab.
2. Enter IP ranges (CIDR or wildcard, e.g. `192.168.1.0/24`, `10.0.0.*`), hostnames, and ports.
3. Click **Generate Targets** to produce an `Alias, URI` CSV.
4. Download the CSV or proceed directly to Step 2.

**Step 2 — Scan Targets**
1. Optionally upload a targets CSV (must have `Alias` and `URI` columns) using the **Targets CSV File** file picker. Leave it empty to reuse the CSV generated in Step 1.
2. Set the per-target **timeout** (default: 5 seconds).
3. Enable **Allow self-signed certificates** if targets use untrusted certificates.
4. Click **Run Scan**.
   - A progress bar shows the current target (`host:port`) being probed in real time.
   - Click **Stop Scan** at any time to halt after the current target finishes.
5. Results appear row-by-row as each probe completes. When the scan finishes, action buttons appear above the results table:
   - **⬇️ Download Certificates CSV** — saves the `Alias, Certdata, URI` CSV for offline use.
   - **Next: Import Certificates →** — navigates to Step 3.

**Protocol detection per target:**

| Detected service | How | What is captured |
|---|---|---|
| **TLS / HTTPS** | Full TLS handshake (strict, with automatic legacy-TLS fallback) | DER certificate, TLS version, cipher suite, subject/issuer, expiry |
| **SSH** | SSH binary protocol (RFC 4253 KEXINIT) | Server banner, host-key type (e.g. `ssh-ed25519`), advertised key algorithms |
| **Plain-text** (FTP, SMTP, POP3, IMAP, …) | TCP banner read | Service label, raw banner |

SSH is detected automatically on standard port `22` and common alternatives `2222` / `22222`, as well as any other port whose banner starts with `SSH-`.

**Security findings reported per target:**

| Finding badge | Meaning |
|---|---|
| `EXPIRED` | Certificate is past its `notAfter` date |
| `EXPIRING SOON` | Certificate expires within 30 days |
| `LEGACY TLS` | Server negotiated TLSv1.0 or TLSv1.1 |
| `WEAK CIPHER` | Cipher uses RC4, DES, 3DES, CBC mode, static RSA key exchange, or similar |
| `WEAK KEY` | RSA/DSA key < 2048 bits or EC key < 224 bits |
| `SELF-SIGNED` | Certificate subject equals issuer |
| `SHA-1 CERT` | Certificate is signed with SHA-1 |
| `WEAK SSH KEY` | Server's preferred host key is `ssh-rsa` (SHA-1 based, deprecated) |
| `LEGACY SSH KEX` | Server advertises `ssh-rsa` but no `rsa-sha2-*` variants |

**Step 3 — Import Scan Results into GCM**

When a scan was run in Step 2, a summary shows the number of each object type ready to import. Click **📤 Import All to GCM** to send all three object types to GCM in one operation:

| Object type | GCM API | What is sent |
|---|---|---|
| **Certificates** | `POST /v1/…/crypto_objects/certificate_from_file` | Base64 DER certificate, alias, IT asset URI |
| **SSH Host Keys** | `POST /v2/…/crypto_objects/keys` | Key algorithm, estimated key length, advertised algorithms (in extensions), IT asset relationship |
| **TLS Protocols** | `POST /v2/…/crypto_objects/protocols` | TLS version, cipher suite, IT asset URI |

After import, a results table shows **Imported** and **Failed** counts per object type. Expand the **GCM responses** collapsible section to see the raw GCM response body for every per-object API call — useful for diagnosing why objects accepted by GCM may not appear in the inventory (e.g. unknown IT asset URI, unsupported field value).

Alternatively, expand **Or upload a certificates CSV manually** to import only TLS certificates from a custom CSV file (useful when scanning was done offline with `convert_certs_into_csv.py`).

**CSV formats:**

| Step | Required columns | Optional columns |
|------|-----------------|-----------------|
| Targets (input to Step 2) | `Alias`, `URI` | — |
| Certificates (output of Step 2 / input to Step 3 manual upload) | `Alias`, `Certdata` | `URI (optional)` |

> **Tip:** Use [`disconnected-scanner/convert_certs_into_csv.py`](disconnected-scanner/convert_certs_into_csv.py) to convert local PEM/DER certificate files into the certificates CSV format instead of running a live scan.

**Backend API endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/scanner/generate-targets` | Expand IP/host/port inputs into a targets CSV |
| `POST` | `/api/v1/scanner/run-scan-stream` | Stream scan progress as Server-Sent Events (SSE) — used by the UI |
| `DELETE` | `/api/v1/scanner/stop-scan/{scan_id}` | Signal a running stream scan to stop after the current target |
| `POST` | `/api/v1/scanner/run-scan` | Non-streaming batch scan (kept for scripting / API compatibility) |
| `POST` | `/api/v1/scanner/validate-csv` | Validate a certificates CSV before import |
| `POST` | `/api/v1/scanner/import-csv` | Import TLS certificates from CSV into GCM |
| `POST` | `/api/v1/scanner/ingest-scan-results` | Ingest SSH host keys and TLS protocol metadata from scan results into GCM |

### Database Migrations

The application runs zero-downtime column migrations on every startup via `migrate_db()` in [`backend/app/database.py`](backend/app/database.py). New columns are added with `ALTER TABLE … ADD COLUMN` and silently skipped if they already exist. **No manual migration steps are required when upgrading.**


## Directory Structure

```
dist/
├── README.md                    # This file
├── config.toml.template         # Configuration template
├── backend/                     # Backend application
│   ├── app/                    # Application code
│   │   ├── api/               # API endpoints
│   │   ├── models/            # Database models
│   │   ├── schemas/           # Data schemas
│   │   ├── services/          # Business logic
│   │   ├── main.py            # FastAPI application
│   │   ├── config.py          # Configuration
│   │   ├── database.py        # Database setup
│   │   └── security.py        # Encryption utilities
│   ├── requirements.txt        # Python dependencies
│   ├── setup.sh               # Setup script
│   └── .env.example           # Environment template
├── frontend/                    # Web interface
│   ├── index.html             # Main page
│   ├── css/                   # Stylesheets
│   └── js/                    # JavaScript modules
├── common/                      # Shared GCM modules
│   ├── config_loader.py       # Config file support
│   ├── oidc_authz_client.py   # Authentication client
│   └── get_authz_token.py     # Token management
├── certificates/                # Certificate operations
│   ├── get_certificate_inventory.py
│   ├── post_certificate.py
│   └── delete_certificate_from_inventory.py
├── it_assets/                   # IT asset operations
│   ├── get_it_assets_by_type.py
│   ├── post_it_asset.py
│   └── delete_it_asset_from_inventory.py
├── user_management/             # User management
│   ├── create_keycloak_user.py
│   ├── register_oidc_user.py
│   └── list_users.py
└── disconnected-scanner/        # Scanner utilities
    ├── gen_target_list.py           # CLI: generate scan targets CSV
    ├── get_certificates.py          # CLI: fetch SSL certs from target list
    ├── post_certificates_from_csv.py # CLI: post certificates CSV to GCM
    └── convert_certs_into_csv.py   # CLI: convert PEM/DER files to CSV
```

## Security

### Credential Storage

- All sensitive data (passwords, tokens, secrets, **API keys**) is encrypted using Fernet symmetric encryption
- Encryption keys are stored in the `.env` file
- Never commit `.env` or `config.toml` files to version control

### Best Practices

1. **Use Strong Passwords**: Ensure GCM credentials are strong and unique
2. **Enable SSL Verification**: Set `insecure = false` in production
3. **Restrict Access**: Limit network access to the web UI server
4. **Regular Updates**: Keep credentials rotated and updated
5. **File Permissions**: Protect configuration files:
   ```bash
   chmod 600 config.toml
   chmod 600 backend/.env
   ```

### HTTPS in Production

For production deployments, use a reverse proxy (nginx, Apache) with SSL/TLS:

```nginx
server {
    listen 443 ssl;
    server_name gcm-ui.example.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Troubleshooting

### Backend Won't Start

**Problem**: Import errors or module not found

**Solution**:
```bash
cd backend
source .venv/bin/activate
pip install -r requirements.txt
```

### Cannot Connect to GCM

**Problem**: Connection refused or timeout errors

**Solution**:
- Verify GCM URIs in `config.toml`
- Check network connectivity: `curl -k https://your-gcm-host:31443`
- Ensure firewall allows connections
- Try with `insecure = true` for testing (development only)

### Authentication Fails

**Problem**: Login or authorization errors (OIDC)

**Solution**:
- Verify credentials in profile
- Check Keycloak realm and client ID
- Ensure user has proper GCM permissions
- Review error messages in browser console

**Problem**: API key requests return `401 Unauthorized`

**Solution**:
- Verify the `api_key` field is set on the active profile
- Confirm the profile has `auth_method = api_key`
- Re-save the profile with the correct key if it was updated on the GCM side
- Note: the `/api/v1/auth/login` endpoint returns `400` for API key profiles — this is expected

### Database Errors

**Problem**: Database locked or corruption errors

**Solution**:
```bash
cd backend
rm gcm_webui.db
uvicorn app.main:app --reload  # Will recreate database
```

### Scanner: Objects Show as Imported but Are Not Visible in GCM

**Problem**: After clicking **📤 Import All to GCM** the results table shows non-zero **Imported** counts for SSH host keys or TLS protocols, but the objects do not appear in the GCM inventory.

**Cause**: GCM returns HTTP 200 for the ingest request even when it silently rejects individual records (e.g. because the `it_asset_uri` does not match a known IT asset, or a field value is not in an expected enumeration).

**Solution**:
1. Expand the **GCM responses** collapsible section in the import results panel — it shows the raw GCM response body per object.
2. Look for messages such as `"no asset found for uri"`, `"invalid value"`, or a `created_count: 0` in the JSON body.
3. Ensure the URI used in the scan target CSV matches an existing IT asset URI registered in GCM (exact string match, including scheme and port).
4. If IT assets for those hosts do not yet exist in GCM, create or import them first via the **IT Assets** tab before re-running the ingest.

### Port Already in Use

**Problem**: Port 8000 is already in use

**Solution**:
```bash
# Use a different port
uvicorn app.main:app --host 0.0.0.0 --port 8080

# Or find and kill the process using port 8000
lsof -ti:8000 | xargs kill -9  # On Linux/macOS
```

## Production Deployment

### Using Gunicorn (Recommended)

```bash
cd backend
source .venv/bin/activate
pip install gunicorn

# Start with multiple workers
gunicorn app.main:app \
  -w 4 \
  -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --access-logfile - \
  --error-logfile -
```

### Using systemd Service

Create `/etc/systemd/system/gcm-webui.service`:

```ini
[Unit]
Description=GCM Web UI
After=network.target

[Service]
Type=notify
User=gcm-user
WorkingDirectory=/path/to/dist/backend
Environment="PATH=/path/to/dist/backend/.venv/bin"
ExecStart=/path/to/dist/backend/.venv/bin/gunicorn app.main:app \
  -w 4 \
  -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable gcm-webui
sudo systemctl start gcm-webui
sudo systemctl status gcm-webui
```

## Upgrading

To upgrade to a newer version:

1. **Backup your data**:
   ```bash
   cp backend/gcm_webui.db backend/gcm_webui.db.backup
   cp config.toml config.toml.backup
   cp backend/.env backend/.env.backup
   ```

2. **Extract new version** to a temporary location

3. **Copy your configuration**:
   ```bash
   cp config.toml.backup new-dist/config.toml
   cp backend/.env.backup new-dist/backend/.env
   cp backend/gcm_webui.db.backup new-dist/backend/gcm_webui.db
   ```

4. **Update dependencies**:
   ```bash
   cd new-dist/backend
   source .venv/bin/activate
   pip install -r requirements.txt --upgrade
   ```

5. **Restart the application**

## Uninstallation

To remove the application:

```bash
# Stop the service (if using systemd)
sudo systemctl stop gcm-webui
sudo systemctl disable gcm-webui

# Remove the application directory
rm -rf /path/to/dist

# Remove systemd service file (if created)
sudo rm /etc/systemd/system/gcm-webui.service
sudo systemctl daemon-reload
```

## Support and Documentation

### Additional Resources

- **API Documentation**: http://localhost:8000/api/docs (when running)
- **GCM Documentation**: Refer to your GCM installation documentation
- **Python FastAPI**: https://fastapi.tiangolo.com/
- **SQLAlchemy**: https://www.sqlalchemy.org/

### Getting Help

For issues or questions:

1. Check this README and troubleshooting section
2. Review the API documentation
3. Check application logs in `backend/logs/` (if configured)
4. Consult your GCM administrator

## Future Enhancements

The following features are planned for future releases:

### User Management
- Keycloak user creation and management
- Role assignment and permissions
- User lifecycle management
- Integration with GCM user directory

## License

This software is provided as-is for use with Guardium Cryptography Manager. Refer to your GCM license agreement for terms and conditions.

## Acknowledgments

This application integrates with:
- **FastAPI**: Modern Python web framework
- **SQLAlchemy**: SQL toolkit and ORM
- **Chart.js**: JavaScript charting library
- **Cryptography**: Python cryptographic library

---

**Note**: This is experimental software. Review and adapt the code and configurations to your organization's security and operational standards before production use.