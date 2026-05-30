#!/usr/bin/env python3

import socket
import ssl
import sys
import pprint

hostname = sys.argv[1]
port = 443
cadir = './client-certs'

print(f"=== Task 1.d: Send and Receive Encrypted Data ===")
print(f"Target: {hostname}")

# Set up the TLS context
context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
context.load_verify_locations(capath=cadir)
context.verify_mode = ssl.CERT_REQUIRED
context.check_hostname = True

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((hostname, port))

ssock = context.wrap_socket(sock, server_hostname=hostname)
ssock.do_handshake()

print(f"\n=== TLS Connection Established ===")
print(f"Protocol: {ssock.version()}")
print(f"Cipher: {ssock.cipher()}")

# Send HTTP GET request
request = f"GET / HTTP/1.1\r\nHost: {hostname}\r\nUser-Agent: TLS-Client/1.0\r\nAccept: */*\r\nConnection: close\r\n\r\n"
print(f"\n=== Sending HTTP Request ===")
print(request.strip())
ssock.sendall(request.encode())

# Receive response
print(f"\n=== Receiving HTTP Response ===")
response = b""
while True:
    chunk = ssock.recv(4096)
    if not chunk:
        break
    response += chunk
    if b"\r\n\r\n" in response:
        # Got headers, check Content-Length
        header_end = response.find(b"\r\n\r\n")
        headers = response[:header_end].decode('utf-8', errors='replace')
        if 'Content-Length' in headers:
            cl = int(headers.split('Content-Length: ')[1].split('\r\n')[0])
            body_received = len(response) - header_end - 4
            if body_received >= cl:
                break
        elif 'Transfer-Encoding: chunked' in headers:
            if response.endswith(b"0\r\n\r\n"):
                break

# Print response (truncate if too long)
resp_str = response.decode('utf-8', errors='replace')
if len(resp_str) > 2000:
    print(resp_str[:2000])
    print(f"\n... [Response truncated, total {len(response)} bytes] ...")
else:
    print(resp_str)

ssock.shutdown(socket.SHUT_RDWR)
ssock.close()
print("\n=== Connection Closed ===")
