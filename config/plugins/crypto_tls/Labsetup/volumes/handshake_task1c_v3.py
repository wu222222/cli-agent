#!/usr/bin/env python3

import socket
import ssl
import sys
import pprint

hostname = sys.argv[1]
# Use a hostname NOT in the certificate's SAN list
fake_hostname = "www.google.com"  # Definitely not in baidu.com's cert
port = 443
cadir = './client-certs'

# Set up the TLS context
context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
context.load_verify_locations(capath=cadir)
context.verify_mode = ssl.CERT_REQUIRED
context.check_hostname = True

# Create TCP connection
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((hostname, port))

# Add TLS - use fake_hostname for SNI and certificate verification
ssock = context.wrap_socket(sock, server_hostname=fake_hostname,
                            do_handshake_on_connect=False)
try:
    ssock.do_handshake()
    print("=== SUCCESS: Handshake completed (unexpected!)")
    print("=== Server hostname: {}".format(ssock.server_hostname))
    pprint.pprint(ssock.getpeercert())
    ssock.shutdown(socket.SHUT_RDWR)
    ssock.close()
except ssl.SSLCertVerificationError as e:
    print(f"=== FAILED (expected): {e}")
    print("\nThis demonstrates hostname mismatch detection works!")
