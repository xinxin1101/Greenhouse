package com.example.sensorplatform.repository;

import com.example.sensorplatform.model.GreenhouseReading;
import com.example.sensorplatform.model.GreenhouseAlarmEvent;
import com.example.sensorplatform.model.GreenhouseTrendPoint;
import org.springframework.stereotype.Repository;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

@Repository
public class GreenhouseRepository {
    private static final String TABLE_NAME = "greenhouse_plc_data";
    private final JdbcConnectionFactory connectionFactory;

    public GreenhouseRepository(JdbcConnectionFactory connectionFactory) {
        this.connectionFactory = connectionFactory;
    }

    public GreenhouseReading findLatest() {
        String sql = "SELECT * FROM " + TABLE_NAME + " ORDER BY record_time DESC LIMIT 1";
        try (Connection conn = connectionFactory.open();
             PreparedStatement stmt = conn.prepareStatement(sql);
             ResultSet rs = stmt.executeQuery()) {
            return rs.next() ? mapReading(rs) : null;
        } catch (SQLException e) {
            throw new IllegalStateException("Failed to query latest greenhouse data", e);
        }
    }

    public long countAll() {
        String sql = "SELECT COUNT(*) FROM " + TABLE_NAME;
        try (Connection conn = connectionFactory.open();
             PreparedStatement stmt = conn.prepareStatement(sql);
             ResultSet rs = stmt.executeQuery()) {
            return rs.next() ? rs.getLong(1) : 0L;
        } catch (SQLException e) {
            throw new IllegalStateException("Failed to count greenhouse data", e);
        }
    }

    public List<GreenhouseAlarmEvent> findAlarmEvents(int limit) {
        String sql = """
                SELECT id, plc_id, alarm_code, alarm_name, message,
                       active, acknowledged, started_at, cleared_at
                FROM greenhouse_alarm_events
                ORDER BY started_at DESC, id DESC
                LIMIT ?
                """;
        List<GreenhouseAlarmEvent> events = new ArrayList<>();
        try (Connection conn = connectionFactory.open();
             PreparedStatement stmt = conn.prepareStatement(sql)) {
            stmt.setInt(1, limit);
            try (ResultSet rs = stmt.executeQuery()) {
                while (rs.next()) {
                    events.add(new GreenhouseAlarmEvent(
                            rs.getLong("id"),
                            rs.getString("plc_id"),
                            rs.getString("alarm_code"),
                            rs.getString("alarm_name"),
                            rs.getString("message"),
                            rs.getBoolean("active"),
                            rs.getBoolean("acknowledged"),
                            toLocalDateTime(rs.getTimestamp("started_at")),
                            toLocalDateTime(rs.getTimestamp("cleared_at"))
                    ));
                }
            }
        } catch (SQLException e) {
            throw new IllegalStateException("Failed to query greenhouse alarms", e);
        }
        return events;
    }

    public int acknowledgeActiveAlarmEvents() {
        String sql = """
                UPDATE greenhouse_alarm_events
                SET acknowledged = 1
                WHERE active = 1 AND acknowledged = 0
                """;
        try (Connection conn = connectionFactory.open();
             PreparedStatement stmt = conn.prepareStatement(sql)) {
            return stmt.executeUpdate();
        } catch (SQLException e) {
            throw new IllegalStateException("Failed to acknowledge active greenhouse alarms", e);
        }
    }

    public int acknowledgeUnacknowledgedAlarmEvents(List<String> plcIds) {
        List<String> normalizedIds = plcIds.stream()
                .map(String::trim)
                .filter(id -> !id.isEmpty())
                .distinct()
                .toList();
        if (normalizedIds.isEmpty()) {
            throw new IllegalArgumentException("至少需要提供一个 PLC 标识");
        }

        String placeholders = String.join(",", normalizedIds.stream().map(id -> "?").toList());
        String sql = "UPDATE greenhouse_alarm_events "
                + "SET acknowledged = 1 "
                + "WHERE acknowledged = 0 AND plc_id IN (" + placeholders + ")";
        try (Connection conn = connectionFactory.open();
             PreparedStatement stmt = conn.prepareStatement(sql)) {
            for (int i = 0; i < normalizedIds.size(); i++) {
                stmt.setString(i + 1, normalizedIds.get(i));
            }
            return stmt.executeUpdate();
        } catch (SQLException e) {
            throw new IllegalStateException("Failed to acknowledge greenhouse alarms", e);
        }
    }

    public boolean acknowledgeAlarmEvent(long eventId, String plcId) {
        String normalizedPlcId = plcId == null ? "" : plcId.trim();
        if (eventId <= 0) {
            throw new IllegalArgumentException("报警事件 ID 无效");
        }
        if (normalizedPlcId.isEmpty()) {
            throw new IllegalArgumentException("PLC 标识不能为空");
        }

        String sql = """
                UPDATE greenhouse_alarm_events
                SET acknowledged = 1
                WHERE id = ? AND plc_id = ? AND acknowledged = 0
                """;
        try (Connection conn = connectionFactory.open();
             PreparedStatement stmt = conn.prepareStatement(sql)) {
            stmt.setLong(1, eventId);
            stmt.setString(2, normalizedPlcId);
            return stmt.executeUpdate() > 0;
        } catch (SQLException e) {
            throw new IllegalStateException("Failed to acknowledge greenhouse alarm event", e);
        }
    }

