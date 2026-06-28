package demo;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.io.File;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import java.util.Date;

import com.jnrsmcu.sdk.netdevice.IDataListener;
import com.jnrsmcu.sdk.netdevice.LoginData;
import com.jnrsmcu.sdk.netdevice.NodeData;
import com.jnrsmcu.sdk.netdevice.ParamData;
import com.jnrsmcu.sdk.netdevice.ParamIdsData;
import com.jnrsmcu.sdk.netdevice.RSServer;
import com.jnrsmcu.sdk.netdevice.RealTimeData;
import com.jnrsmcu.sdk.netdevice.StoreData;
import com.jnrsmcu.sdk.netdevice.TelecontrolAck;
import com.jnrsmcu.sdk.netdevice.TimmingAck;
import com.jnrsmcu.sdk.netdevice.TransDataAck;
import com.jnrsmcu.sdk.netdevice.WriteParamAck;

public class DataCollector {

    private static final String DB_URL = "jdbc:mysql://127.0.0.1:3306/sensor?useUnicode=true&characterEncoding=utf8&serverTimezone=Asia/Shanghai";
    private static final String USER = "root";
    private static final String PASS = "269756";

    // 设定存储间隔，防止数据库过大（10分钟存一次）
    private static final long SAVE_INTERVAL_MS = 10 * 60 * 1000L;

    private RSServer rsServer;

    // 用于缓存每个设备最新的数据，实现多节点数据对齐
    private float currentTemp = 0;
    private float currentHum = 0;
    private float currentLight = 0;
    private final Map<String, Long> lastSaveTimeMap = new HashMap<>();

    public void startListen() throws Exception {
        Class.forName("com.mysql.cj.jdbc.Driver");
        System.out.println("=> [SYSTEM] MySQL Driver Loaded");

        rsServer = RSServer.Initiate(2404, resolveParamFile());
        if (rsServer == null) {
            throw new Exception("SDK初始化失败，请确保 param.dat 在项目根目录");
        }

        rsServer.addDataListener(new IDataListener() {
            @Override
            public void receiveRealtimeData(RealTimeData data) {
                String deviceId = String.valueOf(data.getDeviceId());

                for (NodeData nd : data.getNodeList()) {
                    if (nd.getNodeId() == 1) {
                        // 节点 1 获取温湿度
                        currentTemp = nd.getTem();
                        currentHum = nd.getHum();
                    } else if (nd.getNodeId() == 2) {
                        // 节点 2 获取光照：按照售后方案 32位无符号数 * 10
                        long rawValue = nd.getUnSignedInt32Value();
                        currentLight = rawValue;
                    }
                }

                // 尝试保存（内部会判断时间间隔）
                saveToDatabase(deviceId, currentTemp, currentHum, currentLight, new Date());
            }

            @Override
            public void receiveStoreData(StoreData data) {
                // 存储数据通常也是按节点上报，逻辑与实时一致
                for (NodeData nd : data.getNodeList()) {
                    if (nd.getNodeId() == 1) {
                        currentTemp = nd.getTem();
                        currentHum = nd.getHum();
                    } else if (nd.getNodeId() == 2) {
                        currentLight = nd.getUnSignedInt32Value();
                    }
                    saveToDatabase(String.valueOf(data.getDeviceId()), currentTemp, currentHum, currentLight, nd.getRecordTime());
                }
            }

            @Override
            public void receiveLoginData(LoginData data) {
                System.out.println("=> [LOGIN] 设备登录: " + data.getDeviceId());
            }

            @Override public void receiveTimmingAck(TimmingAck data) {}
            @Override public void receiveTelecontrolAck(TelecontrolAck data) {}
            @Override public void receiveParamIds(ParamIdsData data) {}
            @Override public void receiveParam(ParamData data) {}
            @Override public void receiveWriteParamAck(WriteParamAck data) {}
            @Override public void receiveTransDataAck(TransDataAck data) {}
        });

        rsServer.start();
        System.out.println("=> [RUNNING] 正在监听端口 2404...");
    }

    private void saveToDatabase(String deviceId, float temp, float hum, float light, Date recordTime) {
        long now = System.currentTimeMillis();

        // 只有数据齐全（且达到时间间隔）才保存
        if (temp == 0 && hum == 0) return;
        if (!shouldSaveNow(deviceId, now)) return;

        String sql = "INSERT INTO sensor_data_two (device_id, node_id, temperature, humidity, light_intensity, record_time) VALUES (?, ?, ?, ?, ?, ?)";

        try (Connection conn = DriverManager.getConnection(DB_URL, USER, PASS);
             PreparedStatement pstmt = conn.prepareStatement(sql)) {

            pstmt.setString(1, deviceId);
            pstmt.setInt(2, 1); // 统一记录为节点1的数据行
            pstmt.setFloat(3, temp);
            pstmt.setFloat(4, hum);
            pstmt.setFloat(5, light);
            pstmt.setTimestamp(6, new Timestamp(recordTime.getTime()));

            if (pstmt.executeUpdate() > 0) {
                System.out.printf(Locale.US, "=> [DB OK] 设备:%s | 温度:%.1f | 湿度:%.1f | 光照:%.1f Lux\n",
                        deviceId, temp, hum, light);
            }
        } catch (SQLException e) {
            System.err.println("=> [DB ERROR] " + e.getMessage());
        }
    }

    private synchronized boolean shouldSaveNow(String deviceId, long now) {
        Long last = lastSaveTimeMap.get(deviceId);
        if (last != null && (now - last) < SAVE_INTERVAL_MS) {
            return false;
        }
        lastSaveTimeMap.put(deviceId, now);
        return true;
    }

    private String resolveParamFile() throws Exception {
        String userDir = System.getProperty("user.dir");
        String[] candidates = {
                userDir + File.separator + "param.dat",
                userDir + File.separator + "Demo" + File.separator + "param.dat",
                userDir + File.separator + "JavaSDKV2.2.2" + File.separator + "Demo" + File.separator + "param.dat"
        };

        for (String candidate : candidates) {
            File file = new File(candidate);
            if (file.isFile()) {
                return file.getAbsolutePath();
            }
        }

        throw new Exception("找不到 param.dat，请确认采集模块目录中存在该文件");
    }
}
