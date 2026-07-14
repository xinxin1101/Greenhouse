package com.example.sensorplatform.model;

import java.time.LocalDateTime;

public record GreenhouseAlarmEvent(
        Long id,
        String plcId,
        String alarmCode,
        String alarmName,
        String message,
        boolean active,
        boolean acknowledged,
        LocalDateTime startedAt,
        LocalDateTime clearedAt
) {
}
