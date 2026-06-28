package com.example.sensorplatform.repository;

import com.example.sensorplatform.model.SensorReading;
import com.example.sensorplatform.model.SensorTrendPoint;
import org.springframework.stereotype.Repository;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.ResultSetMetaData;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

@Repository
public class SensorRepository {
    private static final String TABLE_NAME = "sensor_data_two";
    private final JdbcConnectionFactory connectionFactory;

    public SensorRepository(JdbcConnectionFactory connectionFactory) {
        this.connectionFactory = connectionFactory;
    }

    public SensorReading findLatest() {
        String sql = "SELECT * FROM " + TABLE_NAME + " ORDER BY record_time DESC LIMIT 1";
        try (Connection conn = connectionFactory.open();
             PreparedStatement stmt = conn.prepareStatement(sql);
             ResultSet rs = stmt.executeQuery()) {
            if (rs.next()) {
                return mapReading(rs);
            }
            return null;
        } catch (SQLException e) {
            throw new IllegalStateException("Failed to query latest sensor data", e);
        }
    }

    public long countAll() {
        String sql = "SELECT COUNT(*) FROM " + TABLE_NAME;
        try (Connection conn = connectionFactory.open();
             PreparedStatement stmt = conn.prepareStatement(sql);
             ResultSet rs = stmt.executeQuery()) {
            return rs.next() ? rs.getLong(1) : 0L;
        } catch (SQLException e) {
            throw new IllegalStateException("Failed to count sensor data", e);
        }
    }

    public List<SensorTrendPoint> findTrend(String mode, LocalDateTime start, LocalDateTime end, int limit) {
        String normalizedMode = mode == null ? "realtime" : mode.toLowerCase(Locale.ROOT);
        if ("hour".equals(normalizedMode) || "day".equals(normalizedMode) || "week".equals(normalizedMode)) {
            return findAggregatedTrend(normalizedMode, start, end);
        }
        return findRealtimeTrend(start, end, limit);
    }

    private List<SensorTrendPoint> findRealtimeTrend(LocalDateTime start, LocalDateTime end, int limit) {
        StringBuilder sql = new StringBuilder("SELECT * FROM ").append(TABLE_NAME);
        List<Object> params = new ArrayList<>();
        appendRangeWhere(sql, params, start, end);
        sql.append(" ORDER BY record_time DESC LIMIT ?");
        params.add(limit);

        List<SensorReading> readings = new ArrayList<>();
        try (Connection conn = connectionFactory.open();
             PreparedStatement stmt = conn.prepareStatement(sql.toString())) {
            bindParams(stmt, params);
            try (ResultSet rs = stmt.executeQuery()) {
                while (rs.next()) {
                    readings.add(mapReading(rs));
                }
            }
        } catch (SQLException e) {
            throw new IllegalStateException("Failed to query realtime sensor trend", e);
        }

        List<SensorTrendPoint> points = new ArrayList<>();
        for (int i = readings.size() - 1; i >= 0; i--) {
            SensorReading reading = readings.get(i);
            points.add(new SensorTrendPoint(
                    reading.recordTime(),
                    reading.temperature(),
                    reading.humidity(),
                    reading.lightIntensity()
            ));
        }
        return points;
    }

    private List<SensorTrendPoint> findAggregatedTrend(String mode, LocalDateTime start, LocalDateTime end) {
        String bucketExpression = switch (mode) {
            case "day" -> "DATE(record_time)";
            case "week" -> "STR_TO_DATE(CONCAT(YEARWEEK(record_time, 1), ' Monday'), '%X%V %W')";
            default -> "DATE_FORMAT(record_time, '%Y-%m-%d %H:00:00')";
        };

        StringBuilder sql = new StringBuilder()
                .append("SELECT ")
                .append(bucketExpression)
                .append(" AS bucket_time, AVG(temperature) AS temperature, AVG(humidity) AS humidity, ")
                .append("AVG(light_intensity) AS light_intensity FROM ")
                .append(TABLE_NAME);
        List<Object> params = new ArrayList<>();
        appendRangeWhere(sql, params, start, end);
        sql.append(" GROUP BY bucket_time ORDER BY bucket_time ASC");

        List<SensorTrendPoint> points = new ArrayList<>();
        try (Connection conn = connectionFactory.open();
             PreparedStatement stmt = conn.prepareStatement(sql.toString())) {
            bindParams(stmt, params);
            try (ResultSet rs = stmt.executeQuery()) {
                while (rs.next()) {
                    points.add(new SensorTrendPoint(
                            toLocalDateTime(rs.getTimestamp("bucket_time")),
                            rs.getDouble("temperature"),
                            rs.getDouble("humidity"),
                            rs.getDouble("light_intensity")
                    ));
                }
            }
        } catch (SQLException e) {
            throw new IllegalStateException("Failed to query aggregated sensor trend", e);
        }
        return points;
    }

    private void appendRangeWhere(StringBuilder sql, List<Object> params, LocalDateTime start, LocalDateTime end) {
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
    }

    private void bindParams(PreparedStatement stmt, List<Object> params) throws SQLException {
        for (int i = 0; i < params.size(); i++) {
            stmt.setObject(i + 1, params.get(i));
        }
    }

    private SensorReading mapReading(ResultSet rs) throws SQLException {
        Set<String> columns = columns(rs);
        Long id = columns.contains("id") ? rs.getLong("id") : null;
        if (id != null && rs.wasNull()) {
            id = null;
        }
        return new SensorReading(
                id,
                rs.getString("device_id"),
                rs.getInt("node_id"),
                rs.getDouble("temperature"),
                rs.getDouble("humidity"),
                rs.getDouble("light_intensity"),
                toLocalDateTime(rs.getTimestamp("record_time"))
        );
    }

    private Set<String> columns(ResultSet rs) throws SQLException {
        ResultSetMetaData meta = rs.getMetaData();
        Set<String> columns = new HashSet<>();
        for (int i = 1; i <= meta.getColumnCount(); i++) {
            columns.add(meta.getColumnLabel(i).toLowerCase(Locale.ROOT));
        }
        return columns;
    }

    private LocalDateTime toLocalDateTime(Timestamp timestamp) {
        return timestamp == null ? null : timestamp.toLocalDateTime();
    }
}

