#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
usage: gen_target_list.py [-h] [--ip IP] [--hosts HOSTS] -p PORTS [-o OUTPUT_CSV] [--alias_prefix ALIAS_PREFIX]

Generate scan target list as CSV

options:
  -h, --help            show this help message and exit
  --ip IP               One or more IP ranges in CIDR or wildcard format, comma-separated (e.g.,
                        192.168.1.0/24,10.0.0.*)
  --hosts HOSTS         Comma-separated list of FQDNs (e.g., example.com,another.com)
  -p PORTS, --ports PORTS
                        Port range or list (e.g., 443-8443 or 443,8443)
  -o OUTPUT_CSV, --output_csv OUTPUT_CSV
                        Output CSV file (default: scan_targets.csv)
  --alias_prefix ALIAS_PREFIX
                        Optional prefix for alias names
"""

# This code includes collective AI generated fragments

import argparse
import csv
import ipaddress
import sys

def expand_ips(ip_pattern):
    ips = []
    if '*' in ip_pattern:
        # Handle wildcard: e.g., 192.168.1.*
        base = ip_pattern.split('*')[0]
        for i in range(256):
            ips.append(f"{base}{i}")
    else:
        # Handle CIDR: e.g., 192.168.1.0/24
        try:
            network = ipaddress.ip_network(ip_pattern, strict=False)
            ips = [str(ip) for ip in network.hosts()]
        except ValueError:
            # Single IP
            ips = [ip_pattern]
    return ips

def expand_ports(port_pattern):
    ports = []
    for part in port_pattern.split(','):
        if '-' in part:
            start, end = map(int, part.split('-'))
            ports.extend(range(start, end + 1))
        else:
            ports.append(int(part))
    return ports

def main():
    parser = argparse.ArgumentParser(description="Generate scan target list as CSV")
    parser.add_argument("--ip", help="One or more IP ranges in CIDR or wildcard format, comma-separated (e.g., 192.168.1.0/24,10.0.0.*)")
    parser.add_argument("--hosts", help="Comma-separated list of FQDNs (e.g., example.com,another.com)")
    parser.add_argument("-p", "--ports", required=True, help="Port range or list (e.g., 443-8443 or 443,8443)")
    parser.add_argument("-o", "--output_csv", default="scan_targets.csv", help="Output CSV file (default: scan_targets.csv)")
    parser.add_argument("--alias_prefix", default="", help="Optional prefix for alias names")

    args = parser.parse_args()

    # Validate that at least one of ip_range or fqdn_list is provided
    if not args.ip and not args.hosts:
        print("[ERROR] You must specify either --ip or --hosts.")
        parser.print_help()
        sys.exit(1)

    ips = []
    if args.ip:
        # Split multiple ranges by comma and expand each
        for ip_range in args.ip.split(','):
            ip_range = ip_range.strip()
            if ip_range:
                ips.extend(expand_ips(ip_range))
    if args.hosts:
        ips.extend([fqdn.strip() for fqdn in args.hosts.split(',')])

    ports = expand_ports(args.ports)

    rows = []
    for ip in ips:
        for port in ports:
            uri = f"https://{ip}:{port}"
            alias = f"{args.alias_prefix}{ip}_{port}"
            rows.append([alias, uri])

    with open(args.output_csv, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Alias", "URI"])
        writer.writerows(rows)

    print(f"[INFO] Generated {len(rows)} targets in {args.output_csv}")

if __name__ == "__main__":
    main()
