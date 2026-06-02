#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
usage: convert_certs_into_csv.py [-h] [-o OUTPUT] [--recursive] [--default-port DEFAULT_PORT] [--alias-mode {filename,hostport}] path

Export PEM/DER certificates to template CSV: Alias, Certdata (Base64), URI (optional).

positional arguments:
  path                  Path to a certificate file or a folder containing certificates

options:
  -h, --help            show this help message and exit
  -o OUTPUT, --output OUTPUT
                        Output CSV file path (default: certificates_for_import.csv)
  --recursive           Recursively search subfolders (default: disabled)
  --default-port DEFAULT_PORT
                        Port used when not found (default: 443)
  --alias-mode {filename,hostport}
                        Alias generation mode: 'filename' (basename without extension) or 'hostport'. Default: filename
"""

# This code includes collective AI generated fragments

import argparse
import base64
import csv
import re
from pathlib import Path
from urllib.parse import urlparse

from cryptography import x509
from cryptography.x509.oid import NameOID, ExtensionOID

PEM_BEGIN_RE = re.compile(r"-----BEGIN CERTIFICATE-----")
PEM_END_RE = re.compile(r"-----END CERTIFICATE-----")
CERT_EXTS = {".pem", ".crt", ".cer", ".der"}


def read_first_pem_block(text):
    """
    Extract the first 'BEGIN CERTIFICATE' ... 'END CERTIFICATE' block from PEM text.
    Returns the block as bytes (UTF-8), or None if not found.
    """
    begin = PEM_BEGIN_RE.search(text)
    end = PEM_END_RE.search(text)
    if not begin or not end or end.start() < begin.start():
        return None
    block = text[begin.start() : end.end()]
    return block.encode("utf-8")


def load_certificate_from_file(path):
    """
    Load x509.Certificate from a PEM/DER file.
    - PEM: use the first certificate block.
    - DER: load bytes directly.
    Returns certificate or None on failure.
    """
    try:
        data = path.read_bytes()
        try:
            text = data.decode("utf-8", errors="ignore")
        except Exception:
            text = ""

        if "BEGIN CERTIFICATE" in text:
            pem_block = read_first_pem_block(text)
            if pem_block:
                return x509.load_pem_x509_certificate(pem_block)
            # Fallback: try loading entire data as PEM
            return x509.load_pem_x509_certificate(data)
        else:
            return x509.load_der_x509_certificate(data)
    except Exception:
        return None


def get_original_content_b64(path):
    """
    Read the original file content and return Base64 string.
    - For PEM: Base64-encode the first certificate block text (including headers).
      If block cannot be isolated, encode the whole file content as is.
    - For DER: Base64-encode raw bytes.
    """
    try:
        data = path.read_bytes()
        try:
            text = data.decode("utf-8", errors="ignore")
        except Exception:
            text = ""

        if "BEGIN CERTIFICATE" in text:
            pem_block = read_first_pem_block(text)
            if pem_block:
                return base64.b64encode(pem_block).decode("utf-8")
            return base64.b64encode(data).decode("utf-8")
        else:
            return base64.b64encode(data).decode("utf-8")
    except Exception:
        return ""


def get_cn(cert):
    """
    Get Subject Common Name (CN) from certificate, or None if not available.
    """
    try:
        cns = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        if cns:
            return cns[0].value
    except Exception:
        pass
    return None


def extract_uri_or_cn(cert):
    """
    Return a tuple (value, cn) where:
    - value: first URI from SAN if available; otherwise CN (FQDN).
    - cn: CN if available; otherwise None.
    """
    try:
        san = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME).value
        uris = san.get_values_for_type(x509.UniformResourceIdentifier)
        if uris:
            return uris[0], get_cn(cert)
    except x509.ExtensionNotFound:
        pass

    cn = get_cn(cert)
    if cn:
        return cn, cn

    return "", get_cn(cert)


def derive_alias_hostport(value, default_port):
    """
    Derive alias 'host_port' from a URI or CN/FQDN:
    - Parse as URI to get hostname and port when possible.
    - If not a URI, treat value as hostname.
    - If port is missing, use default_port.
    """
    host = None
    port = None

    parsed = urlparse(value)
    if parsed.hostname:
        host = parsed.hostname
        port = parsed.port

    if not host:
        host = value.strip()

    if not port:
        port = default_port

    return "{}_{}".format(host, port)


def is_candidate_file(path):
    """
    Rough check if a file looks like a certificate:
    - Known extensions OR contains PEM header.
    """
    if path.suffix.lower() in CERT_EXTS:
        return True
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "BEGIN CERTIFICATE" in text:
            return True
    except Exception:
        pass
    return False


def iter_cert_files(root, recursive):
    """
    Yield certificate files under 'root'.
    - If 'root' is a file, yield it if it looks like a certificate.
    - If 'root' is a folder, enumerate files (optionally recursive).
    """
    if root.is_file():
        if is_candidate_file(root):
            yield root
        return

    if not root.is_dir():
        return

    if recursive:
        for p in root.rglob("*"):
            if p.is_file() and is_candidate_file(p):
                yield p
    else:
        for p in root.glob("*"):
            if p.is_file() and is_candidate_file(p):
                yield p


def main():
    parser = argparse.ArgumentParser(
        description="Export PEM/DER certificates to template CSV: Alias, Certdata (Base64), URI (optional)."
    )
    parser.add_argument("path", help="Path to a certificate file or a folder containing certificates")
    parser.add_argument("-o", "--output", default="certificates_for_import.csv",
                        help="Output CSV file path (default: certificates_for_import.csv)")
    parser.add_argument("--recursive", action="store_true",
                        help="Recursively search subfolders (default: disabled)")
    parser.add_argument("--default-port", type=int, default=443,
                        help="Port used when not found (default: 443)")
    parser.add_argument("--alias-mode", choices=["filename", "hostport"], default="filename",
                        help="Alias generation mode: 'filename' (basename without extension) or 'hostport'. Default: filename")
    args = parser.parse_args()

    root = Path(args.path)

    rows = []  # (Alias, Certdata, URI (optional))
    for file_path in iter_cert_files(root, args.recursive):
        cert = load_certificate_from_file(file_path)
        if not cert:
            print("[WARN] Failed to load certificate: {}".format(file_path))
            continue

        value, cn = extract_uri_or_cn(cert)
        if not value:
            print("[WARN] No URI/CN found: {}".format(file_path))
            continue

        # Alias generation by mode
        if args.alias_mode == "filename":
            alias = file_path.stem  # basename without extension
        else:
            alias = derive_alias_hostport(value, args.default_port)

        cert_b64 = get_original_content_b64(file_path)
        rows.append((alias, cert_b64, value))
        print("[INFO] {} -> Alias={}, URI={}, Certdata(Base64) generated".format(file_path, alias, value))

    if rows:
        with open(args.output, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            # Match the provided template header exactly
            writer.writerow(["Alias", "Certdata", "URI (optional)"])
            writer.writerows(rows)
        print("[INFO] CSV saved: {}".format(args.output))
    else:
        print("[INFO] No output rows.")


if __name__ == "__main__":
    main()
