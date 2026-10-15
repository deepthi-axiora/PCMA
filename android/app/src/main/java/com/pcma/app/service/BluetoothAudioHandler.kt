package com.pcma.app.service

import android.content.Context
import android.media.AudioDeviceInfo
import android.media.AudioManager
import android.os.Build

class BluetoothAudioHandler(private val context: Context) {

    private val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager

    fun isBluetoothAudioConnected(): Boolean {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            val devices = audioManager.getDevices(AudioManager.GET_DEVICES_INPUTS)
            return devices.any {
                it.type == AudioDeviceInfo.TYPE_BLUETOOTH_SCO ||
                it.type == AudioDeviceInfo.TYPE_BLUETOOTH_A2DP
            }
        }
        @Suppress("DEPRECATION")
        return audioManager.isBluetoothScoOn || audioManager.isBluetoothA2dpOn
    }

    fun startBluetoothSco(): Boolean {
        return try {
            audioManager.startBluetoothSco()
            @Suppress("DEPRECATION")
            audioManager.isBluetoothScoOn = true
            true
        } catch (e: Exception) {
            e.printStackTrace()
            false
        }
    }

    fun stopBluetoothSco() {
        try {
            audioManager.stopBluetoothSco()
            @Suppress("DEPRECATION")
            audioManager.isBluetoothScoOn = false
        } catch (_: Exception) {}
    }
    fun getAvailableAudioInputSources(): List<String> {
        val sources = mutableListOf("phone_microphone")
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            val devices = audioManager.getDevices(AudioManager.GET_DEVICES_INPUTS)
            for (device in devices) {
                when (device.type) {
                    AudioDeviceInfo.TYPE_WIRED_HEADSET, AudioDeviceInfo.TYPE_USB_HEADSET -> {
                        if (!sources.contains("wired_headset")) sources.add("wired_headset")
                    }
                    AudioDeviceInfo.TYPE_BLUETOOTH_SCO, AudioDeviceInfo.TYPE_BLUETOOTH_A2DP, AudioDeviceInfo.TYPE_BLE_HEADSET -> {
                        if (!sources.contains("bluetooth")) sources.add("bluetooth")
                    }
                    AudioDeviceInfo.TYPE_USB_DEVICE, AudioDeviceInfo.TYPE_USB_ACCESSORY, AudioDeviceInfo.TYPE_LINE_ANALOG -> {
                        if (!sources.contains("external_microphone")) sources.add("external_microphone")
                    }
                }
            }
        } else {
            @Suppress("DEPRECATION")
            if (audioManager.isWiredHeadsetOn) sources.add("wired_headset")
            if (isBluetoothAudioConnected()) sources.add("bluetooth")
        }
        return sources
    }
}
