package com.pcma.app.data.repository

import android.content.Context
import android.media.MediaRecorder
import android.os.Build
import java.io.File
import java.io.IOException

import android.util.Log

open class AudioRecordingManager(open val context: Context? = null) {

    private var mediaRecorder: MediaRecorder? = null
    private var currentOutputFile: File? = null
    private var startTimeMs: Long = 0L
    private var pausedDurationMs: Long = 0L
    private var pauseStartTimeMs: Long = 0L

    var isRecording: Boolean = false
        private set

    var isPaused: Boolean = false
        private set

    open fun startRecording(outputFile: File, audioSource: String = "phone_microphone"): Boolean {
        stopRecordingSafely()
        currentOutputFile = outputFile

        val recorder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S && context != null) {
            MediaRecorder(context!!)
        } else {
            @Suppress("DEPRECATION")
            MediaRecorder()
        }

        try {
            recorder.apply {
                setAudioSource(MediaRecorder.AudioSource.MIC)
                setOutputFormat(MediaRecorder.OutputFormat.THREE_GPP)
                setAudioEncoder(MediaRecorder.AudioEncoder.AMR_WB)
                setOutputFile(outputFile.absolutePath)
                prepare()
                start()
            }
            mediaRecorder = recorder
            isRecording = true
            isPaused = false
            startTimeMs = System.currentTimeMillis()
            pausedDurationMs = 0L
            Log.d("PCMA_AUDIO_DIAG", "MediaRecorder initialization result: success (source=$audioSource)")
            return true
        } catch (e: Exception) {
            Log.e("PCMA_AUDIO_DIAG", "MediaRecorder initialization result: failed (${e.message})")
            stopRecordingSafely()
            return false
        }
    }

    fun pauseRecording(): Boolean {
        if (!isRecording || isPaused || mediaRecorder == null) return false
        return try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
                mediaRecorder?.pause()
                isPaused = true
                pauseStartTimeMs = System.currentTimeMillis()
                true
            } else {
                false
            }
        } catch (e: Exception) {
            e.printStackTrace()
            false
        }
    }

    fun resumeRecording(): Boolean {
        if (!isRecording || !isPaused || mediaRecorder == null) return false
        return try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
                mediaRecorder?.resume()
                isPaused = false
                pausedDurationMs += (System.currentTimeMillis() - pauseStartTimeMs)
                true
            } else {
                false
            }
        } catch (e: Exception) {
            e.printStackTrace()
            false
        }
    }

    open fun stopRecording(): File? {
        if (!isRecording && mediaRecorder == null) return currentOutputFile
        val file = currentOutputFile
        stopRecordingSafely()
        return file
    }

    open fun getDurationMs(): Long {
        if (startTimeMs == 0L) return 0L
        val now = if (isPaused) pauseStartTimeMs else System.currentTimeMillis()
        return (now - startTimeMs - pausedDurationMs).coerceAtLeast(0L)
    }

    fun getMaxAmplitude(): Int {
        return try {
            mediaRecorder?.maxAmplitude ?: 0
        } catch (_: Exception) {
            0
        }
    }

    private fun stopRecordingSafely() {
        try {
            mediaRecorder?.apply {
                stop()
                release()
            }
        } catch (_: Exception) {
        } finally {
            mediaRecorder = null
            isRecording = false
            isPaused = false
        }
    }
}
