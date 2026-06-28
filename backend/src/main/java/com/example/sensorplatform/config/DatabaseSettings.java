package com.example.sensorplatform.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Component
public class DatabaseSettings {
    private final String url;
    private final String username;
    private final String password;

    public DatabaseSettings(
            @Value("${app.datasource.url}") String url,
            @Value("${app.datasource.username}") String username,
            @Value("${app.datasource.password}") String password
    ) {
        this.url = url;
        this.username = username;
        this.password = password;
    }

    public String url() {
        return url;
    }

    public String username() {
        return username;
    }

    public String password() {
        return password;
    }
}

