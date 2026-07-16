# Greenhouse

作物生长环境与表型关联分析系统。项目整合了传感器采集、温室 PLC 环境控制、报警记录、历史数据查询、趋势曲线和点云表型展示。

## 功能概览

- 传感器数据展示：温度、湿度、光照等节点采集数据。
- 温室 PLC 运行总览：目标温度、湿度、CO2 写入，设备开关控制，PLC 实际输出状态反馈。
- 曲线控制：按温度、湿度、CO2 创建变化曲线，并对比预设曲线和实际曲线。
- 历史数据：按时间范围查询温室环境数据，绘制趋势图，分页查看检测数值，导出 CSV。
- 报警记录：查看 PLC 报警事件，支持当前报警确认、全部未确认确认、单条确认。
- 点云展示：通过后端读取本地点云文件，前端进行三维可视化。
- 一键启动：根目录脚本同时启动前端、Spring Boot 后端、FastAPI PLC 网关和 Java 采集端。

## 目录结构

```text
backend/                         Spring Boot API 服务
frontend/                        Vue 3 前端界面
plc_web_hmi_v1_7/plc_web_hmi_v1_7 FastAPI 温室 PLC 网关
JavaSDKV2.2.2/                   传感器采集 SDK 与采集端
docs/                            运行说明、接口说明和技术文档
scripts/                         启动、停止和环境检查脚本
start-system.bat                 Windows 一键启动入口
stop-system.bat                  Windows 一键停止入口
```

## 数据库表

项目默认使用 MySQL 数据库 `sensor`。核心表包括：

- `sensor_data_two`：无线传感器环境数据。
- `point_cloud`：点云文件索引。
- `greenhouse_plc_data`：温室 PLC 环境数据、目标设定和设备状态。
- `greenhouse_alarm_events`：温室 PLC 报警事件。

详细建表和运行步骤见 [docs/setup-from-github.md](docs/setup-from-github.md)。

## 首次运行

请先安装 Git、JDK 21、Maven、Node.js 20+、MySQL 8，并准备 conda 环境 `sensor`。

```powershell
git clone https://github.com/xinxin1101/Greenhouse.git
cd Greenhouse
conda activate sensor
.\scripts\start-system.ps1 -InstallDeps
```

如果 PowerShell 阻止脚本执行，可以使用：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-system.ps1 -InstallDeps
```

启动完成后访问：

```text
http://localhost:5173
```

## 日常启动和停止

启动：

```powershell
.\scripts\start-system.ps1
```

或双击：

```text
start-system.bat
```

停止：

```powershell
.\scripts\stop-system.ps1
```

或双击：

```text
stop-system.bat
```

## 温室 PLC 配置

首次启动前，将：

```text
plc_web_hmi_v1_7/plc_web_hmi_v1_7/config.example.json
```

复制为：

```text
plc_web_hmi_v1_7/plc_web_hmi_v1_7/config.json
```

然后按本机情况填写 MySQL 密码。验证界面功能时建议保持：

```json
{
  "mode": "simulation"
}
```

连接真实 PLC 时再改为 `plc` 模式，并填写正确的 PLC IP、端口和 PLC 编号。`config.json` 包含本地密码和设备地址，已被 Git 忽略，不要提交到仓库。

## 常用地址

```text
前端页面：http://localhost:5173
Spring Boot API：http://localhost:8080
温室 PLC 网关：http://localhost:8000
传感器采集监听端口：2404
```

## 文档

- [完整拉取运行指南](docs/setup-from-github.md)
- [温室 PLC 网关配置](docs/greenhouse-setup.md)
- [技术说明](docs/technical-manual.md)
- [接口说明](docs/api.md)

## Git 忽略内容

仓库不会提交以下可再生成或本地敏感内容：

- `frontend/node_modules`
- `frontend/dist`
- `backend/target`
- `logs`
- `frontend/tsconfig.tsbuildinfo`
- `plc_web_hmi_v1_7/plc_web_hmi_v1_7/config.json`
- Java / Maven / IDE 生成目录

首次运行使用 `.\scripts\start-system.ps1 -InstallDeps` 即可重新生成依赖和构建目录。
