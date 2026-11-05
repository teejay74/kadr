package ru.kadr.tv.data

import org.junit.Assert.assertEquals
import org.junit.Test

class CatalogQueryTest {
    @Test
    fun `new movie releases request the server digital-release collection`() {
        assertEquals(
            "/api/v1/movies?page=1&sort=newest&released_within_days=365",
            catalogPath(MediaKind.MOVIE, "newest", null, null, 365),
        )
    }

    @Test
    fun `cartoon age filter is encoded and limited to animation`() {
        assertEquals(
            "/api/v1/movies?page=1&sort=popular&genre=16&age_rating=6%2B",
            catalogPath(MediaKind.MOVIE, "popular", 16, AgeRating.SIX, null),
        )
    }

    @Test
    fun `cartoon series omit unsupported age classification`() {
        assertEquals(
            "/api/v1/series?page=1&sort=popular&genre=16",
            catalogPath(MediaKind.SERIES, "popular", 16, null, null),
        )
    }

    @Test
    fun `details provide an encoded title for metadata fallback`() {
        assertEquals(
            "/api/v1/series/1399?fallback_title=%D0%98%D0%B3%D1%80%D0%B0+" +
                "%D0%BF%D1%80%D0%B5%D1%81%D1%82%D0%BE%D0%BB%D0%BE%D0%B2&fallback_year=2011",
            detailsPath(MediaKind.SERIES, 1399, "Игра престолов", 2011),
        )
    }
}
