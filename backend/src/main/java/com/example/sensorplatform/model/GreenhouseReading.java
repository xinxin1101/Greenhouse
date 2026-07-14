package com.example.sensorplatform.model;

import java.time.LocalDateTime;

public record GreenhouseReading(
        Long id,
        String plcId,
        Double temperature,
        Double humidity,
        Double co2,
        Boolean lightOn,
        LocalDateTime recordTime
) {
}
