package com.example.sensorplatform.service;

import com.example.sensorplatform.model.PointCloudRecord;
import com.example.sensorplatform.repository.PointCloudRepository;
import org.springframework.core.io.FileSystemResource;
import org.springframework.core.io.Resource;
import org.springframework.stereotype.Service;

import java.nio.file.Path;
import java.time.LocalDateTime;
import java.util.List;

@Service
public class PointCloudService {
    private final PointCloudRepository pointCloudRepository;

    public PointCloudService(PointCloudRepository pointCloudRepository) {
        this.pointCloudRepository = pointCloudRepository;
    }

    public List<PointCloudRecord> list(LocalDateTime start, LocalDateTime end) {
        return pointCloudRepository.findByRange(start, end);
    }

    public PointCloudRecord latest() {
        return pointCloudRepository.findLatest();
    }

    public Resource file(String fileName) {
        Path file = pointCloudRepository.resolveExistingFile(fileName);
        return file == null ? null : new FileSystemResource(file);
    }
}

