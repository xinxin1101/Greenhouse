package com.example.sensorplatform.model;

public record GreenhouseSummary(
        GreenhouseReading latest,
        Long totalCount
) {
}
