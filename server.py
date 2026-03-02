import asyncio
import socket
import struct
import json
import time
import socketio
from aiohttp import web

# Socket.IO server
sio = socketio.AsyncServer(async_mode="aiohttp", cors_allowed_origins="*")
app = web.Application()
sio.attach(app)

# Config
with open("config.json") as f:
    CONFIG = json.load(f)

MODBUS_HOST = CONFIG["host"]
MODBUS_PORT = CONFIG["port"]
DEVICES = CONFIG["devices"]
READ_INTERVAL = CONFIG.get("interval", 3)


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


class ModbusConnection:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.sock = None

    def connect(self):
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(5)
        self.sock.connect((self.host, self.port))

    def ensure_connected(self):
        if self.sock is None:
            self.connect()
            return
        try:
            self.sock.setblocking(False)
            data = self.sock.recv(1, socket.MSG_PEEK)
            self.sock.setblocking(True)
            if not data:
                self.connect()
        except BlockingIOError:
            self.sock.setblocking(True)
        except Exception:
            self.connect()

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    def read_register(self, slave_id, addr, retries=2):
        for attempt in range(retries):
            pdu = struct.pack(">BBHH", slave_id, 0x03, addr, 0x0002)
            crc = crc16_modbus(pdu)
            request = pdu + struct.pack("<H", crc)

            # Flush buffer
            self.sock.setblocking(False)
            try:
                while self.sock.recv(1024):
                    pass
            except BlockingIOError:
                pass
            self.sock.setblocking(True)
            self.sock.settimeout(2)

            self.sock.sendall(request)

            try:
                response = self.sock.recv(1024)
            except socket.timeout:
                if attempt < retries - 1:
                    time.sleep(0.1)
                    continue
                return None, "Yanit yok (timeout)"

            if len(response) < 7:
                if attempt < retries - 1:
                    time.sleep(0.1)
                    continue
                return None, "Yanit cok kisa: " + str(len(response)) + " byte"

            resp_crc = struct.unpack("<H", response[-2:])[0]
            calc_crc = crc16_modbus(response[:-2])
            if resp_crc != calc_crc:
                if attempt < retries - 1:
                    time.sleep(0.1)
                    continue
                return None, "CRC hatasi"

            if response[0] != slave_id:
                return None, "Yanlis slave ID: beklenen " + str(slave_id) + " gelen " + str(response[0])

            if response[1] & 0x80:
                return None, "Modbus exception: " + str(response[2])

            value = struct.unpack(">f", response[3:7])[0]
            return value, None
        return None, "Bilinmeyen hata"

    def read_all_devices(self, devices):
        results = []
        self.ensure_connected()
        for i, dev in enumerate(devices):
            if i > 0:
                time.sleep(0.05)
            slave_id = dev["slave_id"]
            name = dev.get("name", "Slave " + str(slave_id))

            giris, giris_err = self.read_register(slave_id, 0x0000)
            time.sleep(0.05)
            ortam, ortam_err = self.read_register(slave_id, 0x0002)

            results.append({
                "slave_id": slave_id,
                "name": name,
                "giris_degeri": int(round(giris * 1000000)) if giris is not None else None,
                "ortam_sicakligi": round(ortam, 2) if ortam is not None else None,
                "error": giris_err or ortam_err,
            })
        return results


modbus = ModbusConnection(MODBUS_HOST, MODBUS_PORT)


async def modbus_loop():
    loop = asyncio.get_event_loop()
    while True:
        try:
            results = await loop.run_in_executor(None, modbus.read_all_devices, DEVICES)
        except Exception as e:
            modbus.close()
            results = [{
                "slave_id": dev["slave_id"],
                "name": dev.get("name", "Slave " + str(dev["slave_id"])),
                "giris_degeri": None,
                "ortam_sicakligi": None,
                "error": "Baglanti hatasi: " + str(e),
            } for dev in DEVICES]

        await sio.emit("modbus_data", results)
        print("Emit:", results)
        await asyncio.sleep(READ_INTERVAL)


@sio.event
async def connect(sid, environ):
    print("Client baglandi:", sid)


@sio.event
async def disconnect(sid):
    print("Client ayrildi:", sid)


async def on_startup(app):
    app["modbus_task"] = asyncio.create_task(modbus_loop())


async def on_cleanup(app):
    app["modbus_task"].cancel()
    modbus.close()


app.on_startup.append(on_startup)
app.on_cleanup.append(on_cleanup)

if __name__ == "__main__":
    port = CONFIG.get("server_port", 8080)
    print("Socket.IO server baslatiliyor - http://localhost:" + str(port))
    print("Modbus hedef: " + MODBUS_HOST + ":" + str(MODBUS_PORT))
    print("Cihaz sayisi: " + str(len(DEVICES)) + ", Okuma araligi: " + str(READ_INTERVAL) + "s")
    web.run_app(app, host="0.0.0.0", port=port)
