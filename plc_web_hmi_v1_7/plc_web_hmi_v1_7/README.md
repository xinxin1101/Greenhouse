# PLC Web HMI v1.7

## 新增：系统总控制与紫外双向互锁

规则：

```text
紫外已开启 → 系统总控制不能开启
系统总控制已开启 → 紫外不能开启
```

当前已开启的一方始终可以关闭。互锁同时在两层执行：

1. 前端将对方开关置为不可用，并显示互锁原因；
2. 后端再次校验，避免绕过网页直接调用接口。

## 新增：异常突发弹窗

四个报警输入仍为：

```text
1 = 正常
0 = 异常
```

当某项从正常突然变为异常时，任意页面都会弹出异常窗口，显示：

- 异常名称
- 异常内容
- 发生时间

同一个异常事件在页面切换时不会重复弹出。

## 新增：持久化异常日志

实时总览的“异常情况”区域增加“异常日志”按钮。

日志样式：

- 当前未解决：红色
- 已恢复：普通样式，不标红

每条日志包含发生时间和恢复时间。异常日志保存在 MySQL 的：

```text
sensor.greenhouse_alarm_events
```

因此程序重启后仍可查看，也可供主平台统一查询。

## 数据存储

每次 PLC 环境轮询都会写入 MySQL 的：

```text
sensor.greenhouse_plc_data
```

写入字段为 `plc_id`、`temperature`、`humidity`、`co2`、`light_on` 和
`record_time`。历史趋势、历史查询和 CSV 导出均从这张 MySQL 表读取。

PLC 报警事件会写入 `sensor.greenhouse_alarm_events`，包含报警代码、名称、
发生时间、确认状态、当前是否激活及恢复时间。

连接配置位于 `config.json`。部署时可设置环境变量
`GREENHOUSE_MYSQL_PASSWORD` 覆盖文件中的 `mysql_password`。

## 启动

```powershell
conda activate sensor
cd C:\Users\lyh\Desktop\plc_web_hmi_v1_7
python -m pip install -r requirements.txt
python run.py
```
