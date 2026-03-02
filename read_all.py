import socket
import struct
import json
import time

with open("config.json") as f:
    CONFIG = json.load(f)

HOST = CONFIG["host"]
PORT = CONFIG["port"]
SLAVE_ID = CONFIG["devices"][0]["slave_id"]

REGISTERS = [
    {"addr": 0x0000, "name": "Giris degeri",        "type": "float"},
    {"addr": 0x0002, "name": "Ortam sicakligi",     "type": "float"},
    {"addr": 0x0004, "name": "Giris tipi",           "type": "int"},
    {"addr": 0x0006, "name": "Giris tipi - secenek 1", "type": "int"},
    {"addr": 0x0008, "name": "Giris tipi - secenek 2", "type": "int"},
    {"addr": 0x000A, "name": "Giris tipi - secenek 3", "type": "int"},
    {"addr": 0x000C, "name": "Baudrate",             "type": "int"},
    {"addr": 0x000E, "name": "Parite",               "type": "int"},
    {"addr": 0x0010, "name": "MODBUS kole ID",       "type": "int"},
    {"addr": 0x0012, "name": "Kayit degeri (WO)",    "type": "int"},
]


def crc16_modbus(data):
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc


sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(5)
sock.connect((HOST, PORT))
print(f"Baglandi: {HOST}:{PORT} (Slave {SLAVE_ID})\n")
print(f"{'Register':<8} {'Adres':<8} {'Ad':<25} {'Raw Hex':<12} {'Deger'}")
print("-" * 80)

for reg in REGISTERS:
    time.sleep(0.1)

    # Flush
    sock.setblocking(False)
    try:
        while sock.recv(1024):
            pass
    except BlockingIOError:
        pass
    sock.setblocking(True)
    sock.settimeout(2)

    pdu = struct.pack(">BBHH", SLAVE_ID, 0x03, reg["addr"], 0x0002)
    crc = crc16_modbus(pdu)
    request = pdu + struct.pack("<H", crc)
    sock.sendall(request)

    try:
        response = sock.recv(1024)
    except socket.timeout:
        print(f"{40001+reg['addr']:<8} 0x{reg['addr']:04X}    {reg['name']:<25} {'TIMEOUT':<12}")
        continue

    if len(response) < 7:
        print(f"{40001+reg['addr']:<8} 0x{reg['addr']:04X}    {reg['name']:<25} {'KISA YANIT':<12}")
        continue

    resp_crc = struct.unpack("<H", response[-2:])[0]
    calc_crc = crc16_modbus(response[:-2])
    if resp_crc != calc_crc:
        print(f"{40001+reg['addr']:<8} 0x{reg['addr']:04X}    {reg['name']:<25} {'CRC HATA':<12}")
        continue

    if response[1] & 0x80:
        exc_code = response[2]
        print(f"{40001+reg['addr']:<8} 0x{reg['addr']:04X}    {reg['name']:<25} {'EXCEPTION':<12} code={exc_code}")
        continue

    raw = response[3:7]
    raw_hex = raw.hex()

    if reg["type"] == "float":
        value = struct.unpack(">f", raw)[0]
        print(f"{40001+reg['addr']:<8} 0x{reg['addr']:04X}    {reg['name']:<25} {raw_hex:<12} {value:.4f}")
    else:
        value_u = struct.unpack(">I", raw)[0]
        value_s = struct.unpack(">i", raw)[0]
        print(f"{40001+reg['addr']:<8} 0x{reg['addr']:04X}    {reg['name']:<25} {raw_hex:<12} {value_u} (signed: {value_s})")

print()
while True:
    time.sleep(1)
    print(f"\n--- {time.strftime('%H:%M:%S')} ---")
    print(f"{'Register':<8} {'Ad':<25} {'Deger'}")
    print("-" * 55)
    for reg in REGISTERS:
        time.sleep(0.05)

        # Flush
        sock.setblocking(False)
        try:
            while sock.recv(1024):
                pass
        except BlockingIOError:
            pass
        sock.setblocking(True)
        sock.settimeout(2)

        pdu = struct.pack(">BBHH", SLAVE_ID, 0x03, reg["addr"], 0x0002)
        crc = crc16_modbus(pdu)
        request = pdu + struct.pack("<H", crc)
        sock.sendall(request)

        try:
            response = sock.recv(1024)
        except socket.timeout:
            print(f"{40001+reg['addr']:<8} {reg['name']:<25} TIMEOUT")
            continue

        if len(response) < 7 or (response[1] & 0x80):
            print(f"{40001+reg['addr']:<8} {reg['name']:<25} HATA")
            continue

        raw = response[3:7]
        if reg["type"] == "float":
            value = struct.unpack(">f", raw)[0]
            print(f"{40001+reg['addr']:<8} {reg['name']:<25} {value:.4f}")
        else:
            value = struct.unpack(">I", raw)[0]
            print(f"{40001+reg['addr']:<8} {reg['name']:<25} {value}")
