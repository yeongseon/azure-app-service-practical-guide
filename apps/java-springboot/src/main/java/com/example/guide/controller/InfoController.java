package com.example.guide.controller;

import java.util.Map;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class InfoController {

    @Value("${spring.profiles.active:local}")
    private String environment;

    @GetMapping("/info")
    public Map<String, String> info() {
        return Map.of(
            "name", "azure-appservice-java-guide",
            "version", "1.0.0",
            "java", "17",
            "framework", "Spring Boot 3.2",
            "environment", environment
        );
    }
}
