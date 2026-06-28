package com.example.sensorplatform.model;

import java.time.LocalDateTime;

public record SensorTrendPoint(
        LocalDateTime recordTime,
        Double temperature,
        Double humidity,
        Double lightIntensity
) {
}

