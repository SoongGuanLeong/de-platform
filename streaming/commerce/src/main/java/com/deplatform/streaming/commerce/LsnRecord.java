package com.deplatform.streaming.commerce;

import java.util.Map;
import java.util.Objects;

/**
 * One CDC change event on the keyed stream the LSN operator sits on.
 *
 * <p>{@code key} is the business primary key the Kafka topic is keyed by, {@code lsn} is the
 * per-row Postgres WAL position Debezium reports as {@code source.lsn}, {@code operation} is the
 * Debezium op code ({@code r}, {@code c}, {@code u} or {@code d}) and {@code afterImage} is the
 * row after the change. The operator compares only {@code lsn}; the rest is carried through
 * untouched so the record reaching the sink is the one the source emitted.
 */
public record LsnRecord(String key, long lsn, String operation, Map<String, Object> afterImage) {

    public LsnRecord {
        Objects.requireNonNull(key, "key");
        Objects.requireNonNull(operation, "operation");
        afterImage = afterImage == null ? Map.of() : Map.copyOf(afterImage);
    }

    public LsnRecord(String key, long lsn, String operation) {
        this(key, lsn, operation, Map.of());
    }
}
