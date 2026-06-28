package com.example.sensorplatform.service;

import com.example.sensorplatform.model.ServiceStatus;
import com.example.sensorplatform.model.SystemStatus;
import com.example.sensorplatform.repository.JdbcConnectionFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.net.InetSocketAddress;
import java.net.Socket;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.time.LocalDateTime;

@Service
public class SystemStatusService {
    private static final String LOCALHOST = "127.0.0.1";
    private static final int COLLECTOR_PORT = 2404;
    private static final int CONNECT_TIMEOUT_MS = 800;

    private final JdbcConnectionFactory connectionFactory;
    private final Path pointCloudDirectory;

    public SystemStatusService(
            JdbcConnectionFactory connectionFactory,
            @Value("${app.point-cloud.directory}") String pointCloudDirectory
    ) {
        this.connectionFactory = connectionFactory;
        this.pointCloudDirectory = Path.of(pointCloudDirectory).toAbsolutePath().normalize();
    }

    public SystemStatus current() {
        ServiceStatus api = new ServiceStatus("Spring Boot 后端", true, "API 服务已响应");
        ServiceStatus database = checkDatabase();
        ServiceStatus collector = checkCollector();
        ServiceStatus pointCloud = checkPointCloudDirectory();
        boolean healthy = api.running() && database.running() && collector.running() && pointCloud.running();
        return new SystemStatus(healthy, LocalDateTime.now(), api, database, collector, pointCloud);
    }

    private ServiceStatus checkDatabase() {
        try (Connection conn = connectionFactory.open();
             PreparedStatement stmt = conn.prepareStatement("SELECT 1");
             ResultSet rs = stmt.executeQuery()) {
            return new ServiceStatus("MySQL 数据库", rs.next(), "数据库连接正常");
        } catch (Exception e) {
            return new ServiceStatus("MySQL 数据库", false, e.getMessage());
        }
    }

    private ServiceStatus checkCollector() {
        try (Socket socket = new Socket()) {
            socket.connect(new InetSocketAddress(LOCALHOST, COLLECTOR_PORT), CONNECT_TIMEOUT_MS);
            return new ServiceStatus("Java 采集模块", true, "端口 " + COLLECTOR_PORT + " 已监听");
        } catch (Exception e) {
            return new ServiceStatus("Java 采集模块", false, "端口 " + COLLECTOR_PORT + " 未监听");
        }
    }

    private ServiceStatus checkPointCloudDirectory() {
        if (Files.isDirectory(pointCloudDirectory)) {
            return new ServiceStatus("点云文件目录", true, pointCloudDirectory.toString());
        }
        return new ServiceStatus("点云文件目录", false, "目录不存在: " + pointCloudDirectory);
    }
}

