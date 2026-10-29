package ru.kadr.tv.data

import android.content.Context
import androidx.core.content.edit

class ServerStore(context: Context) {
    private val preferences = context.getSharedPreferences("kadr_tv", Context.MODE_PRIVATE)

    fun read(): String? = preferences.getString(KEY_SERVER_URL, null)

    fun save(serverUrl: String) {
        preferences.edit { putString(KEY_SERVER_URL, ServerAddress.normalize(serverUrl)) }
    }

    fun clear() {
        preferences.edit { remove(KEY_SERVER_URL) }
    }

    private companion object {
        const val KEY_SERVER_URL = "server_url"
    }
}
