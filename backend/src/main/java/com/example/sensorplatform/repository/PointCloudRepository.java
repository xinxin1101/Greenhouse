package com.example.sensorplatform.repository;

import com.example.sensorplatform.model.PointCloudRecord;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Repository;
import org.springframework.web.util.UriUtils;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.charset.StandardCharsets;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

@Repository
public class PointCloudRepository {
    private static final String TABLE_NAME = "point_cloud";
    private final JdbcConnectionFactory connectionFactory;
    private final Path pointCloudDirectory;

    public PointCloudRepository(
            JdbcConnectionFactory connectionFactory,
            @Value("${app.point-cloud.directory}") String pointCloudDirectory
    ) {
        this.connectionFactory = connectionFactory;
        this.pointCloudDirectory = Path.of(pointCloudDirectory).toAbsolutePath().normalize();
    }

    public List<PointCloudRecord> findByRange(LocalDateTime start, LocalDateTime end) {
        StringBuilder sql = new StringBuilder("SELECT id, record_time, file_name FROM ").append(TABLE_NAME);
        List<Object> params = new ArrayList<>();
        List<String> conditions = new ArrayList<>();
        if (start != null) {
            conditions.add("record_time >= ?");
            params.add(Timestamp.valueOf(start));
        }
        if (end != null) {
            conditions.add("record_time <= ?");
            params.add(Timestamp.valueOf(end));
        }
        if (!conditions.isEmpty()) {
            sql.append(" WHERE ").append(String.join(" AND ", conditions));
        }
        sql.append(" ORDER BY record_time ASC");

        List<PointCloudRecord> records = new ArrayList<>();
        try (Connection conn = connectionFactory.open();
             PreparedStatement stmt = conn.prepareStatement(sql.toString())) {
            for (int i = 0; i < params.size(); i++) {
                stmt.setObject(i + 1, params.get(i));
            }
            try (ResultSet rs = stmt.executeQuery()) {
                while (rs.next()) {
                    records.add(mapRecord(rs));
                }
            }
            return records;
        } catch (SQLException e) {
            throw new IllegalStateException("Failed to query point cloud list", e);
        }
    }

    public PointCloudRecord findLatest() {
        String sql = "SELECT id, record_time, file_name FROM " + TABLE_NAME + " ORDER BY record_time DESC LIMIT 1";
        try (Connection conn = connectionFactory.open();
             PreparedStatement stmt = conn.prepareStatement(sql);
             ResultSet rs = stmt.executeQuery()) {
            return rs.next() ? mapRecord(rs) : null;
        } catch (SQLException e) {
            throw new IllegalStateException("Failed to query latest point cloud", e);
        }
    }

    public Path resolveExistingFile(String fileName) {
        Path resolved = pointCloudDirectory.resolve(fileName).normalize();
        if (!resolved.startsWith(pointCloudDirectory)) {
            throw new IllegalArgumentException("Invalid point cloud file name");
        }
        return Files.exists(resolved) && Files.isRegularFile(resolved) ? resolved : null;
    }

    private PointCloudRecord mapRecord(ResultSet rs) throws SQLException {
        String fileName = rs.getString("file_name");
        Path file = resolveExistingFile(fileName);
        return new PointCloudRecord(
                rs.getLong("id"),
                rs.getTimestamp("record_time").toLocalDateTime(),
                fileName,
                "/api/point-cloud/file/" + UriUtils.encodePathSegment(fileName, StandardCharsets.UTF_8),
                file != null
        );
    }
}
