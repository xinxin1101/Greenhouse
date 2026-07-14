package com.example.sensorplatform.service;

import com.example.sensorplatform.config.GreenhouseGatewaySettings;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;

@Component
public class GreenhouseGatewayClient {
    private final GreenhouseGatewaySettings settings;
    private final ObjectMapper objectMapper;
    private final HttpClient httpClient;

    public GreenhouseGatewayClient(
            GreenhouseGatewaySettings settings,
            ObjectMapper objectMapper
    ) {
        this.settings = settings;
        this.objectMapper = objectMapper;
        this.httpClient = HttpClient.newBuilder()
                .version(HttpClient.Version.HTTP_1_1)
                .connectTimeout(Duration.ofSeconds(4))
                .build();
    }

    public JsonNode state() {
        return get("api/state");
    }

    public JsonNode get(String path) {
        return send(HttpRequest.newBuilder(endpoint(path))
                .GET()
                .timeout(Duration.ofSeconds(12))
                .build());
    }

    public JsonNode post(String path, JsonNode payload) {
        try {
            String body = objectMapper.writeValueAsString(payload);
            return send(HttpRequest.newBuilder(endpoint(path))
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(body))
                    .timeout(Duration.ofSeconds(12))
                    .build());
        } catch (IOException e) {
            throw new IllegalStateException("Failed to serialize greenhouse command", e);
        }
    }

    public JsonNode delete(String path) {
        return send(HttpRequest.newBuilder(endpoint(path))
                .DELETE()
                .timeout(Duration.ofSeconds(12))
                .build());
    }

    public GatewayDownload download(String path, JsonNode payload) {
        try {
            String body = objectMapper.writeValueAsString(payload);
            HttpResponse<byte[]> response = httpClient.send(
                    HttpRequest.newBuilder(endpoint(path))
                            .header("Content-Type", "application/json")
                            .POST(HttpRequest.BodyPublishers.ofString(body))
                            .timeout(Duration.ofSeconds(30))
                            .build(),
                    HttpResponse.BodyHandlers.ofByteArray()
            );
            if (response.statusCode() < 200 || response.statusCode() >= 300) {
                if (response.statusCode() >= 400 && response.statusCode() < 500) {
                    throw new IllegalArgumentException(
                            gatewayErrorMessage(new String(response.body(), StandardCharsets.UTF_8))
                    );
                }
                throw new IllegalStateException(
                        "Greenhouse gateway returned HTTP " + response.statusCode()
                                + ": " + new String(response.body(), StandardCharsets.UTF_8)
                );
            }
            String contentDisposition = response.headers()
                    .firstValue("Content-Disposition")
                    .orElse("attachment; filename=greenhouse-history.csv");
            return new GatewayDownload(response.body(), contentDisposition);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("Greenhouse gateway request was interrupted", e);
        } catch (IOException e) {
            throw new IllegalStateException(
                    "Greenhouse gateway is unavailable at " + settings.baseUrl(),
                    e
            );
        }
    }

    private JsonNode send(HttpRequest request) {
        try {
            HttpResponse<String> response = httpClient.send(
                    request,
                    HttpResponse.BodyHandlers.ofString()
            );
            if (response.statusCode() < 200 || response.statusCode() >= 300) {
                if (response.statusCode() >= 400 && response.statusCode() < 500) {
                    throw new IllegalArgumentException(gatewayErrorMessage(response.body()));
                }
                throw new IllegalStateException(
                        "Greenhouse gateway returned HTTP " + response.statusCode()
                                + ": " + response.body()
                );
            }
            return objectMapper.readTree(response.body());
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("Greenhouse gateway request was interrupted", e);
        } catch (IOException e) {
            throw new IllegalStateException(
                    "Greenhouse gateway is unavailable at " + settings.baseUrl(),
                    e
            );
        }
    }

    private URI endpoint(String path) {
        return URI.create(settings.baseUrl() + path);
    }

    private String gatewayErrorMessage(String body) {
        try {
            JsonNode detail = objectMapper.readTree(body).path("detail");
            if (detail.isTextual()) {
                return detail.asText();
            }
            if (!detail.isMissingNode() && !detail.isNull()) {
                return detail.toString();
            }
        } catch (IOException ignored) {
            // Preserve the original body when the gateway does not return JSON.
        }
        return body;
    }

    public record GatewayDownload(byte[] content, String contentDisposition) {
    }
}
