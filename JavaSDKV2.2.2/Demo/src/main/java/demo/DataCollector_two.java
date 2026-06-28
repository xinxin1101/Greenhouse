package demo;

import java.net.Inet4Address;
import java.net.InetAddress;
import java.net.NetworkInterface;
import java.sql.*;
import java.util.*;

import com.jnrsmcu.sdk.netdevice.*;

import static demo.NetUtil.getLocalIp;

public class DataCollector_two {

    private static final String DB_URL =
            "jdbc:mysql://127.0.0.1:3306/sensor?useUnicode=true&characterEncoding=utf8&serverTimezone=Asia/Shanghai";

    private static final String USER = "root";
    private static final String PASS = "269756";

    private static final long SAVE_INTERVAL = 60 * 1000L;

    private RSServer rsServer;

    private float currentTemp = 0;
    private float currentHum = 0;
    private float currentLight = 0;

    private final Map<String, Long> lastSaveMap = new HashMap<>();

    public void startListen() throws Exception {

        Class.forName("com.mysql.cj.jdbc.Driver");

        String ip = getLocalIp();

        System.out.println("=====================================");
        System.out.println("当前服务器IP: " + ip);
        System.out.println("监听端口: 2404");
        System.out.println("=====================================");

        rsServer = RSServer.Initiate(
                2404,
                "E:/Edge_download/JavaSDKV2.2.2/JavaSDKV2.2.2/Demo/param.dat"
        );

        if (rsServer == null) {
            throw new Exception("SDK 初始化失败");
        }

        rsServer.addDataListener(new IDataListener() {

            @Override
            public void receiveRealtimeData(RealTimeData data) {

                String deviceId = String.valueOf(data.getDeviceId());

                updateDeviceOnline(deviceId);

                for (NodeData nd : data.getNodeList()) {

                    if (nd.getNodeId() == 1) {
                        currentTemp = nd.getTem();
                        currentHum = nd.getHum();
                    }

                    if (nd.getNodeId() == 2) {
                        currentLight = nd.getUnSignedInt32Value();
                    }
                }

                saveSensorData(
                        deviceId,
                        currentTemp,
                        currentHum,
                        currentLight,
                        new Date()
                );
            }

            @Override
            public void receiveLoginData(LoginData data) {
                System.out.println("设备上线: " + data.getDeviceId());
            }
        }