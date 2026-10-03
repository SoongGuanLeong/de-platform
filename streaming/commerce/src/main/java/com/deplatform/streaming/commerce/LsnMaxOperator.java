package com.deplatform.streaming.commerce;

import java.time.Duration;
import org.apache.flink.api.common.state.StateTtlConfig;
import org.apache.flink.api.common.state.ValueState;
import org.apache.flink.api.common.state.ValueStateDescriptor;
import org.apache.flink.streaming.api.operators.AbstractStreamOperator;
import org.apache.flink.streaming.api.operators.OneInputStreamOperator;
import org.apache.flink.streaming.runtime.streamrecord.StreamRecord;

/**
 * A custom keyed stateful operator that holds the maximum {@code source.lsn} seen per key and
 * forwards a record only when its LSN is not strictly less than that maximum (ADR-0013).
 *
 * <p>The CDC sink's upsert path does not compare versions: it writes a key-only equality delete plus
 * the new row, so last-write-wins. A reordered stale event arriving after a fresh one would therefore
 * reinstate the superseded row. Making the stream reaching the sink LSN-monotonic per key is what
 * makes last-write-wins coincide with highest-LSN-wins.
 *
 * <p>The rule drops only the <em>strictly</em> stale, so a record whose LSN equals the maximum is
 * forwarded; collapsing equal LSNs within a commit is the source changelog deduplication's job
 * ({@code table.exec.source.cdc-events-duplicate=true}), which complements this operator rather than
 * replacing it. The keyed state carries a time-to-live, so a key that stops changing releases its
 * state rather than growing the checkpoint without bound.
 */
public class LsnMaxOperator extends AbstractStreamOperator<LsnRecord>
        implements OneInputStreamOperator<LsnRecord, LsnRecord> {

    /**
     * The keyed state's time-to-live. A key that stops changing releases its state after this long
     * without a change, so the checkpoint does not grow with the historical key count.
     */
    private static final Duration STATE_TTL = Duration.ofHours(24);

    private static final String MAX_LSN_STATE_NAME = "max-source-lsn";

    private transient ValueState<Long> maxLsn;

    @Override
    public void open() throws Exception {
        super.open();
        ValueStateDescriptor<Long> descriptor =
                new ValueStateDescriptor<>(MAX_LSN_STATE_NAME, Long.class);
        descriptor.enableTimeToLive(StateTtlConfig.newBuilder(STATE_TTL).build());
        maxLsn = getRuntimeContext().getState(descriptor);
    }

    @Override
    public void processElement(StreamRecord<LsnRecord> element) throws Exception {
        long lsn = element.getValue().lsn();
        Long seen = maxLsn.value();
        if (seen != null && lsn < seen) {
            // Strictly stale: a higher LSN for this key has already been forwarded.
            return;
        }
        maxLsn.update(lsn);
        output.collect(element);
    }
}
