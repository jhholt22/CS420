import socket

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(5)

try:
    sock.sendto(b"command", ("192.168.10.1", 8889))
    print("sent")
    print(sock.recvfrom(1024))
finally:
    sock.close()