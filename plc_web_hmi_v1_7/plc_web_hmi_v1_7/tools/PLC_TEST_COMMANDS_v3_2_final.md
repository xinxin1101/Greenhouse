# PLC 综合测试脚本 v3.2 Final

## 本版变化

压缩机停机保护时间由 PLC 内部固定为 **180 秒**。

上位机程序：

- 不读取 `VW9500`
- 不显示停机时间
- 不提供停机时间修改
- 不干预压缩机内部保护逻辑

## 1. 读取实时状态

```powershell
python .\plc_control_test_v3_2_final.py monitor --json monitor_snapshot.json
```

读取内容：

- 实际温度、设定温度
- 实际湿度、设定湿度
- 实际 CO₂、设定 CO₂
- 高低温保护值
- 运行状态
- 报警状态
- 控制位状态

报警逻辑：

```text
1 = 正常
0 = 异常
```

## 2. 连续监控

```powershell
python .\plc_control_test_v3_2_final.py watch --interval 2
```

按 `Ctrl+C` 停止。

## 3. 设置温度、湿度和 CO₂

```powershell
python .\plc_control_test_v3_2_final.py setpoints `
  --temperature 25 `
  --humidity 60 `
  --co2 800 `
  --apply `
  --yes-i-understand
```

实际写入：

```text
VD264 温度目标
VD268 湿度目标
VD600 CO₂目标
VB4800 = 1
环境第1段 = 00:00～00:00
```

## 4. 系统总控制

开启：

```powershell
python .\plc_control_test_v3_2_final.py control system on --apply --yes-i-understand
```

关闭：

```powershell
python .\plc_control_test_v3_2_final.py control system off --apply --yes-i-understand
```

## 5. 压机独立控制

开启：

```powershell
python .\plc_control_test_v3_2_final.py control compressor on --apply --yes-i-understand
```

关闭：

```powershell
python .\plc_control_test_v3_2_final.py control compressor off --apply --yes-i-understand
```

压机停机后由 PLC 内部执行固定 180 秒保护，程序不做额外处理。

## 6. 紫外独立控制

```powershell
python .\plc_control_test_v3_2_final.py control uv on --apply --yes-i-understand
```

```powershell
python .\plc_control_test_v3_2_final.py control uv off --apply --yes-i-understand
```

## 7. CO₂独立控制

```powershell
python .\plc_control_test_v3_2_final.py control co2 on --apply --yes-i-understand
```

```powershell
python .\plc_control_test_v3_2_final.py control co2 off --apply --yes-i-understand
```

## 8. 初始化环境第1段

```powershell
python .\plc_control_test_v3_2_final.py prepare-env1 --apply --yes-i-understand
```

## 9. 初始化和控制新风

初始化：

```powershell
python .\plc_control_test_v3_2_final.py prepare-fan --apply --yes-i-understand
```

开启：

```powershell
python .\plc_control_test_v3_2_final.py fan on --apply --yes-i-understand
```

关闭：

```powershell
python .\plc_control_test_v3_2_final.py fan off --apply --yes-i-understand
```

## 10. 曲线测试

预览：

```powershell
python .\plc_control_test_v3_2_final.py curve `
  --temperature 20 25 `
  --humidity 50 60 `
  --co2 600 800 `
  --duration 60 `
  --interval 10 `
  --shape smooth
```

执行：

```powershell
python .\plc_control_test_v3_2_final.py curve `
  --temperature 20 25 `
  --humidity 50 60 `
  --co2 600 800 `
  --duration 60 `
  --interval 10 `
  --shape smooth `
  --apply `
  --yes-i-understand
```
