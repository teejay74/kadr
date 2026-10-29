package ru.kadr.tv.data

import java.net.URI

object ServerAddress {
    fun normalize(value: String): String {
        val candidate = value.trim().trimEnd('/')
        require(candidate.isNotEmpty()) { "Введите адрес сервера" }
        val uri = runCatching { URI(candidate) }
            .getOrElse { throw IllegalArgumentException("Некорректный адрес сервера") }
        require(uri.scheme == "http" || uri.scheme == "https") {
            "Адрес должен начинаться с http:// или https://"
        }
        require(!uri.host.isNullOrBlank()) { "В адресе отсутствует имя или IP сервера" }
        require(uri.userInfo == null && uri.query == null && uri.fragment == null) {
            "Логин, параметры и фрагмент в адресе не поддерживаются"
        }
        require(uri.path.isNullOrBlank() || uri.path == "/") {
            "Укажите только адрес сервера без дополнительного пути"
        }
        require(uri.scheme == "https" || isPrivateNetworkHost(uri.host)) {
            "Открытый HTTP разрешён только для LAN или Tailscale; для публичного адреса используйте HTTPS"
        }
        return URI(uri.scheme, null, uri.host, uri.port, null, null, null).toString()
    }

    fun resolve(baseUrl: String, path: String): String =
        URI("${normalize(baseUrl)}/").resolve(path.removePrefix("/")).toString()

    fun resolveImage(baseUrl: String, value: String?): String? {
        val candidate = value?.trim()?.takeIf { it.isNotEmpty() } ?: return null
        if (candidate.startsWith('/')) return resolve(baseUrl, candidate)
        val image = runCatching { URI(candidate) }.getOrNull() ?: return null
        if (image.userInfo != null || image.host.isNullOrBlank()) return null
        if (image.scheme == "https") return image.toString()
        if (image.scheme != "http") return null
        val server = URI(normalize(baseUrl))
        return image.toString().takeIf {
            image.host.equals(server.host, ignoreCase = true) && image.port == server.port
        }
    }

    private fun isPrivateNetworkHost(host: String): Boolean {
        val normalized = host.lowercase()
        if (!normalized.contains('.') || normalized.endsWith(".local") || normalized.endsWith(".lan") || normalized.endsWith(".ts.net")) {
            return true
        }
        if (normalized == "localhost" || normalized == "::1" || normalized.startsWith("fe80:") || normalized.startsWith("fc") || normalized.startsWith("fd")) {
            return true
        }
        val octets = normalized.split('.').mapNotNull { it.toIntOrNull() }
        if (octets.size != 4 || octets.any { it !in 0..255 }) return false
        return octets[0] == 10 ||
            octets[0] == 127 ||
            (octets[0] == 172 && octets[1] in 16..31) ||
            (octets[0] == 192 && octets[1] == 168) ||
            (octets[0] == 100 && octets[1] in 64..127)
    }
}
