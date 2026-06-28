package com.example.sensorplatform.controller;

import com.example.sensorplatform.model.SystemStatus;
import com.example.sensorplatform.service.SystemStatusService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/system")
public class SystemController {
    private final SystemStatusService systemStatusService;

    public SystemController(SystemStatusService systemStatusService) {
        this.systemStatusService = systemStatusService;
    }

    @GetMapping("/status")
    public SystemStatus status() {
        return systemStatusService.current();
    }
}

