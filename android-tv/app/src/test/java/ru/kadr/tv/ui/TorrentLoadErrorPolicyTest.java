package ru.kadr.tv.ui;

import static org.junit.Assert.assertEquals;
import static ru.kadr.tv.ui.TorrentLoadErrorPolicyKt.torrentRetryDelayMs;

import androidx.media3.common.C;
import androidx.media3.common.ParserException;
import androidx.media3.common.PlaybackException;
import androidx.media3.datasource.HttpDataSource.HttpDataSourceException;
import androidx.media3.datasource.HttpDataSource.InvalidResponseCodeException;
import java.io.IOException;
import java.util.Collections;
import org.junit.Test;

public class TorrentLoadErrorPolicyTest {
    @Test
    public void gatewayTimeoutUsesBoundedBackoff() {
        var timeout = httpError(504);

        assertEquals(2_000L, torrentRetryDelayMs(timeout, 1));
        assertEquals(8_000L, torrentRetryDelayMs(timeout, 4));
        assertEquals(C.TIME_UNSET, torrentRetryDelayMs(timeout, 5));
    }

    @Test
    public void wrappedNetworkFailureAndSocketTimeoutAreRetried() {
        for (int reason : new int[] {
            PlaybackException.ERROR_CODE_IO_NETWORK_CONNECTION_FAILED,
            PlaybackException.ERROR_CODE_IO_NETWORK_CONNECTION_TIMEOUT,
        }) {
            var error = new IOException(new HttpDataSourceException(null, reason, HttpDataSourceException.TYPE_READ));
            assertEquals(2_000L, torrentRetryDelayMs(error, 1));
        }
    }

    @Test
    public void missingFileInvalidRangeAndUnsupportedFormatFailWithoutRetry() {
        assertEquals(C.TIME_UNSET, torrentRetryDelayMs(httpError(404), 1));
        assertEquals(C.TIME_UNSET, torrentRetryDelayMs(httpError(416), 1));
        var formatError = ParserException.createForUnsupportedContainerFeature("Unsupported format");
        assertEquals(C.TIME_UNSET, torrentRetryDelayMs(formatError, 1));
    }

    // Request metadata is unused by the policy, so no Android URI is needed on the JVM.
    private static InvalidResponseCodeException httpError(int status) {
        return new InvalidResponseCodeException(status, null, null, Collections.emptyMap(), null, new byte[0]);
    }
}
