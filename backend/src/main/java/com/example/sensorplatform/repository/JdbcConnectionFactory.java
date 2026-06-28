package com.example.sensorplatform.repository;

import com.example.sensorplatform.config.DatabaseSettings;
import org.springframework.stereotype.Component;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;

@Component
public class JdbcConnectionFactory {
    private final DatabaseSettings settings;

    public JdbcConnectionFactory(DatabaseSettings settings) {
        this.settings = settings;
    }

    public Connection open() throws SQLException {
        return DriverManager.getConnection(settings.url(), settings.username(), settings.password());
    }
}

