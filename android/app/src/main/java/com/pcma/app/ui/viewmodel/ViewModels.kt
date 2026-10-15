package com.pcma.app.ui.viewmodel

import android.content.Context
import android.content.Intent
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.pcma.app.BuildConfig
import com.pcma.app.data.models.*
import com.pcma.app.data.repository.AudioRecordingManager
import com.pcma.app.data.repository.PcmaRepository
import com.pcma.app.service.RecordingForegroundService
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import java.io.File

import android.Manifest
import android.content.pm.PackageManager
import android.util.Log
import com.pcma.app.service.BluetoothAudioHandler
import com.auth0.android.Auth0
import com.auth0.android.authentication.AuthenticationException
import com.auth0.android.callback.Callback
import com.auth0.android.provider.WebAuthProvider
import com.auth0.android.result.Credentials

// MainViewModel
class MainViewModel(val repository: PcmaRepository) : ViewModel() {
    val isAuthenticated = MutableStateFlow(
        try { repository.storage.accessToken != null || (BuildConfig.DEBUG && repository.storage.isDevMode) } catch (_: Exception) { false }
    )
    val userProfile = MutableStateFlow<ProfileResponse?>(null)
    val isLoading = MutableStateFlow(false)
    val errorMessage = MutableStateFlow<String?>(null)

    fun login(devMode: Boolean = true) {
        if (BuildConfig.DEBUG && devMode) {
            repository.storage.isDevMode = true
            isAuthenticated.value = true
            loadProfile()
        } else {
            errorMessage.value = "Mock authentication is disabled in production release builds."
        }
    }

    fun loginWithAuth0(context: Context, onComplete: () -> Unit) {
        val account = Auth0(
            clientId = BuildConfig.AUTH0_CLIENT_ID,
            domain = BuildConfig.AUTH0_DOMAIN
        )

        WebAuthProvider.login(account)
            .withScheme("demo")
            .withAudience(BuildConfig.AUTH0_AUDIENCE)
            .withScope("openid profile email offline_access")
            .start(context, object : Callback<Credentials, AuthenticationException> {
                override fun onSuccess(credentials: Credentials) {
                    val token = credentials.accessToken
                    val refresh = credentials.refreshToken
                    repository.storage.isDevMode = false
                    repository.storage.accessToken = token
                    if (!refresh.isNullOrEmpty()) {
                        repository.storage.refreshToken = refresh
                    }
                    isAuthenticated.value = true
                    loadProfile()
                    onComplete()
                }

                override fun onFailure(error: AuthenticationException) {
                    errorMessage.value = "Sign in failed. Please try again."
                }
            })
    }

    fun loginWithAuth0Token(token: String, onComplete: () -> Unit) {
        repository.storage.isDevMode = false
        repository.storage.accessToken = token
        isAuthenticated.value = true
        loadProfile()
        onComplete()
    }

    fun logout() {
        repository.storage.clearSession()
        isAuthenticated.value = false
        userProfile.value = null
    }

    fun loadProfile() {
        viewModelScope.launch {
            isLoading.value = true
            try {
                val prof = repository.getProfile()
                userProfile.value = prof
                repository.storage.jurisdiction = prof.jurisdiction
            } catch (e: Exception) {
                if (e is com.pcma.app.data.api.ApiException && (e.statusCode == 401 || e.message?.contains("expired", ignoreCase = true) == true)) {
                    val refreshed = repository.refreshAuthToken()
                    if (refreshed) {
                        try {
                            val prof = repository.getProfile()
                            userProfile.value = prof
                            repository.storage.jurisdiction = prof.jurisdiction
                            return@launch
                        } catch (_: Exception) {}
                    }
                    isAuthenticated.value = false
                    errorMessage.value = "Session expired. Please sign in again."
                } else {
                    errorMessage.value = e.message
                }
            } finally {
                isLoading.value = false
            }
        }
    }

    fun updateJurisdiction(jurisdiction: String, onComplete: () -> Unit) {
        viewModelScope.launch {
            try {
                val updated = repository.updateProfile(jurisdiction)
                userProfile.value = updated
                onComplete()
            } catch (e: Exception) {
                errorMessage.value = e.message
            }
        }
    }
}

