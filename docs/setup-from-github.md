# GitHub 拉取后完整运行指南

本文档说明在一台新电脑上从 GitHub 拉取本项目后，如何恢复依赖、配置数据库，并完整启动前端、后端和 Java 数据采集模块。

## 1. 环境准备

请先安装并确认以下软件可在命令行中使用：

| 软件 | 建议版本 | 验证命令 |
| --- | --- | --- |
| Git | 任意较新版本 | `git --version` |
| JDK | 21 | `java -version` |
| Maven | 3.9+ | `mvn -version` |
| Node.js | 20+ | `node -v` |
| npm | 随 Node.js 安装 | `npm -v` |
| MySQL | 8.x | `mysql --version` |

如果使用 Windows，建议用 PowerShell 执行下面的命令。

## 2. 拉取代码

```powershell
git clone https://github.com/xinxin1101/Greenhouse.git
cd Greenhouse
```

如果你把项目 fork 或复制到了其他仓库，请替换上面的 GitHub URL。

## 3. 准备 MySQL 数据库

项目默认连接本机 MySQL：

```text
地址：127.0.0.1:3306
数据库：sensor
用户名：root
密码：269756
```

如果你的 MySQL 密码不是 `269756`，需要在后面的配置步骤中修改。

登录 MySQL：

```powershell
mysql -u root -p
```

创建数据库和数据表：

```sql
CREATE DATABASE IF NOT EXISTS sensor
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE sensor;

CREATE TABLE IF NOT EXISTS sensor_data_two (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  device_id VARCHAR(64) NOT NULL,
  node_id INT NOT NULL,
  temperature DOUBLE,
  humidity DOUBLE,
  light_intensity DOUBLE,
  record_time DATETIME NOT NULL,
  INDEX idx_sensor_record_time (record_time)
);

CREATE TABLE IF NOT EXISTS point_cloud (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  record_time DATETIME NOT NULL,
  file_name VARCHAR(255) NOT NULL,
  INDEX idx_point_cloud_record_time (record_time)
);
```

如果暂时没有真实传感器，可以先插入一条测试数据：

```sql
INSERT INTO sensor_data_two
  (device_id, node_id, temperature, humidity, light_intensity, record_time)
VALUES
  ('test-device', 1, 25.6, 68.2, 1200, NOW());
```

## 4. 配置后端

打开：

```text
backend/src/main/resources/application.yml
```

检查并按本机情况修改：

```yaml
app:
  datasource:
    url: jdbc:mysql://127.0.0.1:3306/sensor?useUnicode=true&characterEncoding=utf8&serverTimezone=Asia/Shanghai
    username: root
    password: "269756"
  point-cloud:
    directory: E:/study/new_sensor/pointCloud
```

必须确认：

- `datasource.password` 与本机 MySQL 密码一致。
- `point-cloud.directory` 是本机真实存在的点云 `.ply` 文件目录。
- 如果暂时没有点云文件，也请先创建一个空目录，否则系统状态面板会提示点云目录异常。

例如：

```powershell
mkdir E:\study\new_sensor\pointCloud
```

## 5. 恢复被 Git 忽略的依赖和构建目录

GitHub 仓库不会上传 `node_modules`、`dist`、`target`、`logs` 等可再生成内容。首次运行前需要安装依赖。

推荐直接执行：

```powershell
.\scripts\start-system.ps1 -InstallDeps
```

这个命令会自动完成：

- 安装前端 npm 依赖，重新生成 `frontend/node_modules`。
- 下载并准备后端 Maven 依赖，重新生成 `backend/target`。
- 编译 Java SDK 采集模块，重新生成 `JavaSDKV2.2.2/Demo/target`。
- 启动后端、前端和采集模块。

如果 PowerShell 阻止脚本执行，可以用：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-system.ps1 -InstallDeps
```

也可以双击根目录的：

```text
start-system.bat
```

首次运行建议仍然在 PowerShell 中加上 `-InstallDeps`，方便看到日志。

## 6. 启动系统

首次依赖安装完成后，以后正常启动可以执行：

```powershell
.\scripts\start-system.ps1
```

启动脚本会尝试启动：

| 模块 | 端口 | 说明 |
| --- | --- | --- |
| Spring Boot 后端 | `8080` | 提供 `/api` 接口 |
| Vue 前端 | `5173` | 浏览器访问入口 |
| FastAPI 温室 PLC 网关 | `8000` | 提供 PLC 状态、控制、历史和报警接口 |
| Java 采集模块 | `2404` | 接收传感器设备上报 |

启动成功后访问：

```text
http://localhost:5173
```

后端接口验证地址：

```text
http://localhost:8080/api/sensor/summary
http://localhost:8080/api/system/status
```

## 7. 停止系统

执行：

```powershell
.\scripts\stop-system.ps1
```

或者双击：

```text
stop-system.bat
```

停止脚本会根据 `.runtime` 中记录的进程号，以及 `8080`、`5173`、`2404` 端口占用情况停止相关进程。

## 8. 点云数据说明

点云文件本身不放在数据库中，数据库 `point_cloud.file_name` 只保存文件名，后端会到 `application.yml` 中配置的 `point-cloud.directory` 目录查找文件。

如果目录中有文件：

```text
E:/study/new_sensor/pointCloud/Stage_Flowering.ply
```

那么数据库中可以插入：

```sql
INSERT INTO point_cloud (record_time, file_name)
VALUES (NOW(), 'Stage_Flowering.ply');
```

前端加载点云时，会通过后端接口读取该文件。

## 9. 常见问题

### 9.1 页面能打开，但没有传感器数据

检查 MySQL 中是否有数据：

```sql
USE sensor;
SELECT * FROM sensor_data_two ORDER BY record_time DESC LIMIT 5;
```

如果没有真实设备，可以先插入第 3 节的测试数据验证页面。

### 9.2 后端启动失败，提示数据库连接失败

检查：

- MySQL 服务是否已启动。
- `backend/src/main/resources/application.yml` 中的用户名和密码是否正确。
- `sensor` 数据库是否已经创建。

### 9.3 前端依赖不存在

如果提示 `frontend\node_modules does not exist`，执行：

```powershell
.\scripts\start-system.ps1 -InstallDeps
```

或者手动安装：

```powershell
cd frontend
npm install
```

### 9.4 采集模块未监听 2404

检查：

- `JavaSDKV2.2.2/Demo/param.dat` 是否存在。
- 端口 `2404` 是否被其他程序占用。
- `logs/collector.err.log` 是否有错误信息。

如果只是想先看前端和后端，可以跳过采集模块：

```powershell
.\scripts\start-system.ps1 -SkipCollector
```

### 9.5 点云目录异常

检查 `application.yml`：

```yaml
app:
  point-cloud:
    directory: E:/study/new_sensor/pointCloud
```

确认该目录存在，并且数据库 `point_cloud.file_name` 中记录的是文件名，而不是完整路径。

## 10. 手动启动方式

如果不使用一键脚本，可以分别启动。

后端：

```powershell
cd backend
mvn spring-boot:run
```

前端：

```powershell
cd frontend
npm install
npm run dev
```

采集模块：

```powershell
cd JavaSDKV2.2.2\Demo
mvn compile
mvn dependency:build-classpath "-Dmdep.outputFile=target/classpath.txt"
```

然后按 `scripts/start-system.ps1` 中的 classpath 逻辑启动 `demo.Application`。一般情况下建议直接使用一键脚本，避免手动拼接 classpath。
