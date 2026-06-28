package demo;

public class Application {

    public static void main(String[] args) {
        String currentIp = NetUtil.getLocalIp();
        System.out.println("=========================================");
        System.out.println("         温室数据采集系统 启动中...        ");
        System.out.println("=========================================");

        try {
            // 实例化业务类并启动
            DataCollector collector = new DataCollector();
            collector.startListen();

            // 为了防止主线程退出，加一个无限循环休眠（因为底层的 RSServer 是后台线程）
            while (true) {
                Thread.sleep(10000);
            }

        } catch (Exception e) {
            System.err.println("!!! 系统启动发生致命错误 !!!");
            System.err.println("错误原因: " + e.getMessage());
            e.printStackTrace();
        }
    }
}