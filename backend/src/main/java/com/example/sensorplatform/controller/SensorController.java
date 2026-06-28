package com.example.sensorplatform.controller;

import com.example.sensorplatform.model.SensorReading;
import com.example.sensorplatform.model.SensorSummary;
import com.example.sensorplatform.model.SensorTrendPoint;
import com.example.sensorplatform.service.SensorService;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDateTime;
import java.util.List;

@RestController
@RequestMapping("/api/sensor")
public class SensorController {
    private final SensorService sensorService;

    public SensorController(SensorService sensorService) {
        this.sensorService = sensorService;
    }

    @GetMapping("/latest")
    public SensorReading latest() {
        return sensorService.latest();
    }

    @GetMapping("/summary")
    public SensorSummary summary() {
        return sensorService.summary();
    }

    @GetMapping("/trend")
    public List<SensorTrendPoint> trend(
            @RequestParam(defaultValue = "realtime") String mode,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime start,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime end,
            @RequestParam(required = false) Integer limit
    ) {
        return sensorService.trend(mode, start, end, limit);
    }
}

