const net = require('net');

/**
 * Modbus TCP istemcisi başlatır ve belirli aralıklarla veri okur
 * @param {string} host - Modbus sunucu IP adresi
 * @param {number} port - Modbus sunucu portu
 * @param {number} interval - Veri okuma aralığı (ms)
 * @param {Function} onData - Float değeri alındığında çağrılacak callback
 */
function startModbusClient(host, port, interval = 1000, onData = null) {
	const client = new net.Socket();
	//01 03 00 00 00 02 C4 0B

	const requestBuffer = Buffer.from([
		0x01, 0x03, 0x00, 0x00, 0x00, 0x02, 0xc4, 0x0b,
	]);
	let intervalId = null;

	client.connect(port, host, () => {
		console.log('Connected');
		intervalId = setInterval(() => {
			client.write(requestBuffer);
		}, interval);
	});

	client.on('data', (data) => {
		if (data.length >= 9) {
			const floatData = data.slice(3, 7);
			if (floatData.length === 4) {
				const floatValue = floatData.readFloatBE(0);
				console.log('32-bit Float:', floatValue);
				if (onData) onData(floatValue);
			}
		} else {
			console.log(
				'Yanıt çok kısa, float parse edilemedi. Uzunluk:',
				data.length
			);
		}
	});

	client.on('error', (error) => {
		console.error('Error:', error);
	});

	client.on('close', () => {
		console.log('Connection closed');
		if (intervalId) clearInterval(intervalId);
	});

	return client;
}

// Kullanım örneği
const client = startModbusClient('192.168.1.201', 4196, 1000, (floatValue) => {
	console.log('Alınan değer:', floatValue);
});
