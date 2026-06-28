# Sensor Platform

Engineering rewrite of the crop environment and phenotype visualization system.

## Modules

- `backend`: Spring Boot API service. It reads MySQL data written by the existing Java SDK collector and serves PLY files.
- `frontend`: Vue 3 dashboard. It renders sensor charts and Three.js point clouds.

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

## One-Click Local Run

- Start: double-click `start-system.bat`
- Stop: double-click `stop-system.bat`
- First run on a new computer: `.\scripts\start-system.ps1 -InstallDeps`
