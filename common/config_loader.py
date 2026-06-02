#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Common configuration loader for GCM API scripts.
Loads configuration from TOML files and provides defaults for command-line arguments.

Usage:
    from common.config_loader import load_config, get_config_path
    
    config = load_config()  # Loads from default path or GCM_CONFIG env var
    # Use config values as defaults in argparse
"""

# This file includes AI-generated code - Review and modify as needed

import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional

# Python 3.11+ has tomllib in stdlib, earlier versions need tomli
try:
    import tomllib
except ModuleNotFoundError:
    try:
        import tomli as tomllib
    except ModuleNotFoundError:
        tomllib = None


def get_config_path(config_arg: Optional[str] = None) -> Optional[Path]:
    """
    Determine the configuration file path.
    
    Priority order:
    1. Explicit config_arg parameter (from -f/--config-file argument)
    2. GCM_CONFIG environment variable
    3. config.toml in current directory
    4. config.toml in script's parent directory (workspace root)
    
    Args:
        config_arg: Explicit config file path from command-line argument
        
    Returns:
        Path object if config file exists, None otherwise
    """
    # Priority 1: Explicit argument
    if config_arg:
        path = Path(config_arg)
        if path.exists():
            return path
        else:
            print(f"Warning: Specified config file not found: {config_arg}", file=sys.stderr)
            return None
    
    # Priority 2: Environment variable
    env_config = os.getenv('GCM_CONFIG')
    if env_config:
        path = Path(env_config)
        if path.exists():
            return path
        else:
            print(f"Warning: GCM_CONFIG points to non-existent file: {env_config}", file=sys.stderr)
    
    # Priority 3: Current directory
    current_config = Path('config.toml')
    if current_config.exists():
        return current_config
    
    # Priority 4: Script's parent directory (workspace root)
    # This handles cases where script is in subdirectory (certificates/, it_assets/, etc.)
    script_dir = Path(__file__).parent
    parent_config = script_dir.parent / 'config.toml'
    if parent_config.exists():
        return parent_config
    
    return None


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load configuration from TOML file.
    
    Args:
        config_path: Optional explicit path to config file
        
    Returns:
        Dictionary containing configuration sections (connection, authentication, http, tenant, advanced)
        Returns empty dict if no config file found or tomllib/tomli not available
    """
    if tomllib is None:
        # TOML library not available - return empty config
        # Scripts will fall back to command-line arguments
        return {}
    
    path = get_config_path(config_path)
    if path is None:
        # No config file found - return empty config
        return {}
    
    try:
        with open(path, 'rb') as f:
            config = tomllib.load(f)
        return config
    except Exception as e:
        print(f"Warning: Failed to load config file {path}: {e}", file=sys.stderr)
        return {}


def get_connection_defaults(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract connection-related defaults from config.
    
    Args:
        config: Configuration dictionary from load_config()
        
    Returns:
        Dictionary with keys: app_uri, oidc_uri, realm
    """
    conn = config.get('connection', {})
    return {
        'app_uri': conn.get('app_uri'),
        'oidc_uri': conn.get('oidc_uri'),
        'realm': conn.get('realm', 'gcmrealm'),
    }


def get_authentication_defaults(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract authentication-related defaults from config.
    
    Args:
        config: Configuration dictionary from load_config()
        
    Returns:
        Dictionary with keys: client_id, client_secret, refresh_token, username, password
    """
    auth = config.get('authentication', {})
    return {
        'client_id': auth.get('client_id', ''),
        'client_secret': auth.get('client_secret', ''),
        'refresh_token': auth.get('refresh_token'),
        'username': auth.get('username'),
        'password': auth.get('password'),
    }


def get_http_defaults(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract HTTP-related defaults from config.
    
    Args:
        config: Configuration dictionary from load_config()
        
    Returns:
        Dictionary with keys: timeout, insecure
    """
    http = config.get('http', {})
    return {
        'timeout': http.get('timeout', 30.0),
        'insecure': http.get('insecure', False),
    }


def get_tenant_defaults(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract tenant-related defaults from config.
    
    Args:
        config: Configuration dictionary from load_config()
        
    Returns:
        Dictionary with keys: tenant_id
    """
    tenant = config.get('tenant', {})
    return {
        'tenant_id': tenant.get('tenant_id', ''),
    }


def get_advanced_defaults(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract advanced settings from config.
    
    Args:
        config: Configuration dictionary from load_config()
        
    Returns:
        Dictionary with keys: user_agent
    """
    advanced = config.get('advanced', {})
    return {
        'user_agent': advanced.get('user_agent', 'gcm-api-scripts/1.0'),
    }


def add_config_argument(parser) -> None:
    """
    Add --config-file argument to an ArgumentParser.
    
    Args:
        parser: argparse.ArgumentParser instance
    """
    parser.add_argument(
        '-f', '--config-file',
        help='Path to TOML configuration file (default: config.toml in current or parent directory, or GCM_CONFIG env var)'
    )


def apply_config_defaults(parser, config: Dict[str, Any]) -> None:
    """
    Apply configuration defaults to parser arguments.
    This should be called after all arguments are added but before parsing.
    
    Note: This modifies parser defaults in-place.
    Command-line arguments will override these defaults.
    
    Args:
        parser: argparse.ArgumentParser instance
        config: Configuration dictionary from load_config()
    """
    conn = get_connection_defaults(config)
    auth = get_authentication_defaults(config)
    http = get_http_defaults(config)
    tenant = get_tenant_defaults(config)
    
    # Update defaults for connection arguments
    if conn['app_uri']:
        parser.set_defaults(app_uri=conn['app_uri'])
    if conn['oidc_uri']:
        parser.set_defaults(oidc_uri=conn['oidc_uri'])
    parser.set_defaults(realm=conn['realm'])
    
    # Update defaults for authentication arguments
    parser.set_defaults(client_id=auth['client_id'])
    parser.set_defaults(client_secret=auth['client_secret'])
    if auth['refresh_token']:
        parser.set_defaults(refresh_token=auth['refresh_token'])
    if auth['username']:
        parser.set_defaults(username=auth['username'])
    if auth['password']:
        parser.set_defaults(password=auth['password'])
    
    # Update defaults for HTTP arguments
    parser.set_defaults(timeout=http['timeout'])
    parser.set_defaults(insecure=http['insecure'])
    
    # Update defaults for tenant arguments
    parser.set_defaults(tenant_id=tenant['tenant_id'])