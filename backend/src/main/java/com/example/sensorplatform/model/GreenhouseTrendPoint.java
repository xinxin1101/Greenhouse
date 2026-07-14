package com.example.sensorplatform.model;

import java.time.LocalDateTime;

public record GreenhouseTrendPoint(
        LocalDateTime recordTime,
        Double temperature,
        Double humidity,
        Double co2,
        Double lightOn
) {
}
