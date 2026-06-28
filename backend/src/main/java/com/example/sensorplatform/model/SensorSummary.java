package com.example.sensorplatform.model;

public record SensorSummary(
        SensorReading latest,
        Long totalCount
) {
}

