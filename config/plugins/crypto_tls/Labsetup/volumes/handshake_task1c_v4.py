#!/usr/bin/env python3

import socket
import ssl
import sys
import pprint

hostname = sys.argv[1]
port = 443
cadir = './client-certs'

print(f"=== Task 1.c: Hostname Verification Test ===")
print(f"Target: {hostname}")

# Set up the TLS context - disable hostname check first to get the cert
context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
context.load_verify_locations(capath=cadir)
context.verify_mode = ssl.CERT_REQUIRED
context.check_hostname = False  # Disable hostname check to get cert first

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((hostname, port))

ssock = context.wrap_socket(sock, server_hostname=hostname)
ssock.do_handshake()

# Get the server certificate
cert = ssock.getpeercert()
print("\n=== Server Certificate Subject Alt Names ===")
san_list = cert.get('subjectAltName', [])
for san_type, san_value in san_list:
    print(f"  {san_type}: {san_value}")

# Test 1: Verify with correct hostname
print("\n--- Test 1: Verify with CORRECT hostname ---")
try:
    ssl.match_hostname(cert, hostname)
    print(f"  PASS: '{hostname}' matches certificate")
except ssl.CertificateError as e:
    print(f"  FAIL: {e}")

# Test 2: Verify with WRONG hostname
fake_hostname = "www.evil.com"
print(f"\n--- Test 2: Verify with WRONG hostname '{fake_hostname}' ---")
try:
    ssl.match_hostname(cert, fake_hostname)
    print(f"  PASS: '{fake_hostname}' matches certificate (unexpected!)")
except ssl.CertificateError as e:
    print(f"  FAIL (expected): {e}")
    print("  This demonstrates hostname mismatch detection works!")

# Test 3: Verify with wildcard-compatible hostname
wildcard_test = "map.baidu.com"
print(f"\n--- Test 3: Verify with wildcard-compatible hostname '{wildcard_test}' ---")
try:
    ssl.match_hostname(cert, wildcard_test)
    print(f"  PASS: '{wildcard_test}' matches certificate (wildcard match)")
except ssl.CertificateError as e:
    print(f"  FAIL: {e}")

ssock.shutdown(socket.SHUT_RDWR)
ssock.close()
