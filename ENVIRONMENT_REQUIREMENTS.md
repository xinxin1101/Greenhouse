# Environment Requirements

本文档说明 Greenhouse 项目的完整运行环境。项目不是纯 Python 应用，依赖分为系统软件、Python PLC 网关、Node.js 前端、Maven Java 后端和 Java 采集端。

## 1. 系统软件

建议在 Windows + PowerShell 环境运行。

| 软件 | 建议版本 | 用途 | 验证命令 |
| --- | --- | --- | --- |
| Git | 2.40+ | 拉取和提交代码 | `git --version` |
| Conda | Miniconda 或 Anaconda | 创建 Python 环境 `sensor` | `conda --version` |
| Python | 3.11 | FastAPI 温室 PLC 网关 | `python --version` |
| JDK | 21 | Spring Boot 后端 | `java -version` |
| Maven | 3.9+ | 后端和采集端依赖管理 | `mvn -version` |
| Node.js | 20+ | Vue 前端 | `node -v` |
| npm | 随 Node.js 安装 | 前端依赖安装 | `npm -v` |
| MySQL | 8.x | 业务数据存储 | `mysql --version` |

## 2. Python 环境

推荐直接使用仓库根目录的 `environment.yml` 创建 conda 环境：

```powershell
conda env create -f environment.yml
conda activate sensor
```

如果环境已经存在，可更新：

```powershell
conda env update -f environment.yml --prune
conda activate sensor
```

Python 依赖同时记录在：

```text
plc_web_hmi_v1_7/plc_web_hmi_v1_7/requirements.txt
```

也可以手动安装：

```powershell
conda create -n sensor python=3.11 -y
conda activate sensor
python -m pip install -r plc_web_hmi_v1_7/plc_web_hmi_v1_7/requirements.txt
```

当前 Python 依赖：

| 包 | 版本范围 | 用途 |
| --- | --- | --- |
| `python-snap7` | `2.1.0` | 连接 Siemens PLC |
| `fastapi` | `>=0.115,<1` | PLC 网关 API |
| `uvicorn[standard]` | `>=0.34,<1` | FastAPI 服务运行器 |
| `pydantic` | `>=2.10,<3` | 配置和数据模型 |
| `PyMySQL` | `>=1.1,<2` | 写入 MySQL |
| `cryptography` | `42.0.8` | MySQL 认证相关加密支持 |

## 3. 前端环境

前端目录：

```text
frontend/
```

依赖由 `frontend/package.json` 和 `frontend/package-lock.json` 锁定。首次安装：

```powershell
cd frontend
npm install
```

主要依赖：

| 包 | 版本 | 用途 |
| --- | --- | --- |
| `vue` | `3.5.22` | 前端框架 |
| `vite` | `8.0.16` | 开发服务器和构建工具 |
| `typescript` | `5.6.3` | 类型检查 |
| `vue-tsc` | `3.1.5` | Vue 类型检查 |
| `axios` | `1.18.0` | HTTP 请求 |
| `echarts` | `5.5.1` | 趋势图表 |
| `three` | `0.160.0` | 点云三维展示 |

构建验证：

```powershell
cd frontend
npm run build
```

## 4. 后端环境

后端目录：

```text
backend/
```

后端使用 Spring Boot 3.5.7，要求 JDK 21。依赖由 `backend/pom.xml` 管理。

主要依赖：

| 依赖 | 版本 | 用途 |
| --- | --- | --- |
| `spring-boot-starter-web` | `3.5.7` | REST API |
| `mysql-connector-j` | `8.0.33` | MySQL 驱动 |
| `spring-boot-starter-test` | `3.5.7` | 测试 |

构建验证：

```powershell
cd backend
mvn -q -DskipTests package
```

## 5. Java 采集端环境

采集端目录：

```text
JavaSDKV2.2.2/Demo/
```

采集端使用 Maven 编译，源码目标版本为 Java 8。当前系统一键脚本会用本机 `java` 命令启动，建议安装 JDK 21 即可兼容运行。

主要依赖：

| 依赖 | 版本 | 用途 |
| --- | --- | --- |
| `mysql-connector-java` | `8.0.33` | 写入 MySQL |
| `RSNetDevice-2.2.2.jar` | `2.2.2` | 无线传感器 SDK |

构建验证：

```powershell
cd JavaSDKV2.2.2/Demo
mvn -q compile
```

## 6. MySQL 环境

默认数据库：

```text
host: 127.0.0.1
port: 3306
database: sensor
username: root
```

本地密码需要分别配置：

- Spring Boot：`backend/src/main/resources/application.yml`
- PLC 网关：复制 `plc_web_hmi_v1_7/plc_web_hmi_v1_7/config.example.json` 为 `config.json` 后填写 `mysql_password`

核心数据表：

- `sensor_data_two`
- `point_cloud`
- `greenhouse_plc_data`
- `greenhouse_alarm_events`

完整建表说明见：

```text
docs/setup-from-github.md
```

## 7. 一键安装依赖并启动

在仓库根目录执行：

```powershell
conda activate sensor
.\scripts\start-system.ps1 -InstallDeps
```

脚本会自动完成：

- `npm install`
- `mvn -q -DskipTests package`
- `mvn -q compile`
- `python -m pip install -r plc_web_hmi_v1_7/plc_web_hmi_v1_7/requirements.txt`
- 启动 FastAPI PLC 网关、Spring Boot 后端、Vue 前端和 Java 采集端

日常启动：

```powershell
.\scripts\start-system.ps1
```

停止：

```powershell
.\scripts\stop-system.ps1
```
