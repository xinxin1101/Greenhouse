package demo;

import com.jnrsmcu.sdk.netdevice.IDataListener;
import com.jnrsmcu.sdk.netdevice.LoginData;
import com.jnrsmcu.sdk.netdevice.NodeData;
import com.jnrsmcu.sdk.netdevice.RSServer;
import com.jnrsmcu.sdk.netdevice.RealTimeData;
import com.jnrsmcu.sdk.netdevice.StoreData;
import com.jnrsmcu.sdk.netdevice.TelecontrolAck;
import com.jnrsmcu.sdk.netdevice.TimmingAck;
import com.jnrsmcu.sdk.netdevice.TransDataAck;
import com.jnrsmcu.sdk.netdevice.WriteParamAck;
import com.jnrsmcu.sdk.netdevice.ParamIdsData;
import com.jnrsmcu.sdk.netdevice.ParamData;

import java.util.Date;
import java.text.SimpleDateFormat;

public class Test {
    // 缓存变量
    private static float curTemp = 0;
    private static float curHum = 0;

    public static void main(String[] args) throws Exception {
        // 1. 初始化服务器（端口2404）
        RSServer rsServer = RSServer.Initiate(2404);
        if (rsServer == null) {
            System.err.println("SDK初始化失败，请检查根目录下的 param.dat 文件！");
            return;
        }

        // 2. 添加监听器
        rsServer.addDataListener(new IDataListener() {
            @Override
            public void receiveRealtimeData(RealTimeData data) {
                SimpleDateFormat sdf = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss");
                System.out.println("\n======= 实时数据监测 (" + sdf.format(new Date()) + ") =======");
                System.out.println("设备地址: " + data.getDeviceId());

                for (NodeData nd : data.getNodeList()) {
                    int nodeId = nd.getNodeId();

                    if (nodeId == 1) {
                        // 节点 1 解析温湿度
                        curTemp = nd.getTem();
                        curHum = nd.getHum();
                        System.out.println("[节点 1] 温度: " + curTemp + " °C, 湿度: " + curHum + " %");
                    }
                    else if (nodeId == 2) {
                        // 节点 2 解析光照
                        // 1. 获取 32 位无符号原始数
                        long raw32 = nd.getUnSignedInt32Value();
                        // 2. 计算光照（根据售后指导：原始数 * 10）
                        float lightLux = raw32 * 10.0f;

                        System.out.println("[节点 2] 原始 32 位无符号数: " + raw32);
                        System.out.println("[节点 2] 计算结果 (原始数 * 10): " + lightLux + " Lux");
                    }
                }
                System.out.println("=====================================================");
            }

            @Override
            public void receiveLoginData(LoginData data) {
                System.out.println(">>> 设备上线: " + data.getDeviceId());
            }

            // 以下方法留空
            @Override public void receiveStoreData(StoreData data) {}
            @Override public void receiveTimmingAck(TimmingAck data) {}
            @Override public void receiveTelecontrolAck(TelecontrolAck data) {}
            @Override public void receiveParamIds(ParamIdsData data) {}
            @Override public void receiveParam(ParamData data) {}
            @Override public void receiveWriteParamAck(WriteParamAck data) {}
            @Override public void receiveTransDataAck(TransDataAck data) {}
        });

        // 3. 启动服务
        rsServer.start();
        System.out.println("测试服务已启动，监听端口: 2404 (等待硬件数据上报...)");

        // 4. 阻塞主线程
        while (true) {
            Thread.sleep(1000);
        }
    }
}