package com.example.guide.controller;

import java.time.Instant;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/requests")
public class RequestController {

    private static final Logger logger = LoggerFactory.getLogger(RequestController.class);

    @GetMapping("/log-levels")
    public Map<String, String> generateLogs(@RequestParam(defaultValue = "anonymous") String userId) {
        logger.debug("debug log emitted for userId={}", userId);
        logger.info("info log emitted for userId={}", userId);
        logger.warn("warn log emitted for userId={}", userId);
        logger.error("error log emitted for userId={} at={}", userId, Instant.now());

        return Map.of(
            "status", "ok",
            "message", "Generated DEBUG/INFO/WARN/ERROR logs",
            "userId", userId
        );
    }
}
