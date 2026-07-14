package com.example.sensorplatform.service;

import com.example.sensorplatform.model.GreenhouseReading;
import com.example.sensorplatform.model.GreenhouseAlarmEvent;
import com.example.sensorplatform.model.GreenhouseSummary;
import com.example.sensorplatform.model.GreenhouseTrendPoint;
import com.example.sensorplatform.repository.GreenhouseRepository;
import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;

@Service
public class GreenhouseService {
    private final GreenhouseRepository greenhouseRepository;
    private final GreenhouseGatewayClient greenhouseGatewayClient;

    public GreenhouseService(
            GreenhouseRepository greenhouseRepository,
            GreenhouseGatewayClient greenhouseGatewayClient
    ) {
        this.greenhouseRepository = greenhouseRepository;
        this.greenhouseGatewayClient = greenhouseGatewayClient;
    }

    public GreenhouseReading latest() {
        return greenhouseRepository.findLatest();
    }

    public GreenhouseSummary summary() {
        return new GreenhouseSummary(greenhouseRepository.findLatest(), greenhouseRepository.countAll());
    }

    public List<GreenhouseTrendPoint> trend(
            String mode,
            LocalDateTime start,
            LocalDateTime end,
            Integer limit
    ) {
        int safeLimit = limit == null ? 300 : Math.max(1, Math.min(limit, 2000));
        return greenhouseRepository.findTrend(mode, start, end, safeLimit);
    }

    public List<GreenhouseAlarmEvent> alarms(Integer limit) {
        int safeLimit = limit == null ? 100 : Math.max(1, Math.min(limit, 5000));
        return greenhouseRepository.findAlarmEvents(safeLimit);
    }

    public JsonNode state() {
        return greenhouseGatewayClient.state();
    }

    public JsonNode updateTargets(JsonNode request) {
        return greenhouseGatewayClient.post("api/targets", request);
    }

    public JsonNode updateControl(JsonNode request) {
        return greenhouseGatewayClient.post("api/control", request);
    }

    public JsonNode updateFan(JsonNode request) {
        return greenhouseGatewayClient.post("api/fan", request);
    }

    public JsonNode startCurve(JsonNode request) {
        return greenhouseGatewayClient.post("api/curves", request);
    }

    public JsonNode curveTrace(String sensor, Integer maxPoints) {
        int safeMaxPoints = maxPoints == null ? 1200 : Math.max(100, Math.min(maxPoints, 5000));
        return greenhouseGatewayClient.get("api/curves/" + sensor + "/trace?max_points=" + safeMaxPoints);
    }

    public JsonNode cancelCurve(String sensor) {
        return greenhouseGatewayClient.delete("api/curves/" + sensor);
    }

    public JsonNode historyMeta() {
        return greenhouseGatewayClient.get("api/history/meta");
    }

    public JsonNode queryHistory(JsonNode request) {
        return greenhouseGatewayClient.post("api/history/query", request);
    }

    public GreenhouseGatewayClient.GatewayDownload exportHistory(JsonNode request) {
        return greenhouseGatewayClient.download("api/history/export", request);
    }

    public JsonNode acknowledgeAlarms() {
        return greenhouseGatewayClient.post("api/alarms/ack", objectMapperEmptyObject());
    }

    public JsonNode acknowledgeAllAlarms(JsonNode request) {
        return greenhouseGatewayClient.post("api/alarms/ack-all", request);
    }

    public JsonNode acknowledgeAlarmEvent(long eventId, JsonNode request) {
        return greenhouseGatewayClient.post("api/alarms/" + eventId + "/ack", request);
    }

    private JsonNode objectMapperEmptyObject() {
        return com.fasterxml.jackson.databind.node.JsonNodeFactory.instance.objectNode();
    }
}
