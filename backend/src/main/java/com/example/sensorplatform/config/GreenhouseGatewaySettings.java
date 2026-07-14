package com.example.sensorplatform.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Component
public class GreenhouseGatewaySettings {
    private final String baseUrl;

    public GreenhouseGatewaySettings(
            @Value("${app.greenhouse.gateway-url:http://127.0.0.1:8000}") String baseUrl
    ) {
        this.baseUrl = baseUrl.endsWith("/") ? baseUrl : baseUrl + "/";
    }

    public String baseUrl() {
        return baseUrl;
    }
}
