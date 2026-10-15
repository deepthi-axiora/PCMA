package com.pcma.app

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.os.Build

class PcmaApplication : Application() {

    override fun onCreate() {
        super.onCreate()
        createNotificationChannels()
    }

    private fun createNotificationChannels() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val manager = getSystemService(NotificationManager::class.java)

            // Foreground Recording Channel
            val recordingChannel = NotificationChannel(
                CHANNEL_RECORDING,
                getString(R.string.recording_notification_channel),
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = getString(R.string.recording_notification_desc)
            }

            // Reminders Channel
            val remindersChannel = NotificationChannel(
                CHANNEL_REMINDERS,
                getString(R.string.reminders_notification_channel),
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "PCMA Scheduled Reminders and Alerts"
            }

            manager?.createNotificationChannel(recordingChannel)
            manager?.createNotificationChannel(remindersChannel)
        }
    }

    companion object {
        const val CHANNEL_RECORDING = "pcma_recording_channel"
        const val CHANNEL_REMINDERS = "pcma_reminders_channel"
    }
}
