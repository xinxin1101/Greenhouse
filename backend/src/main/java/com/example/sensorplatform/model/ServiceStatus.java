package com.example.sensorplatform.model;

public record ServiceStatus(
        String name,
        boolean running,
        String detail
) {
}

