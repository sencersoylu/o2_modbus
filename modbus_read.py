import socket
import struct
import json
import sys
import time

RESPONSE_TIMEOUT = 2  # saniye - slave yanit bekleme suresi


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


def read_register_0_1(sock, slave_id):
    """Register 0-1 oku, float dondur."""
    pdu = struct.pack(">BBHH", slave_id, 0x03, 0x0000, 0x0002)
    crc = crc16_modbus(pdu)
    request = pdu + struct.pack("<H", crc)

    # Onceki kalinti veriyi temizle
    sock.setblocking(False)
    try:
        while sock.recv(1024):
            pass
    except BlockingIOError:
        pass
    sock.setblocking(True)
    sock.settimeout(RESPONSE_TIMEOUT)

    sock.sendall(request)

    try:
        response = sock.recv(1024)
    except socket.timeout:
        raise ValueError("Yanit yok (timeout) - cihaz bagli degil")

    if len(response) < 7:
        raise ValueError(f"Yanit cok kisa ({len(response)} byte)")

    # CRC kontrolu
    resp_crc = struct.unpack("<H", response[-2:])[0]
    calc_crc = crc16_modbus(response[:-2])
    if resp_crc != calc_crc:
        raise ValueError("CRC hatasi")

    # Slave ID kontrolu
    resp_slave = response[0]
    if resp_slave != slave_id:
        raise ValueError(f"Yanlis slave ID: beklenen {slave_id}, gelen {resp_slave}")

    resp_fc = response[1]
    if resp_fc & 0x80:
        error_code = response[2]
        raise ValueError(f"Modbus exception: {error_code}")

    # 2 register -> float (Big Endian)
    raw = response[3:7]
    value = struct.unpack(">f", raw)[0]
    return value


def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.json"

    with open(config_path) as f:
        config = json.load(f)

    host = config["host"]
    port = config["port"]
    devices = config["devices"]

    print(f"Hedef: {host}:{port}")
    print(f"Cihaz sayisi: {len(devices)}\n")

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(5)
            sock.connect((host, port))

            for dev in devices:
                slave_id = dev["slave_id"]
                name = dev.get("name", f"Slave {slave_id}")
                try:
                    value = read_register_0_1(sock, slave_id)
                    print(f"  {name} (ID:{slave_id}) -> {value:.2f}")
                except ValueError as e:
                    print(f"  {name} (ID:{slave_id}) -> HATA: {e}")

    except socket.timeout:
        print("HATA: Baglanti zaman asimina ugradi")
    except ConnectionRefusedError:
        print("HATA: Baglanti reddedildi")
    except Exception as e:
        print(f"HATA: {e}")


if __name__ == "__main__":
    main()
