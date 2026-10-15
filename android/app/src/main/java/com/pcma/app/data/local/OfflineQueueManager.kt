package com.pcma.app.data.local

import android.content.Context
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import com.pcma.app.data.models.OfflineOperation
import java.util.UUID

class OfflineQueueManager(context: Context) {

    private val prefs = context.getSharedPreferences("pcma_offline_queue_prefs", Context.MODE_PRIVATE)
    private val gson = Gson()

    fun getQueue(): List<OfflineOperation> {
        val json = prefs.getString(KEY_QUEUE, "[]") ?: "[]"
        val type = object : TypeToken<List<OfflineOperation>>() {}.type
        return try {
            gson.fromJson(json, type) ?: emptyList()
        } catch (e: Exception) {
            emptyList()
        }
    }

    fun enqueue(type: String, payload: Any): OfflineOperation {
        val currentQueue = getQueue().toMutableList()
        val op = OfflineOperation(
            id = "op_${System.currentTimeMillis()}_${UUID.randomUUID().toString().take(6)}",
            type = type,
            payload = gson.toJson(payload),
            createdAt = java.text.SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", java.util.Locale.US).format(java.util.Date())
        )
        currentQueue.add(op)
        saveQueue(currentQueue)
        return op
    }

    fun clearQueue() {
        prefs.edit().remove(KEY_QUEUE).apply()
    }

    private fun saveQueue(queue: List<OfflineOperation>) {
        val json = gson.toJson(queue)
        prefs.edit().putString(KEY_QUEUE, json).apply()
    }

    companion object {
        private const val KEY_QUEUE = "offline_ops_queue"
    }
}