// RecordingViewModel
class RecordingViewModel(
    val repository: PcmaRepository,
    val recordingManager: AudioRecordingManager
) : ViewModel() {

    val recordingState = MutableStateFlow("idle") // idle, recording, paused, uploading, processing, ready, failed
    val activeRecording = MutableStateFlow<RecordingResponse?>(null)
    val durationSeconds = MutableStateFlow(0)
    val audioSource = MutableStateFlow("phone_microphone")
    val errorMessage = MutableStateFlow<String?>(null)
    val abandonedRecording = MutableStateFlow<RecordingResponse?>(null)
    val isRecovering = MutableStateFlow(false)
    val processingStage = MutableStateFlow("Idle")

    fun startRecording(
        cacheDir: File,
        context: Context? = null,
        consentAcknowledged: Boolean = repository.storage.consentAcknowledged
    ) {
        viewModelScope.launch {
            recordingState.value = "preparing"
            errorMessage.value = null
            var createdRecId: Int? = null
            try {
                val ctx = context ?: recordingManager.context
                val availableSources = if (ctx != null) {
                    try {
                        val bluetoothHandler = BluetoothAudioHandler(ctx)
                        bluetoothHandler.getAvailableAudioInputSources()
                    } catch (_: Exception) {
                        listOf("phone_microphone")
                    }
                } else {
                    listOf("phone_microphone")
                }

                // Resolve active audio source with graceful fallback to built-in mic
                var selectedSource = audioSource.value
                if (selectedSource != "phone_microphone" && !availableSources.contains(selectedSource)) {
                    try { Log.w("PCMA_AUDIO_DIAG", "Selected audio source '$selectedSource' unavailable. Falling back to 'phone_microphone'") } catch (_: Exception) {}
                    selectedSource = "phone_microphone"
                    audioSource.value = "phone_microphone"
                }

                val hasMicPermission = if (ctx != null) {
                    try {
                        ContextCompat.checkSelfPermission(ctx, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
                    } catch (_: Exception) {
                        true
                    }
                } else {
                    true
                }
                val isBtConnected = availableSources.contains("bluetooth")

                // Safe Diagnostic Logging (NO audio data or sensitive info logged)
                try {
                    Log.d("PCMA_AUDIO_DIAG", "Selected audio source: $selectedSource")
                    Log.d("PCMA_AUDIO_DIAG", "Available audio input devices: $availableSources")
                    Log.d("PCMA_AUDIO_DIAG", "Microphone permission granted: $hasMicPermission")
                    Log.d("PCMA_AUDIO_DIAG", "Bluetooth input connected: $isBtConnected")
                    Log.d("PCMA_AUDIO_DIAG", "Consent acknowledged: $consentAcknowledged")
                } catch (_: Exception) {}

                // 1. Start Backend Recording Session
                val rec = repository.startRecording(
                    audioSource = selectedSource,
                    sourceAvailable = true,
                    microphonePermissionGranted = hasMicPermission,
                    consentAcknowledged = consentAcknowledged
                )
                createdRecId = rec.id
                activeRecording.value = rec

                // 2. Start Foreground Recording Service
                if (ctx != null) {
                    try {
                        val serviceIntent = Intent(ctx, RecordingForegroundService::class.java).apply {
                            action = RecordingForegroundService.ACTION_START
                        }
                        ContextCompat.startForegroundService(ctx, serviceIntent)
                    } catch (_: Exception) {}

                    if (selectedSource == "bluetooth" && isBtConnected) {
                        try {
                            BluetoothAudioHandler(ctx).startBluetoothSco()
                        } catch (_: Exception) {}
                    }
                }

                // 3. Start Native Audio Capture
                val file = File(cacheDir, "recording_${rec.id}.3gp")
                if (recordingManager.startRecording(file, selectedSource)) {
                    recordingState.value = "recording"
                    durationSeconds.value = 0
                    startTimer()
                } else {
                    recordingState.value = "failed"
                    errorMessage.value = "Microphone initialization failed"
                    try {
                        repository.cancelRecording(rec.id)
                    } catch (_: Exception) {}
                    activeRecording.value = null
                    stopForegroundService(context)
                }
            } catch (e: Exception) {
                createdRecId?.let { id ->
                    try {
                        repository.cancelRecording(id)
                    } catch (_: Exception) {}
                    activeRecording.value = null
                }
                recordingState.value = "failed"
                errorMessage.value = e.message
                stopForegroundService(context)
                if (e.message?.contains("already active", ignoreCase = true) == true ||
                    e.message?.contains("recording_already_active", ignoreCase = true) == true) {
                    checkForAbandonedRecording()
                }
            }
        }
    }

    fun onConsentDeclined() {
        recordingState.value = "failed"
        errorMessage.value = "Recording consent was declined"
    }

    fun pauseRecording() {
        viewModelScope.launch {
            activeRecording.value?.let { rec ->
                try {
                    repository.pauseRecording(rec.id)
                    recordingManager.pauseRecording()
                    recordingState.value = "paused"
                } catch (e: Exception) {
                    errorMessage.value = e.message
                }
            }
        }
    }

    fun resumeRecording() {
        viewModelScope.launch {
            activeRecording.value?.let { rec ->
                try {
                    repository.resumeRecording(rec.id)
                    recordingManager.resumeRecording()
                    recordingState.value = "recording"
                } catch (e: Exception) {
                    errorMessage.value = e.message
                }
            }
        }
    }

    fun stopRecording(cacheDir: File? = null, context: Context? = null, onFinished: (Int) -> Unit) {
        viewModelScope.launch {
            val rec = activeRecording.value ?: return@launch
            recordingState.value = "uploading"

            val audioFile = recordingManager.stopRecording()
            val durationMs = recordingManager.getDurationMs()

            try {
                if (audioFile != null && audioFile.exists()) {
                    // Upload audio file to backend
                    repository.uploadAudio(rec.id, audioFile, durationMs)

                    // Safe Cleanup: Delete local temp file ONLY after successful upload
                    try {
                        audioFile.delete()
                    } catch (_: Exception) {}

                    repository.stopRecording(rec.id)
                    pollTranscription(rec.id, onFinished)
                } else {
                    // No audio captured: safely cancel empty session rather than crashing with 422
                    repository.cancelRecording(rec.id)
                    activeRecording.value = null
                    recordingState.value = "idle"
                    errorMessage.value = "Recording stopped without captured audio (session cancelled safely)."
                }
            } catch (e: Exception) {
                recordingState.value = "failed"
                errorMessage.value = e.message
                // Upload failed: audioFile is RETAINED for retry!
            } finally {
                stopForegroundService(context)
            }
        }
    }

    fun retryUploadAndTranscription(recordingId: Int, audioFile: File?, onFinished: (Int) -> Unit) {
        viewModelScope.launch {
            recordingState.value = "uploading"
            errorMessage.value = null
            try {
                if (audioFile != null && audioFile.exists()) {
                    repository.uploadAudio(recordingId, audioFile, null)
                    // Delete temp file after retry upload succeeds
                    try { audioFile.delete() } catch (_: Exception) {}
                }
                repository.retryTranscription(recordingId)
                pollTranscription(recordingId, onFinished)
            } catch (e: Exception) {
                recordingState.value = "failed"
                errorMessage.value = e.message
            }
        }
    }

    private fun stopForegroundService(context: Context?) {
        context?.let { ctx ->
            try {
                val serviceIntent = Intent(ctx, RecordingForegroundService::class.java)
                ctx.stopService(serviceIntent)
            } catch (_: Exception) {}
        }
    }

    fun refreshLatestStatus() {
        viewModelScope.launch {
            val rec = activeRecording.value
            if (rec != null && recordingState.value != "idle") {
                try {
                    val status = repository.getTranscriptionStatus(rec.id)
                    if (status.status == "complete" || status.status == "completed" || status.status == "ready_for_review") {
                        recordingState.value = "ready"
                    } else if (status.status == "failed") {
                        recordingState.value = "failed"
                        errorMessage.value = status.lastErrorMessage ?: "Transcription failed"
                    }
                } catch (_: Exception) {}
            } else {
                try {
                    val recordings = repository.getRecordings()
                    val activeOrPaused = recordings.firstOrNull {
                        it.state == "active" || it.state == "paused" || it.status == "active" || it.status == "paused"
                    }
                    if (activeOrPaused != null) {
                        abandonedRecording.value = activeOrPaused
                        errorMessage.value = "Active recording session (#${activeOrPaused.id}) detected from a previous session."
                    } else {
                        abandonedRecording.value = null
                        val latest = recordings.firstOrNull()
                        if (latest != null && (latest.state == "ready_for_review" || latest.status == "ready_for_review")) {
                            recordingState.value = "ready"
                            activeRecording.value = latest
                        }
                    }
                } catch (_: Exception) {}
            }
        }
    }

    private suspend fun syncAbandonedState() {
        val active = try {
            repository.getActiveRecording()
        } catch (_: Exception) {
            val recordings = repository.getRecordings()
            recordings.firstOrNull {
                it.state == "active" || it.state == "paused" || it.status == "active" || it.status == "paused"
            }
        }
        abandonedRecording.value = active
    }

    fun checkForAbandonedRecording() {
        viewModelScope.launch {
            try {
                syncAbandonedState()
            } catch (_: Exception) {
                abandonedRecording.value = null
            }
        }
    }

    fun recoverAbandonedRecording(onFinished: ((Int) -> Unit)? = null) {
        viewModelScope.launch {
            isRecovering.value = true
            errorMessage.value = null
            try {
                val targetId = abandonedRecording.value?.id ?: activeRecording.value?.id
                val rec = repository.recoverActiveRecording(targetId)
                abandonedRecording.value = null
                if (rec.state == "processing" || rec.state == "stopped" || (rec.durationMs != null && rec.durationMs > 0)) {
                    activeRecording.value = rec
                    recordingState.value = "processing"
                    pollTranscription(rec.id) { id ->
                        onFinished?.invoke(id)
                    }
                } else {
                    activeRecording.value = null
                    recordingState.value = "idle"
                    errorMessage.value = "Session #${rec.id} was safely closed."
                }
                syncAbandonedState()
            } catch (e: Exception) {
                errorMessage.value = "Recovery failed: ${e.message}"
                syncAbandonedState()
            } finally {
                isRecovering.value = false
            }
        }
    }

    fun discardAbandonedRecording() {
        viewModelScope.launch {
            isRecovering.value = true
            errorMessage.value = null
            try {
                val targetId = abandonedRecording.value?.id ?: activeRecording.value?.id
                if (targetId != null) {
                    val rec = repository.cancelRecording(targetId)
                    abandonedRecording.value = null
                    activeRecording.value = null
                    recordingState.value = "idle"
                    errorMessage.value = "Session #${rec.id} discarded successfully."
                }
                syncAbandonedState()
            } catch (e: Exception) {
                syncAbandonedState()
                if (abandonedRecording.value == null) {
                    activeRecording.value = null
                    recordingState.value = "idle"
                    errorMessage.value = "Session was already resolved on server."
                } else {
                    errorMessage.value = "Discard failed: ${e.message}"
                }
            } finally {
                isRecovering.value = false
            }
        }
    }

    private fun pollTranscription(recordingId: Int, onFinished: (Int) -> Unit) {
        viewModelScope.launch {
            recordingState.value = "processing"
            processingStage.value = "Transcribing audio..."
            var attempts = 0
            var terminalReached = false
            while (attempts < 45) {
                delay(2000)
                attempts++
                try {
                    val status = repository.getTranscriptionStatus(recordingId)
                    val st = status.status.lowercase()
                    when (st) {
                        "queued" -> {
                            processingStage.value = "Processing recording..."
                        }
                        "running" -> {
                            processingStage.value = "Transcribing audio..."
                        }
                        "retrying" -> {
                            processingStage.value = "Transcribing audio..."
                        }
                        "complete", "completed", "ready_for_review" -> {
                            processingStage.value = "Transcription complete. Preparing meeting notes..."
                            recordingState.value = "ready"
                            terminalReached = true
                            val resolvedConvId = try {
                                repository.getConversationDetail(recordingId).id
                            } catch (_: Exception) {
                                recordingId
                            }
                            try { repository.processExtraction(resolvedConvId) } catch (_: Exception) {}
                            onFinished(resolvedConvId)
                            break
                        }
                        "failed" -> {
                            recordingState.value = "failed"
                            errorMessage.value = status.lastErrorMessage ?: "Unable to complete transcription. Please try again."
                            terminalReached = true
                            break
                        }
                    }
                } catch (_: Exception) {}
            }
            if (!terminalReached) {
                recordingState.value = "idle"
                errorMessage.value = "Processing is continuing in the background. Check your conversations list shortly."
            }
        }
    }

    private fun startTimer() {
        viewModelScope.launch {
            while (recordingState.value == "recording") {
                delay(1000)
                durationSeconds.value += 1
            }
        }
    }
}

// ConversationsViewModel
class ConversationsViewModel(val repository: PcmaRepository) : ViewModel() {
    val conversations = MutableStateFlow<List<ConversationResponse>>(emptyList())
    val selectedConversationId = MutableStateFlow<Int?>(null)
    val activeConversation = MutableStateFlow<ConversationResponse?>(null)
    val transcript = MutableStateFlow<TranscriptResponse?>(null)
    val extractions = MutableStateFlow<ConversationExtractionsResponse?>(null)
    val people = MutableStateFlow<List<PersonResponse>>(emptyList())
    val isLoading = MutableStateFlow(false)
    val errorMessage = MutableStateFlow<String?>(null)
    val isExtracting = MutableStateFlow(false)
    val extractionError = MutableStateFlow<String?>(null)

    fun selectConversation(id: Int) {
        selectedConversationId.value = id
    }

    fun loadConversations() {
        viewModelScope.launch {
            isLoading.value = true
            errorMessage.value = null
            try {
                conversations.value = repository.getConversations()
            } catch (e: Exception) {
                if (e is com.pcma.app.data.api.ApiException && (e.statusCode == 401 || e.message?.contains("expired", ignoreCase = true) == true)) {
                    val refreshed = repository.refreshAuthToken()
                    if (refreshed) {
                        try {
                            conversations.value = repository.getConversations()
                            return@launch
                        } catch (retryEx: Exception) {
                            errorMessage.value = retryEx.message ?: "Unable to load conversations. Please try again."
                            return@launch
                        }
                    }
                }
                try { Log.e("PCMA_CONV", "Failed to load conversations: ${e.message}", e) } catch (_: Throwable) {}
                errorMessage.value = e.message ?: "Unable to connect to server. Please try again."
            } finally {
                isLoading.value = false
            }
        }
    }

    fun loadConversationDetail(id: Int) {
        selectedConversationId.value = id
        viewModelScope.launch {
            isLoading.value = true
            errorMessage.value = null
            try {
                val detail = repository.getConversationDetail(id)
                activeConversation.value = detail
                selectedConversationId.value = detail.id
                val targetRecId = detail.recordingId ?: detail.id
                try { transcript.value = repository.getTranscript(targetRecId) } catch (e: Exception) {
                    try { Log.w("PCMA_CONV", "Transcript fetch warning: ${e.message}") } catch (_: Throwable) {}
                }
                try { extractions.value = repository.getExtractions(detail.id) } catch (e: Exception) {
                    try { Log.w("PCMA_CONV", "Extractions fetch warning: ${e.message}") } catch (_: Throwable) {}
                }
                try { people.value = repository.getPeople() } catch (e: Exception) {
                    try { Log.w("PCMA_CONV", "People fetch warning: ${e.message}") } catch (_: Throwable) {}
                }
            } catch (e: Exception) {
                if (e is com.pcma.app.data.api.ApiException && (e.statusCode == 401 || e.message?.contains("expired", ignoreCase = true) == true)) {
                    val refreshed = repository.refreshAuthToken()
                    if (refreshed) {
                        try {
                            val detail = repository.getConversationDetail(id)
                            activeConversation.value = detail
                            selectedConversationId.value = detail.id
                            return@launch
                        } catch (_: Exception) {}
                    }
                }
                try { Log.e("PCMA_CONV", "Failed to load conversation detail: ${e.message}", e) } catch (_: Throwable) {}
                errorMessage.value = e.message ?: "Unable to load conversation details. Please try again."
            } finally {
                isLoading.value = false
            }
        }
    }

    fun retryExtraction(conversationId: Int) {
        viewModelScope.launch {
            isExtracting.value = true
            extractionError.value = null
            try {
                repository.processExtraction(conversationId)
                loadConversationDetail(conversationId)
            } catch (e: Exception) {
                extractionError.value = e.message ?: "Unable to analyze conversation. Please try again."
            } finally {
                isExtracting.value = false
            }
        }
    }

    val isCorrectingSegment = MutableStateFlow(false)
    val correctionError = MutableStateFlow<String?>(null)

    fun relabelSpeaker(recordingId: Int, speakerId: Int, label: String?, personId: Int?) {
        viewModelScope.launch {
            try {
                repository.relabelSpeaker(recordingId, speakerId, label, personId)
                transcript.value = repository.getTranscript(recordingId)
                selectedConversationId.value?.let { loadConversationDetail(it) }
            } catch (_: Exception) {}
        }
    }

    fun correctSegment(
        recordingId: Int,
        segmentId: Int,
        newText: String,
        reExtract: Boolean,
        onComplete: ((Boolean) -> Unit)? = null
    ) {
        viewModelScope.launch {
            isCorrectingSegment.value = true
            correctionError.value = null
            try {
                repository.correctSegment(recordingId, segmentId, newText, reExtract)
                transcript.value = repository.getTranscript(recordingId)
                selectedConversationId.value?.let { convId ->
                    loadConversationDetail(convId)
                }
                onComplete?.invoke(true)
            } catch (e: Exception) {
                correctionError.value = e.message ?: "Unable to update transcript. Please try again."
                onComplete?.invoke(false)
            } finally {
                isCorrectingSegment.value = false
            }
        }
    }
}

// MomViewModel
class MomViewModel(val repository: PcmaRepository) : ViewModel() {
    val selectedConversationId = MutableStateFlow<Int?>(null)
    val currentMom = MutableStateFlow<MomResponse?>(null)
    val history = MutableStateFlow<List<MomHistoryResponse>>(emptyList())
    val shares = MutableStateFlow<List<MomShareResponse>>(emptyList())
    val isLoading = MutableStateFlow(false)
    val errorMessage = MutableStateFlow<String?>(null)
    val momNotFound = MutableStateFlow(false)

    fun selectConversation(conversationId: Int) {
        selectedConversationId.value = conversationId
        loadMom(conversationId)
    }

    fun loadMom(conversationId: Int) {
        selectedConversationId.value = conversationId
        viewModelScope.launch {
            isLoading.value = true
            errorMessage.value = null
            momNotFound.value = false
            try {
                val mom = repository.getMom(conversationId)
                currentMom.value = mom
                if (mom != null) {
                    momNotFound.value = false
                    try { history.value = repository.getMomHistory(mom.id) } catch (_: Exception) {}
                    try { shares.value = repository.getMomShares(mom.id) } catch (_: Exception) {}
                } else {
                    momNotFound.value = true
                    history.value = emptyList()
                    shares.value = emptyList()
                }
            } catch (e: Exception) {
                currentMom.value = null
                momNotFound.value = false
                errorMessage.value = e.message ?: "Unable to load meeting notes"
            } finally {
                isLoading.value = false
            }
        }
    }

    fun generateMom(conversationId: Int) {
        selectedConversationId.value = conversationId
        viewModelScope.launch {
            isLoading.value = true
            errorMessage.value = null
            try {
                val mom = repository.generateMom(conversationId)
                currentMom.value = mom
                momNotFound.value = false
                try { history.value = repository.getMomHistory(mom.id) } catch (_: Exception) {}
                try { shares.value = repository.getMomShares(mom.id) } catch (_: Exception) {}
            } catch (e: Exception) {
                errorMessage.value = e.message ?: "Unable to generate meeting notes"
            } finally {
                isLoading.value = false
            }
        }
    }

    fun approveMom(momId: Int, confirmedReview: Boolean = false) {
        viewModelScope.launch {
            isLoading.value = true
            errorMessage.value = null
            try {
                currentMom.value = repository.approveMom(momId, confirmedReview)
            } catch (e: Exception) {
                errorMessage.value = e.message ?: "Unable to approve meeting notes"
            } finally {
                isLoading.value = false
            }
        }
    }
}

// SearchViewModel
class SearchViewModel(val repository: PcmaRepository) : ViewModel() {
    val searchResults = MutableStateFlow<List<ConversationResponse>>(emptyList())
    val memories = MutableStateFlow<List<MemoryResponse>>(emptyList())
    val isSearching = MutableStateFlow(false)

    fun executeSearch(query: String?) {
        viewModelScope.launch {
            isSearching.value = true
            try {
                searchResults.value = repository.searchConversations(query)
            } catch (_: Exception) {} finally {
                isSearching.value = false
            }
        }
    }

    fun loadMemories() {
        viewModelScope.launch {
            try {
                memories.value = repository.getPersonalMemories()
            } catch (_: Exception) {}
        }
    }
}

// EntitiesViewModel
class EntitiesViewModel(val repository: PcmaRepository) : ViewModel() {
    val people = MutableStateFlow<List<PersonResponse>>(emptyList())
    val projects = MutableStateFlow<List<ProjectResponse>>(emptyList())
    val topics = MutableStateFlow<List<TopicResponse>>(emptyList())

    fun loadEntities() {
        viewModelScope.launch {
            try { people.value = repository.getPeople() } catch (_: Exception) {}
            try { projects.value = repository.getProjects() } catch (_: Exception) {}
            try { topics.value = repository.getTopics() } catch (_: Exception) {}
        }
    }
}

// CommitmentsViewModel
class CommitmentsViewModel(val repository: PcmaRepository) : ViewModel() {
    val commitments = MutableStateFlow<List<CommitmentResponse>>(emptyList())
    val reminders = MutableStateFlow<List<ReminderResponse>>(emptyList())

    fun loadData() {
        viewModelScope.launch {
            try { commitments.value = repository.getCommitments() } catch (_: Exception) {}
            try { reminders.value = repository.getReminders() } catch (_: Exception) {}
        }
    }

    fun updateStatus(id: Int, status: String) {
        viewModelScope.launch {
            try {
                repository.updateCommitmentStatus(id, status)
                commitments.value = repository.getCommitments()
            } catch (_: Exception) {}
        }
    }
}

// AssistantViewModel
class AssistantViewModel(val repository: PcmaRepository) : ViewModel() {
    val messages = MutableStateFlow<List<Pair<String, AssistantQueryResponse?>>>(emptyList())
    val isLoading = MutableStateFlow(false)

    fun askQuery(query: String) {
        viewModelScope.launch {
            val list = messages.value.toMutableList()
            list.add(Pair(query, null))
            messages.value = list
            isLoading.value = true

            try {
                val res = repository.askAssistant(query)
                val updatedList = messages.value.toMutableList()
                val lastIdx = updatedList.size - 1
                if (lastIdx >= 0) {
                    updatedList[lastIdx] = Pair(query, res)
                }
                messages.value = updatedList
            } catch (e: Exception) {
                val updatedList = messages.value.toMutableList()
                val lastIdx = updatedList.size - 1
                if (lastIdx >= 0) {
                    updatedList[lastIdx] = Pair(query, AssistantQueryResponse(answer = "Error: ${e.message}"))
                }
                messages.value = updatedList
            } finally {
                isLoading.value = false
            }
        }
    }
}

// SettingsViewModel
class SettingsViewModel(val repository: PcmaRepository) : ViewModel() {
    fun wipeData(onSuccess: () -> Unit) {
        viewModelScope.launch {
            try {
                repository.deleteUserData()
                onSuccess()
            } catch (_: Exception) {}
        }
    }

    fun deleteAccount(onSuccess: () -> Unit) {
        viewModelScope.launch {
            try {
                repository.deleteAccount()
                onSuccess()
            } catch (_: Exception) {}
        }
    }
}
