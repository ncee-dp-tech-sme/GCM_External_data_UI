#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
usage: get_certificates.py [-h] [-i INPUT_CSV] [-o OUTPUT_CSV] [--timeout TIMEOUT] [--insecure]

SSL Certificate Collector: Fetch certificates from a list of URLs and export to CSV

options:
  -h, --help            show this help message and exit
  -i INPUT_CSV, --input_csv INPUT_CSV
                        Path to the input CSV file containing target URLs (default: input_urls.csv)
  -o OUTPUT_CSV, --output_csv OUTPUT_CSV
                        Path to the output CSV file to save certificate information (default: certificates.csv)
  --timeout TIMEOUT     Socket timeout seconds (default: 5)
  --insecure            Allow self-signed certificates (disable certificate verification)
"""

# This code includes collective AI generated fragments

import csv, ssl, socket, base64, argparse
from urllib.parse import urlparse

def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="SSL Certificate Collector: Fetch certificates from a list of URLs and export to CSV"
    )
    parser.add_argument(
        "-i", "--input_csv",
        default="input_urls.csv",
        help="Path to the input CSV file containing target URLs (default: input_urls.csv)"
    )
    parser.add_argument(
        "-o", "--output_csv",
        default="certificates.csv",
        help="Path to the output CSV file to save certificate information (default: certificates.csv)"
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


def create_ssl_context(insecure: bool) -> ssl.SSLContext:
    """Create an SSLContext.
    If insecure=True, disable certificate verification and hostname checking.
    Otherwise, use the default verified context.
    """
    if insecure:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context
    else:
        return ssl.create_default_context()


def main():
    # Set up command-line argument parser
    parser = build_arg_parser()
    args = parser.parse_args()

    input_csv = args.input_csv
    output_csv = args.output_csv
    timeout = args.timeout
    insecure = args.insecure

    rows = []
    # Read input CSV file
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
                        cert = ssock.getpeercert(binary_form=True)
                        cert_b64 = base64.b64encode(cert).decode('utf-8')
                        rows.append([alias, cert_b64, uri])
                        print(f"[INFO] Successfully retrieved certificate from {uri}")
            except Exception as e:
                print(f"[ERROR] Failed to retrieve certificate from {uri} - {e}")

    # Write output CSV file
    with open(output_csv, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Alias", "Certdata", "URI (optional)"])
        writer.writerows(rows)
    print(f"[INFO] Certificate information has been saved to {output_csv}")


if __name__ == "__main__":
    main()
