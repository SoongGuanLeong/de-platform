package com.deplatform.streaming.commerce;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.util.List;
import org.apache.flink.api.common.typeinfo.Types;
import org.apache.flink.streaming.runtime.streamrecord.StreamRecord;
import org.apache.flink.streaming.util.KeyedOneInputStreamOperatorTestHarness;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

/**
 * The staleness rule of the keyed LSN operator (ADR-0013), tested through the operator's output
 * under Flink's own test harness.
 *
 * <p>The claim is per key: the operator holds the maximum {@code source.lsn} seen for a key and
 * forwards a record only when its LSN is not strictly less than that maximum. An equal LSN is
 * forwarded, because the rule drops only the <em>strictly</em> stale; collapsing equal LSNs within a
 * commit is the source changelog deduplication's job, not the operator's.
 */
class LsnMaxOperatorTest {

    private KeyedOneInputStreamOperatorTestHarness<String, LsnRecord, LsnRecord> harness;

    @BeforeEach
    void openHarness() throws Exception {
        harness = new KeyedOneInputStreamOperatorTestHarness<>(
                new LsnMaxOperator(), LsnRecord::key, Types.STRING);
        harness.open();
    }

    @AfterEach
    void closeHarness() throws Exception {
        harness.close();
    }

    @Test
    void holdsTheMaximumLsnPerKeyAndDropsStrictlyStaleRecords() throws Exception {
        process("order-1", 10, "c");
        process("order-1", 5, "u");
        process("order-1", 20, "u");
        process("order-2", 3, "c");
        process("order-1", 15, "u");

        assertEquals(
                List.of(
                        record("order-1", 10, "c"),
                        record("order-1", 20, "u"),
                        record("order-2", 3, "c")),
                harness.extractOutputValues());
    }

    @Test
    void holdsTheMaximumRatherThanTheLastSeenLsn() throws Exception {
        process("order-1", 20, "c");
        process("order-1", 10, "u");
        process("order-1", 15, "u");

        assertEquals(List.of(record("order-1", 20, "c")), harness.extractOutputValues());
    }

    @Test
    void anEqualLsnIsNotStrictlyStale() throws Exception {
        process("order-1", 7, "c");
        process("order-1", 7, "u");

        assertEquals(
                List.of(record("order-1", 7, "c"), record("order-1", 7, "u")),
                harness.extractOutputValues());
    }

    @Test
    void keysAreIndependent() throws Exception {
        process("order-1", 100, "c");
        process("order-2", 1, "c");
        process("order-1", 50, "u");
        process("order-2", 2, "u");

        assertEquals(
                List.of(
                        record("order-1", 100, "c"),
                        record("order-2", 1, "c"),
                        record("order-2", 2, "u")),
                harness.extractOutputValues());
    }

    private void process(String key, long lsn, String operation) throws Exception {
        harness.processElement(new StreamRecord<>(record(key, lsn, operation)));
    }

    private static LsnRecord record(String key, long lsn, String operation) {
        return new LsnRecord(key, lsn, operation);
    }
}
