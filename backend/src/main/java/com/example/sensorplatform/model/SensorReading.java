package com.example.sensorplatform.model;

import java.time.LocalDateTime;

public record SensorReading(
        Long id,
        String deviceId,
        Integer nodeId,
        Double temperature,
        Double humidity,
        Double lightIntensity,
        LocalDateTime recordTime
) {
}

