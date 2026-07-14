package com.example.sensorplatform.controller;

import com.example.sensorplatform.model.GreenhouseReading;
import com.example.sensorplatform.model.GreenhouseAlarmEvent;
import com.example.sensorplatform.model.GreenhouseSummary;
import com.example.sensorplatform.model.GreenhouseTrendPoint;
import com.example.sensorplatform.service.GreenhouseService;
import com.example.sensorplatform.service.GreenhouseGatewayClient;
import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDateTime;
import java.util.List;

@RestController
@RequestMapping("/api/greenhouse")
public class GreenhouseController {
    private final GreenhouseService greenhouseService;

    public GreenhouseController(GreenhouseService greenhouseService) {
        this.greenhouseService = greenhouseService;
    }

    @GetMapping("/latest")
    public GreenhouseReading latest() {
        return greenhouseService.latest();
    }

    @GetMapping("/summary")
    public GreenhouseSummary summary() {
        return greenhouseService.summary();
    }

    @GetMapping("/trend")
    public List<GreenhouseTrendPoint> trend(
            @RequestParam(defaultValue = "realtime") String mode,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime start,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime end,
            @RequestParam(required = false) Integer limit
    ) {
        return greenhouseService.trend(mode, start, end, limit);
    }

    @GetMapping("/alarms")
    public List<GreenhouseAlarmEvent> alarms(
            @RequestParam(required = false) Integer limit
    ) {
        return greenhouseService.alarms(limit);
    }

    @GetMapping("/state")
    public JsonNode state() {
        return greenhouseService.state();
    }

    @PostMapping("/targets")
    public JsonNode updateTargets(@RequestBody JsonNode request) {
        return greenhouseService.updateTargets(request);
    }

    @PostMapping("/control")
    public JsonNode updateControl(@RequestBody JsonNode request) {
        return greenhouseService.updateControl(request);
    }

    @PostMapping("/fan")
    public JsonNode updateFan(@RequestBody JsonNode request) {
        return greenhouseService.updateFan(request);
    }

    @PostMapping("/curves")
    public JsonNode startCurve(@RequestBody JsonNode request) {
        return greenhouseService.startCurve(request);
    }

    @GetMapping("/curves/{sensor}/trace")
    public JsonNode curveTrace(
            @PathVariable String sensor,
            @RequestParam(required = false) Integer maxPoints
    ) {
        return greenhouseService.curveTrace(sensor, maxPoints);
    }

    @DeleteMapping("/curves/{sensor}")
    public JsonNode cancelCurve(@PathVariable String sensor) {
        return greenhouseService.cancelCurve(sensor);
    }

    @GetMapping("/history/meta")
    public JsonNode historyMeta() {
        return greenhouseService.historyMeta();
    }

    @PostMapping("/history/query")
    public JsonNode queryHistory(@RequestBody JsonNode request) {
        return greenhouseService.queryHistory(request);
    }

    @PostMapping("/history/export")
    public ResponseEntity<byte[]> exportHistory(@RequestBody JsonNode request) {
        GreenhouseGatewayClient.GatewayDownload download = greenhouseService.exportHistory(request);
        return ResponseEntity.ok()
                .contentType(MediaType.parseMediaType("text/csv;charset=UTF-8"))
                .header(HttpHeaders.CONTENT_DISPOSITION, download.contentDisposition())
                .body(download.content());
    }

    @PostMapping("/alarms/ack")
    public JsonNode acknowledgeAlarms() {
        return greenhouseService.acknowledgeAlarms();
    }

    @PostMapping("/alarms/ack-all")
    public JsonNode acknowledgeAllAlarms(@RequestBody JsonNode request) {
        return greenhouseService.acknowledgeAllAlarms(request);
    }

    @PostMapping("/alarms/{eventId}/ack")
    public JsonNode acknowledgeAlarmEvent(@PathVariable long eventId, @RequestBody JsonNode request) {
        return greenhouseService.acknowledgeAlarmEvent(eventId, request);
    }
}
