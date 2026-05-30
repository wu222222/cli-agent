#!/usr/bin/env python3

import socket
import ssl
import sys
import pprint

hostname = sys.argv[1]
fake_hostname = sys.argv[2]  # The hostname to check against certificate
port = 443
cadir = './client-certs'

# Resolve the actual IP of the target
ip_addr = socket.getaddrinfo(hostname, port)[0][4][0]
print(f"Connecting to {hostname} (IP: {ip_addr})")
print(f"Checking certificate against: {fake_hostname}")

# Set up the TLS context
context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
context.load_verify_locations(capath=cadir)
context.verify_mode = ssl.CERT_REQUIRED
context.check_hostname = True

# Create TCP connection to the actual IP
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((ip_addr, port))

# Add TLS - use fake_hostname for certificate verification
ssock = context.wrap_socket(sock, server_hostname=fake_hostname,
                            do_handshake_on_connect=False)
try:
    ssock.do_handshake()
    print("=== SUCCESS: Handshake completed")
    print("=== Cipher used: {}".format(ssock.cipher()))
    print("=== Server hostname: {}".format(ssock.server_hostname))
    pprint.pprint(ssock.getpeercert())
    ssock.shutdown(socket.SHUT_RDWR)
    ssock.close()
except ssl.SSLCertVerificationError as e:
    print(f"=== FAILED: {e}")
