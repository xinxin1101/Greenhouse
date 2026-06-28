package com.example.sensorplatform.model;

import java.time.LocalDateTime;

public record PointCloudRecord(
        Long id,
        LocalDateTime recordTime,
        String fileName,
        String url,
        boolean fileExists
) {
}

