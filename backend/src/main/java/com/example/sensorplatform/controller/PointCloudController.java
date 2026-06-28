package com.example.sensorplatform.controller;

import com.example.sensorplatform.model.PointCloudRecord;
import com.example.sensorplatform.service.PointCloudService;
import org.springframework.core.io.Resource;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.ContentDisposition;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDateTime;
import java.util.List;

@RestController
@RequestMapping("/api/point-cloud")
public class PointCloudController {
    private final PointCloudService pointCloudService;

    public PointCloudController(PointCloudService pointCloudService) {
        this.pointCloudService = pointCloudService;
    }

    @GetMapping("/list")
    public List<PointCloudRecord> list(
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime start,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime end
    ) {
        return pointCloudService.list(start, end);
    }

    @GetMapping("/latest")
    public PointCloudRecord latest() {
        return pointCloudService.latest();
    }

    @GetMapping("/file/{fileName:.+}")
    public ResponseEntity<Resource> file(@PathVariable String fileName) {
        Resource resource = pointCloudService.file(fileName);
        if (resource == null) {
            return ResponseEntity.notFound().build();
        }
        return ResponseEntity.ok()
                .contentType(MediaType.APPLICATION_OCTET_STREAM)
                .header(HttpHeaders.CONTENT_DISPOSITION, ContentDisposition.inline().filename(fileName).build().toString())
                .body(resource);
    }
}

