# GCM Web UI - Distribution Package

**Version:** 1.0.0  
**Last Updated:** 2026-06-02

## Overview

This is a distributable package of the GCM (Guardium Cryptography Manager) Web UI application. It provides a complete web-based interface for managing GCM operations including certificate management, IT asset management, profile management, and authentication. Additional features for user management and disconnected scanning are planned for future releases.

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
- 🔑 **Authentication**: Secure login and authorization with GCM
- 📜 **Certificate Management**: Upload, sync, view, and manage certificates
- 🖥️ **IT Asset Management**: Create, sync, and manage IT assets
- 📈 **Visual Analytics**: Real-time charts and statistics
- 🔒 **Security**: Encrypted credential storage with Fernet encryption

### Coming Soon

- 👥 **User Management**: Keycloak user creation and management *(Future Addition)*
- 🔍 **Disconnected Scanner**: Certificate discovery in air-gapped environments *(Future Addition)*

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

```toml
[connection]
app_uri = "https://your-gcm-host:31443"
oidc_uri = "https://your-gcm-host:30443"
realm = "gcmrealm"

[http]
timeout = 30.0
insecure = false  # Set to true only for development/test
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
   - **Client ID**: OIDC client identifier
   - **Client Secret**: OIDC client secret (will be encrypted)
   - **Username**: Your GCM username (will be encrypted)
   - **Password**: Your GCM password (will be encrypted)
3. Click **Save Profile**
4. Click **Activate** to set it as the active profile

### Authentication

After creating and activating a profile:

1. Navigate to the **Authentication** tab
2. Click **Login & Authorize**
3. The system will authenticate and authorize with GCM

You're now ready to use all features!

## Usage Guide

### Certificate Management

**Sync Certificates from GCM:**
1. Go to **Certificates** tab
2. Click **Sync from GCM**
3. View synced certificates in the list

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

**Create a New Asset:**
1. Click **Create Asset**
2. Fill in asset details (URI, hostname, type, etc.)
3. Click **Create**

**View Asset Details:**
- Click **View** on any asset to see full information
- Includes organizational metadata and security attributes


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
    ├── get_certificates.py
    ├── post_certificates_from_csv.py
    └── convert_certs_into_csv.py
```

## Security

### Credential Storage

- All sensitive data (passwords, tokens, secrets) is encrypted using Fernet symmetric encryption
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

**Problem**: Login or authorization errors

**Solution**:
- Verify credentials in profile
- Check Keycloak realm and client ID
- Ensure user has proper GCM permissions
- Review error messages in browser console

### Database Errors

**Problem**: Database locked or corruption errors

**Solution**:
```bash
cd backend
rm gcm_webui.db
uvicorn app.main:app --reload  # Will recreate database
```

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

### Disconnected Scanner
- Certificate discovery in air-gapped environments
- Bulk certificate scanning from target lists
- CSV import/export for scan results
- Automated certificate inventory updates

These features are currently in development and will be included in upcoming versions. The backend API endpoints and frontend modules are partially implemented but not yet fully functional or tested.

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