#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
usage: get_certificate_info.py [-h] [-i INPUT_CSV] [-o OUTPUT_CSV] [--timeout TIMEOUT] [--insecure]

SSL Certificate Collector: Fetch certificates information from a list of URLs and export to CSV

options:
  -h, --help            show this help message and exit
  -i INPUT_CSV, --input_csv INPUT_CSV
                        Path to the input CSV file containing target URLs (default: input_urls.csv)
  -o OUTPUT_CSV, --output_csv OUTPUT_CSV
                        Path to the output CSV file to save certificate information (default: certificate_info.csv)
  --timeout TIMEOUT     Socket timeout seconds (default: 5)
  --insecure            Allow self-signed certificates (disable certificate verification)
"""

# This code includes collective AI generated fragments

import csv, ssl, socket, argparse
from urllib.parse import urlparse
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.x509.oid import ExtensionOID, ExtendedKeyUsageOID

# Mapping of common Extended Key Usage OIDs to human-readable names
EKU_NAMES = {
    ExtendedKeyUsageOID.SERVER_AUTH.dotted_string: "TLS Web Server Authentication",
    ExtendedKeyUsageOID.CLIENT_AUTH.dotted_string: "TLS Web Client Authentication",
    ExtendedKeyUsageOID.CODE_SIGNING.dotted_string: "Code Signing",
    ExtendedKeyUsageOID.EMAIL_PROTECTION.dotted_string: "Email Protection",
    ExtendedKeyUsageOID.TIME_STAMPING.dotted_string: "Time Stamping",
    ExtendedKeyUsageOID.OCSP_SIGNING.dotted_string: "OCSP Signing"
}

def create_ssl_context(insecure: bool) -> ssl.SSLContext:
    """Create an SSLContext. If insecure=True, disable verification and hostname checks."""
    if insecure:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    return ssl.create_default_context()


def parse_certificate(cert_bytes):
    cert = x509.load_der_x509_certificate(cert_bytes, default_backend())
    # Basic details
    version = cert.version.name
    serial_number = hex(cert.serial_number)
    signature_algorithm = cert.signature_hash_algorithm.name if cert.signature_hash_algorithm else "Unknown"
    issuer = ", ".join([f"{attr.oid._name}={attr.value}" for attr in cert.issuer])
    subject = ", ".join([f"{attr.oid._name}={attr.value}" for attr in cert.subject])
    not_before = str(cert.not_valid_before)
    not_after = str(cert.not_valid_after)
    # Extract specific X509v3 extensions
    subject_alt_name = ""
    key_usage = ""
    extended_key_usage = ""
    for ext in cert.extensions:
        if ext.oid == ExtensionOID.SUBJECT_ALTERNATIVE_NAME:
            subject_alt_name = ", ".join(ext.value.get_values_for_type(x509.DNSName))
        elif ext.oid == ExtensionOID.KEY_USAGE:
            key_usage = ", ".join([name for name, value in {
                "Digital Signature": ext.value.digital_signature,
                "Content Commitment": ext.value.content_commitment,
                "Key Encipherment": ext.value.key_encipherment,
                "Data Encipherment": ext.value.data_encipherment,
                "Key Agreement": ext.value.key_agreement,
                "Key Cert Sign": ext.value.key_cert_sign,
                "CRL Sign": ext.value.crl_sign
            }.items() if value])
        elif ext.oid == ExtensionOID.EXTENDED_KEY_USAGE:
            eku_names = []
            for eku in ext.value:
                eku_names.append(EKU_NAMES.get(eku.dotted_string, eku.dotted_string))
            extended_key_usage = ", ".join(eku_names)
    return (version, serial_number, signature_algorithm, issuer, subject,
            not_before, not_after, subject_alt_name, key_usage, extended_key_usage)


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="SSL Certificate Collector: Fetch certificates information from a list of URLs and export to CSV"
    )
    parser.add_argument(
        "-i", "--input_csv",
        default="input_urls.csv",
        help="Path to the input CSV file containing target URLs (default: input_urls.csv)"
    )
    parser.add_argument(
        "-o", "--output_csv",
        default="certificate_info.csv",
        help="Path to the output CSV file to save certificate information (default: certificate_info.csv)"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="Socket timeout seconds (default: 5)"
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Allow self-signed certificates (disable certificate verification)"
    )
    return parser


def main():
    # Parse arguments
    parser = build_arg_parser()
    args = parser.parse_args()

    input_csv = args.input_csv
    output_csv = args.output_csv
    timeout = args.timeout
    insecure = args.insecure

    rows = []
    # Read input CSV
    with open(input_csv, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            uri = row.get("URI") or row.get("URL")
            alias = row.get("Alias") or ""
            if not uri:
                continue
            parsed = urlparse(uri)
            host = parsed.hostname
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            # Generate alias if missing
            if not alias.strip():
                alias = f"{host}_{port}"
            try:
                # Establish SSL connection and retrieve certificate
                context = create_ssl_context(insecure)
                with socket.create_connection((host, port), timeout=timeout) as sock:
                    with context.wrap_socket(sock, server_hostname=host) as ssock:
                        cert_bytes = ssock.getpeercert(binary_form=True)
                        (version, serial_number, signature_algorithm, issuer, subject,
                         not_before, not_after, subject_alt_name, key_usage, extended_key_usage) = parse_certificate(cert_bytes)
                        rows.append([alias, uri, version, serial_number, signature_algorithm, issuer, subject,
                                     not_before, not_after, subject_alt_name, key_usage, extended_key_usage])
                        print(f"[INFO] Successfully retrieved certificate from {uri}")
            except Exception as e:
                print(f"[ERROR] Failed to retrieve certificate from {uri} - {e}")

    # Write output CSV
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Alias", "URI", "Version", "Serial Number", "Signature Algorithm", "Issuer", "Subject",
                         "Not Before", "Not After", "Subject Alt Name", "Key Usage", "Extended Key Usage"])
        writer.writerows(rows)
    print(f"[INFO] Detailed certificate information has been saved to {output_csv}")


if __name__ == "__main__":
    main()
