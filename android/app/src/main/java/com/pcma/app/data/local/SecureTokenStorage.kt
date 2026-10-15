package com.pcma.app.data.local

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import com.pcma.app.BuildConfig

class SecureTokenStorage(context: Context) {

    private val prefs: SharedPreferences = createEncryptedPrefs(context)

    private fun createEncryptedPrefs(context: Context): SharedPreferences {
        return try {
            val masterKey = MasterKey.Builder(context)
                .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
                .build()

            EncryptedSharedPreferences.create(
                context,
                PREF_NAME,
                masterKey,
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
            )
        } catch (e: Exception) {
            // Fallback for JVM unit test execution or unsupported platform
            context.getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE)
        }
    }

    var accessToken: String?
        get() = prefs.getString(KEY_ACCESS_TOKEN, null)
        set(value) = prefs.edit().putString(KEY_ACCESS_TOKEN, value).apply()

    var refreshToken: String?
        get() = prefs.getString(KEY_REFRESH_TOKEN, null)
        set(value) = prefs.edit().putString(KEY_REFRESH_TOKEN, value).apply()

    var baseUrl: String
        get() {
            val stored = prefs.getString(KEY_BASE_URL, null)
            return if (stored.isNullOrEmpty() || stored == "http://10.0.2.2:8000" || stored == "http://192.168.29.190:8000") DEFAULT_URL else stored
        }
        set(value) = prefs.edit().putString(KEY_BASE_URL, value).apply()

    var jurisdiction: String?
        get() = prefs.getString(KEY_JURISDICTION, null)
        set(value) = prefs.edit().putString(KEY_JURISDICTION, value).apply()

    var isDevMode: Boolean
        get() = if (BuildConfig.DEBUG) prefs.getBoolean(KEY_DEV_MODE, false) else false
        set(value) {
            if (BuildConfig.DEBUG) {
                prefs.edit().putBoolean(KEY_DEV_MODE, value).apply()
            }
        }

    var consentAcknowledged: Boolean
        get() = prefs.getBoolean(KEY_CONSENT_ACKNOWLEDGED, false)
        set(value) = prefs.edit().putBoolean(KEY_CONSENT_ACKNOWLEDGED, value).apply()

    fun clearSession() {
        prefs.edit()
            .remove(KEY_ACCESS_TOKEN)
            .remove(KEY_REFRESH_TOKEN)
            .remove(KEY_DEV_MODE)
            .remove(KEY_CONSENT_ACKNOWLEDGED)
            .apply()
    }

    companion object {
        private const val PREF_NAME = "pcma_encrypted_secure_prefs"
        private const val KEY_ACCESS_TOKEN = "access_token"
        private const val KEY_REFRESH_TOKEN = "refresh_token"
        private const val KEY_BASE_URL = "base_url"
        private const val KEY_JURISDICTION = "jurisdiction"
        private const val KEY_DEV_MODE = "dev_mode"
        private const val KEY_CONSENT_ACKNOWLEDGED = "consent_acknowledged"

        val DEFAULT_URL: String get() = BuildConfig.DEFAULT_API_BASE_URL
    }
}
