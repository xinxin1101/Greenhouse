# Sensor Platform

Engineering rewrite of the crop environment and phenotype visualization system.

## Modules

- `backend`: Spring Boot API service. It reads MySQL data, serves PLY files, and proxies greenhouse operations to the PLC service.
- `frontend`: Vue 3 dashboard. It renders sensor charts, Three.js point clouds, and greenhouse controls.
- `plc_web_hmi_v1_7/plc_web_hmi_v1_7`: FastAPI PLC gateway. It writes greenhouse measurements and alarm events to MySQL.

The data collector remains in the original Java SDK demo project and is not modified here.

## Data Sources

Sensor table:

```text
sensor_data_two(device_id, node_id, temperature, humidity, light_intensity, record_time)
```

Point cloud table:

```text
point_cloud(id, record_time, file_name)
```

## Documentation

- [Technical Manual](docs/technical-manual.md)
- [API Draft](docs/api.md)
- [GitHub Pull & Run Guide](docs/setup-from-github.md)
- [Greenhouse Gateway Setup](docs/greenhouse-setup.md)

## One-Click Local Run

- Start: double-click `start-system.bat`
- Stop: double-click `stop-system.bat`
- First run on a new computer: activate conda environment `sensor`, then run `.\scripts\start-system.ps1 -InstallDeps`

Before its first startup, copy `plc_web_hmi_v1_7/plc_web_hmi_v1_7/config.example.json` to `config.json` and fill in the local MySQL password. The local `config.json` is intentionally ignored by Git.

The one-click script starts the FastAPI greenhouse gateway on port `8000` as well as the frontend, backend, and collector. Its example PLC configuration uses `simulation` mode; change the local `config.json` to the real PLC settings only when the device is ready.
