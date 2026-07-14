# Greenhouse Gateway Setup

The greenhouse gateway is a FastAPI service that reads the PLC, writes readings and alarm events to MySQL, and serves the dashboard through the Spring Boot proxy.

## First-time configuration

1. Create and activate the conda environment named `sensor`.
2. Copy `plc_web_hmi_v1_7/plc_web_hmi_v1_7/config.example.json` to `config.json` in the same directory.
3. Set `mysql_password` in the local `config.json`. Do not commit this file.
4. Keep `mode` set to `simulation` while validating the dashboard. For a real device, set `mode` to `plc`, then provide the correct `plc_ip`, `plc_port`, and `plc_id`.

## Start and verify

Run the root script after activating `sensor`:

```powershell
.\scripts\start-system.ps1 -InstallDeps
```

Later starts only need:

```powershell
.\scripts\start-system.ps1
```

It starts the gateway on `http://127.0.0.1:8000`. The dashboard uses the Spring Boot API at `http://127.0.0.1:8080/api/greenhouse/state`; it does not call the PLC gateway directly.

Use this command to stop all services:

```powershell
.\scripts\stop-system.ps1
```
