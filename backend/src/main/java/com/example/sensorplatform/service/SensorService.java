package com.example.sensorplatform.service;

import com.example.sensorplatform.model.SensorReading;
import com.example.sensorplatform.model.SensorSummary;
import com.example.sensorplatform.model.SensorTrendPoint;
import com.example.sensorplatform.repository.SensorRepository;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;

@Service
public class SensorService {
    private final SensorRepository sensorRepository;

    public SensorService(SensorRepository sensorRepository) {
        this.sensorRepository = sensorRepository;
    }

    public SensorReading latest() {
        return sensorRepository.findLatest();
    }

    public SensorSummary summary() {
        return new SensorSummary(sensorRepository.findLatest(), sensorRepository.countAll());
    }

    public List<SensorTrendPoint> trend(String mode, LocalDateTime start, LocalDateTime end, Integer limit) {
        int safeLimit = limit == null ? 300 : Math.max(1, Math.min(limit, 2000));
        return sensorRepository.findTrend(mode, start, end, safeLimit);
    }
}

