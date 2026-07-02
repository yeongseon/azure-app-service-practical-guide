package com.example.stage0;

import java.io.IOException;
import java.io.OutputStream;
import java.time.Duration;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.StreamingResponseBody;

/**
 * Stage 0 config-discovery app for the Windows App Service Java SE timeout lab.
 *
 * <p>Endpoints:
 * <ul>
 *   <li>{@code GET /} - simple liveness ping used by the platform.</li>
 *   <li>{@code GET /actuator/health} - Spring Boot Actuator health endpoint.</li>
 *   <li>{@code GET /slow/{seconds}} - sleeps for {@code seconds} without
 *       emitting any bytes, then returns a JSON body. Used by
 *       {@code run-timeout-probe.sh} to observe when the front end cuts the
 *       connection.</li>
 *   <li>{@code GET /stream/{seconds}} - streams one line to the client every
 *       30 seconds for a total of {@code seconds}. Used to falsify Oracle
 *       hypothesis H7: if the 230s front-end limit is an <em>idle</em>
 *       timeout, {@code /stream/300} completes; if it is an
 *       <em>absolute</em> request-duration limit, {@code /stream/300} still
 *       gets cut around 230s.</li>
 * </ul>
 *
 * <p>All handlers log the request/response boundaries with UTC timestamps so
 * the AppServiceConsoleLogs entries can be correlated with client-side curl
 * timing rows.
 */
@SpringBootApplication
public class Stage0Application {

    private static final Logger LOG = LoggerFactory.getLogger(Stage0Application.class);

    private static final int MAX_SECONDS = 600;

    private static final Duration STREAM_INTERVAL = Duration.ofSeconds(30);

    public static void main(String[] args) {
        SpringApplication.run(Stage0Application.class, args);
    }

    @RestController
    public static class ProbeController {

        @GetMapping(value = "/", produces = MediaType.TEXT_PLAIN_VALUE)
        public String root() {
            return "OK";
        }

        /**
         * Sleeps server-side without emitting bytes until completion, then
         * returns a small JSON body. Any HTTP status other than 200 or any
         * mid-request connection close is attributed to the platform, not the
         * application.
         */
        @GetMapping(value = "/slow/{seconds}", produces = MediaType.APPLICATION_JSON_VALUE)
        public ResponseEntity<Map<String, Object>> slow(@PathVariable("seconds") int seconds) {
            int bounded = clamp(seconds);
            Instant start = Instant.now();
            LOG.info("slow.start seconds={} bounded={} start={}", seconds, bounded, start);
            try {
                Thread.sleep(Duration.ofSeconds(bounded).toMillis());
            } catch (InterruptedException ex) {
                Thread.currentThread().interrupt();
                LOG.warn("slow.interrupted seconds={} elapsedMs={}", bounded,
                        Duration.between(start, Instant.now()).toMillis());
                return ResponseEntity.status(499).body(errorBody("interrupted", bounded, start));
            }
            Instant end = Instant.now();
            long elapsedMs = Duration.between(start, end).toMillis();
            LOG.info("slow.end seconds={} elapsedMs={} end={}", bounded, elapsedMs, end);

            Map<String, Object> body = new LinkedHashMap<>();
            body.put("endpoint", "slow");
            body.put("requestedSeconds", seconds);
            body.put("actualSeconds", bounded);
            body.put("elapsedMs", elapsedMs);
            body.put("startUtc", start.toString());
            body.put("endUtc", end.toString());
            return ResponseEntity.ok(body);
        }

        /**
         * Streams a JSON line every {@link #STREAM_INTERVAL} for a total of
         * {@code seconds}. If the front-end 230s ceiling is an idle timeout,
         * this endpoint completes even for {@code seconds > 230}. If it is an
         * absolute request-duration ceiling, the connection is still cut
         * around 230s.
         */
        @GetMapping(value = "/stream/{seconds}", produces = MediaType.APPLICATION_NDJSON_VALUE)
        public ResponseEntity<StreamingResponseBody> stream(@PathVariable("seconds") int seconds) {
            int bounded = clamp(seconds);
            Instant start = Instant.now();
            LOG.info("stream.start seconds={} bounded={} intervalSec={} start={}",
                    seconds, bounded, STREAM_INTERVAL.toSeconds(), start);

            StreamingResponseBody body = (OutputStream out) -> {
                long deadlineMs = start.toEpochMilli() + Duration.ofSeconds(bounded).toMillis();
                int chunkIndex = 0;
                writeChunk(out, chunkIndex++, start);
                while (System.currentTimeMillis() < deadlineMs) {
                    long remainingMs = deadlineMs - System.currentTimeMillis();
                    long sleepMs = Math.min(STREAM_INTERVAL.toMillis(), remainingMs);
                    if (sleepMs <= 0) {
                        break;
                    }
                    try {
                        Thread.sleep(sleepMs);
                    } catch (InterruptedException ex) {
                        Thread.currentThread().interrupt();
                        LOG.warn("stream.interrupted seconds={} chunkIndex={} elapsedMs={}",
                                bounded, chunkIndex,
                                Duration.between(start, Instant.now()).toMillis());
                        return;
                    }
                    writeChunk(out, chunkIndex++, start);
                }
                LOG.info("stream.end seconds={} chunkCount={} elapsedMs={}",
                        bounded, chunkIndex,
                        Duration.between(start, Instant.now()).toMillis());
            };
            return ResponseEntity.ok(body);
        }

        private static void writeChunk(OutputStream out, int index, Instant start) throws IOException {
            Instant now = Instant.now();
            String line = String.format(
                    "{\"chunkIndex\":%d,\"elapsedMs\":%d,\"utc\":\"%s\"}%n",
                    index, Duration.between(start, now).toMillis(), now);
            out.write(line.getBytes(java.nio.charset.StandardCharsets.UTF_8));
            out.flush();
        }

        private static int clamp(int seconds) {
            if (seconds < 0) {
                return 0;
            }
            if (seconds > MAX_SECONDS) {
                return MAX_SECONDS;
            }
            return seconds;
        }

        private static Map<String, Object> errorBody(String reason, int bounded, Instant start) {
            Map<String, Object> body = new LinkedHashMap<>();
            body.put("endpoint", "slow");
            body.put("error", reason);
            body.put("actualSeconds", bounded);
            body.put("elapsedMs", Duration.between(start, Instant.now()).toMillis());
            body.put("startUtc", start.toString());
            return body;
        }
    }
}
