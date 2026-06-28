package com.example.sensorplatform.model;

import java.time.LocalDateTime;

public record SystemStatus(
        boolean healthy,
        LocalDateTime checkedAt,
        ServiceStatus api,
        ServiceStatus database,
        ServiceStatus collector,
        ServiceStatus pointCloudDirectory
) {
}