    public List<GreenhouseTrendPoint> findTrend(
            String mode,
            LocalDateTime start,
            LocalDateTime end,
            int limit
    ) {
        String normalizedMode = mode == null ? "realtime" : mode.toLowerCase(Locale.ROOT);
        if (List.of("hour", "day", "week").contains(normalizedMode)) {
            return findAggregatedTrend(normalizedMode, start, end);
        }
        return findRealtimeTrend(start, end, limit);
    }

    private List<GreenhouseTrendPoint> findRealtimeTrend(
            LocalDateTime start,
            LocalDateTime end,
            int limit
    ) {
        StringBuilder sql = new StringBuilder("SELECT * FROM ").append(TABLE_NAME);
        List<Object> params = new ArrayList<>();
        appendRangeWhere(sql, params, start, end);
        sql.append(" ORDER BY record_time DESC LIMIT ?");
        params.add(limit);

        List<GreenhouseReading> readings = new ArrayList<>();
        try (Connection conn = connectionFactory.open();
             PreparedStatement stmt = conn.prepareStatement(sql.toString())) {
            bindParams(stmt, params);
            try (ResultSet rs = stmt.executeQuery()) {
                while (rs.next()) {
                    readings.add(mapReading(rs));
                }
            }
        } catch (SQLException e) {
            throw new IllegalStateException("Failed to query realtime greenhouse trend", e);
        }

        List<GreenhouseTrendPoint> points = new ArrayList<>();
        for (int i = readings.size() - 1; i >= 0; i--) {
            GreenhouseReading reading = readings.get(i);
            points.add(new GreenhouseTrendPoint(
                    reading.recordTime(),
                    reading.temperature(),
                    reading.humidity(),
                    reading.co2(),
                    reading.lightOn() == null ? null : (reading.lightOn() ? 1.0 : 0.0)
            ));
        }
        return points;
    }

    private List<GreenhouseTrendPoint> findAggregatedTrend(
            String mode,
            LocalDateTime start,
            LocalDateTime end
    ) {
        String bucketExpression = switch (mode) {
            case "day" -> "DATE(record_time)";
            case "week" -> "STR_TO_DATE(CONCAT(YEARWEEK(record_time, 1), ' Monday'), '%X%V %W')";
            default -> "DATE_FORMAT(record_time, '%Y-%m-%d %H:00:00')";
        };

        StringBuilder sql = new StringBuilder()
                .append("SELECT ").append(bucketExpression).append(" AS bucket_time, ")
                .append("AVG(temperature) AS temperature, AVG(humidity) AS humidity, ")
                .append("AVG(co2) AS co2, AVG(light_on) AS light_on FROM ")
                .append(TABLE_NAME);
        List<Object> params = new ArrayList<>();
        appendRangeWhere(sql, params, start, end);
        sql.append(" GROUP BY bucket_time ORDER BY bucket_time ASC");

        List<GreenhouseTrendPoint> points = new ArrayList<>();
        try (Connection conn = connectionFactory.open();
             PreparedStatement stmt = conn.prepareStatement(sql.toString())) {
            bindParams(stmt, params);
            try (ResultSet rs = stmt.executeQuery()) {
                while (rs.next()) {
                    points.add(new GreenhouseTrendPoint(
                            toLocalDateTime(rs.getTimestamp("bucket_time")),
                            nullableDouble(rs, "temperature"),
                            nullableDouble(rs, "humidity"),
                            nullableDouble(rs, "co2"),
                            nullableDouble(rs, "light_on")
                    ));
                }
            }
        } catch (SQLException e) {
            throw new IllegalStateException("Failed to query aggregated greenhouse trend", e);
        }
        return points;
    }

    private void appendRangeWhere(
            StringBuilder sql,
            List<Object> params,
            LocalDateTime start,
            LocalDateTime end
    ) {
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

    private GreenhouseReading mapReading(ResultSet rs) throws SQLException {
        long rawId = rs.getLong("id");
        Long id = rs.wasNull() ? null : rawId;
        int rawLightOn = rs.getInt("light_on");
        Boolean lightOn = rs.wasNull() ? null : rawLightOn != 0;
        return new GreenhouseReading(
                id,
                rs.getString("plc_id"),
                nullableDouble(rs, "temperature"),
                nullableDouble(rs, "humidity"),
                nullableDouble(rs, "co2"),
                lightOn,
                toLocalDateTime(rs.getTimestamp("record_time"))
        );
    }

    private Double nullableDouble(ResultSet rs, String column) throws SQLException {
        double value = rs.getDouble(column);
        return rs.wasNull() ? null : value;
    }

    private LocalDateTime toLocalDateTime(Timestamp timestamp) {
        return timestamp == null ? null : timestamp.toLocalDateTime();
    }
}
