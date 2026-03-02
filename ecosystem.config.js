module.exports = {
  apps: [
    {
      name: "modbus-server",
      script: "server.py",
      interpreter: "./venv/bin/python3",
      cwd: __dirname,
      autorestart: true,
      max_restarts: 10,
      restart_delay: 3000,
    },
  ],
};
