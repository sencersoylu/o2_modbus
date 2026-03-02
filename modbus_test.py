import socket
import struct

HOST = "192.168.1.201"
PORT = 4196


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


# Modbus RTU over TCP: Read 10 Holding Registers, address 0, Slave ID 2
slave_id = 0x02
function_code = 0x03
start_address = 0x0000
quantity = 0x000A

pdu = struct.pack(">BBHH", slave_id, function_code, start_address, quantity)
crc = crc16_modbus(pdu)
request = pdu + struct.pack("<H", crc)  # CRC little-endian

print(f"Hedef: {HOST}:{PORT}")
print(f"Gonderilen (hex): {request.hex(' ')}")
print(f"  Slave ID       : {slave_id}")
print(f"  Function       : 0x03 (Read Holding Registers)")
print(f"  Start Address  : {start_address}")
print(f"  Quantity       : {quantity}")
print(f"  CRC            : {crc:#06x}")
print()

try:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(5)
        print("Baglaniyor...")
        sock.connect((HOST, PORT))
        print("Baglanti kuruldu!")

        sock.sendall(request)
        print("Istek gonderildi, yanit bekleniyor...\n")

        response = sock.recv(1024)
        print(f"Alinan (hex): {response.hex(' ')}")
        print(f"Alinan ({len(response)} byte)")

        if len(response) < 5:
            print("Yanit cok kisa, parse edilemiyor.")
        else:
            # CRC kontrolu
            resp_data = response[:-2]
            resp_crc = struct.unpack("<H", response[-2:])[0]
            calc_crc = crc16_modbus(resp_data)

            resp_slave = response[0]
            resp_fc = response[1]

            print(f"\n--- Yanit Analizi ---")
            print(f"  Slave ID       : {resp_slave}")
            print(f"  Function Code  : {resp_fc:#04x}")
            print(f"  CRC            : {resp_crc:#06x} ({'OK' if resp_crc == calc_crc else 'HATALI!'})")

            if resp_fc == 0x03:
                byte_count = response[2]
                print(f"  Byte Count     : {byte_count}")
                print(f"\n--- Register Degerleri ---")
                for i in range(byte_count // 2):
                    val = struct.unpack(">H", response[3 + i*2 : 5 + i*2])[0]
                    print(f"  Register {start_address + i:5d} : {val:5d}  (0x{val:04X})")
            elif resp_fc & 0x80:
                error_code = response[2]
                errors = {
                    1: "Illegal Function",
                    2: "Illegal Data Address",
                    3: "Illegal Data Value",
                    4: "Server Device Failure",
                }
                print(f"  HATA! Exception code: {error_code} - {errors.get(error_code, 'Bilinmeyen')}")

except socket.timeout:
    print("HATA: Baglanti zaman asimina ugradi (5 saniye)")
except ConnectionRefusedError:
    print("HATA: Baglanti reddedildi. Cihaz eriselebilir mi?")
except Exception as e:
    print(f"HATA: {e}")
