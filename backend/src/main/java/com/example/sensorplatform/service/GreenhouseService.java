package com.example.sensorplatform.service;

import com.example.sensorplatform.model.GreenhouseReading;
import com.example.sensorplatform.model.GreenhouseAlarmEvent;
import com.example.sensorplatform.model.GreenhouseSummary;
import com.example.sensorplatform.model.GreenhouseTrendPoint;
import com.example.sensorplatform.repository.GreenhouseRepository;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.JsonNodeFactory;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.ArrayList;
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
        int updated = greenhouseRepository.acknowledgeActiveAlarmEvents();
        return ackResult(updated, "当前报警已确认");
    }

    public JsonNode acknowledgeAllAlarms(JsonNode request) {
        JsonNode idsNode = request.path("plc_ids");
        if (!idsNode.isArray()) {
            throw new IllegalArgumentException("确认范围缺少 PLC 标识");
        }

        List<String> plcIds = new ArrayList<>();
        idsNode.forEach(node -> {
            if (node.isTextual() && !node.asText().trim().isEmpty()) {
                plcIds.add(node.asText().trim());
            }
        });

        int updated = greenhouseRepository.acknowledgeUnacknowledgedAlarmEvents(plcIds);
        if (updated == 0) {
            throw new IllegalArgumentException("没有可确认的报警记录，请刷新页面后重试");
        }
        return ackResult(updated, "所有未确认报警已确认");
    }

    public JsonNode acknowledgeAlarmEvent(long eventId, JsonNode request) {
        String plcId = request.path("plc_id").asText("");
        boolean updated = greenhouseRepository.acknowledgeAlarmEvent(eventId, plcId);
        if (!updated) {
            throw new IllegalArgumentException("报警事件不存在、已确认，或不属于当前 PLC");
        }
        return ackResult(1, "报警记录已确认");
    }

    private ObjectNode ackResult(int updated, String message) {
        ObjectNode result = JsonNodeFactory.instance.objectNode();
        result.put("ok", true);
        result.put("updated", updated);
        result.put("message", message);
        return result;
    }
}
