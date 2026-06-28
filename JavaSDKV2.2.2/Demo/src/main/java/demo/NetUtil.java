package demo;

import java.net.Inet4Address;
import java.net.InetAddress;
import java.net.NetworkInterface;
import java.util.Enumeration;

public class NetUtil {

    // 获取当前局域网 IPv4
    public static String getLocalIp() {

        try {
            Enumeration<NetworkInterface> interfaces =
                    NetworkInterface.getNetworkInterfaces();

            while (interfaces.hasMoreElements()) {

                NetworkInterface ni = interfaces.nextElement();

                // 跳过虚拟网卡/未启用网卡
                if (!ni.isUp() || ni.isLoopback() || ni.isVirtual()) {
                    continue;
                }

                Enumeration<InetAddress> addresses =
                        ni.getInetAddresses();

                while (addresses.hasMoreElements()) {

                    InetAddress addr = addresses.nextElement();

                    // 只要 IPv4
                    if (addr instanceof Inet4Address) {

                        String ip = addr.getHostAddress();

                        // 过滤 127.x 和虚拟网段
                        if (!ip.startsWith("127.")
                                && !ip.startsWith("172.")
                                && !ip.startsWith("169.254")) {

                            return ip;
                        }
                    }
                }
            }

        } catch (Exception e) {
            e.printStackTrace();
        }

        return "UNKNOWN";
    }
}