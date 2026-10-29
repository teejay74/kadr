package ru.kadr.tv.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test

class ServerAddressTest {
    @Test
    fun normalizesLanAndTailscaleAddresses() {
        assertEquals("http://192.168.1.50:8180", ServerAddress.normalize(" http://192.168.1.50:8180/ "))
        assertEquals("http://100.101.102.103:8180", ServerAddress.normalize("http://100.101.102.103:8180"))
        assertEquals("https://kadr.example-tailnet.ts.net", ServerAddress.normalize("https://kadr.example-tailnet.ts.net/"))
    }

    @Test
    fun resolvesApiAndStreamPathsAgainstConfiguredServer() {
        assertEquals(
            "http://100.64.0.10:8180/api/v1/library/item/stream",
            ServerAddress.resolve("http://100.64.0.10:8180", "/api/v1/library/item/stream"),
        )
        assertEquals(
            "https://image.tmdb.org/t/p/w500/poster.jpg",
            ServerAddress.resolveImage(
                "http://100.64.0.10:8180",
                "https://image.tmdb.org/t/p/w500/poster.jpg",
            ),
        )
        assertEquals(
            "http://100.64.0.10:8180/images/poster.jpg",
            ServerAddress.resolveImage("http://100.64.0.10:8180", "/images/poster.jpg"),
        )
        assertEquals(
            null,
            ServerAddress.resolveImage("http://100.64.0.10:8180", "http://public.example.com/poster.jpg"),
        )
    }

    @Test
    fun rejectsUnsupportedOrAmbiguousAddresses() {
        assertThrows(IllegalArgumentException::class.java) { ServerAddress.normalize("192.168.1.50:8180") }
        assertThrows(IllegalArgumentException::class.java) { ServerAddress.normalize("ftp://server/media") }
        assertThrows(IllegalArgumentException::class.java) { ServerAddress.normalize("http://server/path") }
        assertThrows(IllegalArgumentException::class.java) { ServerAddress.normalize("http://user:secret@server") }
        assertThrows(IllegalArgumentException::class.java) { ServerAddress.normalize("http://public.example.com") }
        assertEquals("https://public.example.com", ServerAddress.normalize("https://public.example.com"))
    }
}
