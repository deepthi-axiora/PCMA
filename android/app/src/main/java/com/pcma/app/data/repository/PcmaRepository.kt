package com.pcma.app.data.repository

import com.pcma.app.data.api.ApiClient
import com.pcma.app.data.local.OfflineQueueManager
import com.pcma.app.data.local.SecureTokenStorage
import com.pcma.app.data.models.*
import java.io.File
import kotlin.coroutines.resume

open class PcmaRepository(
    storage: SecureTokenStorage? = null,
    offlineQueue: OfflineQueueManager? = null,
    api: ApiClient? = null
) {
    private val _storage: SecureTokenStorage? = storage
    private val _offlineQueue: OfflineQueueManager? = offlineQueue
    private val _api: ApiClient? = api ?: storage?.let { ApiClient(it) }

    open val storage: SecureTokenStorage
        get() = _storage ?: throw IllegalStateException("SecureTokenStorage is not configured")

    val offlineQueue: OfflineQueueManager
        get() = _offlineQueue ?: throw IllegalStateException("OfflineQueueManager is not configured")

    private val api: ApiClient
        get() = _api ?: throw IllegalStateException("ApiClient is not configured")

    // Auth & Profile
    suspend fun getMe(): UserResponse = api.getMe()
    open suspend fun getProfile(): ProfileResponse = api.getProfile()
    suspend fun updateProfile(jurisdiction: String): ProfileResponse {
        storage.jurisdiction = jurisdiction
        return api.updateProfile(ProfileUpdateRequest(jurisdiction))
    }

    open suspend fun refreshAuthToken(): Boolean = kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) {
        val refreshToken = try { storage.refreshToken } catch (_: Exception) { null }
        if (refreshToken.isNullOrEmpty()) return@withContext false

        return@withContext try {
            val account = com.auth0.android.Auth0(
                com.pcma.app.BuildConfig.AUTH0_CLIENT_ID,
                com.pcma.app.BuildConfig.AUTH0_DOMAIN
            )
            val authClient = com.auth0.android.authentication.AuthenticationAPIClient(account)
            kotlinx.coroutines.suspendCancellableCoroutine { continuation ->
                authClient.renewAuth(refreshToken)
                    .start(object : com.auth0.android.callback.Callback<com.auth0.android.result.Credentials, com.auth0.android.authentication.AuthenticationException> {
                        override fun onSuccess(credentials: com.auth0.android.result.Credentials) {
                            val newAccess = credentials.accessToken
                            val newRefresh = credentials.refreshToken
                            if (!newAccess.isNullOrEmpty()) {
                                storage.accessToken = newAccess
                            }
                            if (!newRefresh.isNullOrEmpty()) {
                                storage.refreshToken = newRefresh
                            }
                            if (continuation.isActive) {
                                continuation.resume(true)
                            }
                        }

                        override fun onFailure(error: com.auth0.android.authentication.AuthenticationException) {
                            if (continuation.isActive) {
                                continuation.resume(false)
                            }
                        }
                    })
            }
        } catch (_: Exception) {
            false
        }
    }

    // Recordings
    open suspend fun startRecording(
        audioSource: String = "phone_microphone",
        sourceAvailable: Boolean = true,
        microphonePermissionGranted: Boolean = true,
        consentAcknowledged: Boolean = false
    ): RecordingResponse =
        api.createRecording(
            RecordingStartRequest(
                audioSource = audioSource,
                sourceAvailable = sourceAvailable,
                microphonePermissionGranted = microphonePermissionGranted,
                consentAcknowledged = consentAcknowledged
            )
        )

    open suspend fun getRecordings(): List<RecordingResponse> = api.getRecordings().toList()
    open suspend fun getActiveRecording(): RecordingResponse? = api.getActiveRecording()

    open suspend fun pauseRecording(id: Int): RecordingResponse = api.pauseRecording(id)
    open suspend fun resumeRecording(id: Int): RecordingResponse = api.resumeRecording(id)
    open suspend fun stopRecording(id: Int): RecordingResponse = api.stopRecording(id)
    open suspend fun cancelRecording(id: Int): RecordingResponse = api.cancelRecording(id)
    open suspend fun cancelRecording(): RecordingResponse = api.cancelRecording(null)
    open suspend fun recoverActiveRecording(id: Int? = null): RecordingResponse = api.recoverActiveRecording(id)
    open suspend fun setAudioSource(id: Int, source: String): RecordingResponse =
        api.setAudioSource(id, AudioSourceChangeRequest(audioSource = source))

    open suspend fun uploadAudio(id: Int, audioFile: File, durationMs: Long?): AudioFileResponse =
        api.uploadAudio(id, audioFile, durationMs)

    // Transcription & Diarization
    open suspend fun getTranscriptionStatus(id: Int): TranscriptionStatusResponse = api.getTranscriptionStatus(id)
    open suspend fun getTranscript(id: Int): TranscriptResponse = api.getTranscript(id)
    open suspend fun retryTranscription(id: Int): TranscriptionStatusResponse = api.retryTranscription(id)
    open suspend fun relabelSpeaker(recordingId: Int, speakerId: Int, label: String?, personId: Int?): SpeakerResponse =
        api.relabelSpeaker(recordingId, speakerId, SpeakerRelabelRequest(label, personId))

    open suspend fun correctSegment(recordingId: Int, segmentId: Int, text: String, reExtract: Boolean): SegmentResponse =
        api.correctSegment(recordingId, segmentId, SegmentCorrectionRequest(text, reExtract))

    // Conversations
    open suspend fun getConversations(): List<ConversationResponse> = api.getConversations().toList()
    open suspend fun getConversationDetail(id: Int): ConversationResponse = api.getConversationDetail(id)
    open suspend fun processExtraction(id: Int): ConversationResponse = api.processExtraction(id)
    open suspend fun getExtractions(id: Int): ConversationExtractionsResponse = api.getExtractions(id)

    // MOM
    open suspend fun generateMom(conversationId: Int): MomResponse = api.generateMom(conversationId)
    open suspend fun getMom(conversationId: Int): MomResponse? {
        return try {
            api.getMom(conversationId)
        } catch (e: com.pcma.app.data.api.ApiException) {
            if (e.statusCode == 404) null else throw e
        } catch (e: Exception) {
            if (e.message?.contains("404") == true || e.message?.contains("not found", ignoreCase = true) == true) {
                null
            } else {
                throw e
            }
        }
    }
    open suspend fun updateMom(momId: Int, title: String?, summary: String?): MomResponse =
        api.updateMom(momId, MomUpdateRequest(title, summary))
    open suspend fun approveMom(momId: Int, confirmedReview: Boolean = false): MomResponse =
        api.approveMom(momId, confirmedReview)
    open suspend fun getMomHistory(momId: Int): List<MomHistoryResponse> = api.getMomHistory(momId).toList()
    open suspend fun shareMom(momId: Int, recipientEmail: String): MomShareResponse =
        api.shareMom(momId, MomShareRequest(recipientEmail))
    open suspend fun getMomShares(momId: Int): List<MomShareResponse> = api.getMomShares(momId).toList()
    open suspend fun revokeMomShare(momId: Int, shareId: Int) = api.revokeMomShare(momId, shareId)

    // Entities
    suspend fun getPeople(): List<PersonResponse> = api.getPeople().toList()
    suspend fun createPerson(name: String, email: String?, org: String?, title: String?): PersonResponse =
        api.createPerson(PersonCreateRequest(name, email, org, title))
    suspend fun mergePeople(sourceId: Int, targetId: Int): PersonResponse =
        api.mergePeople(MergePeopleRequest(sourceId, targetId))

    suspend fun getProjects(): List<ProjectResponse> = api.getProjects().toList()
    suspend fun createProject(name: String, desc: String?): ProjectResponse =
        api.createProject(ProjectCreateRequest(name, desc))

    suspend fun getTopics(): List<TopicResponse> = api.getTopics().toList()
    suspend fun mergeTopics(sourceId: Int, targetId: Int): TopicResponse =
        api.mergeTopics(MergeTopicsRequest(sourceId, targetId))

    // Search & Memory
    suspend fun searchConversations(query: String?): List<ConversationResponse> =
        api.searchConversations(query).toList()
    suspend fun getPersonalMemories(): List<MemoryResponse> = api.getPersonalMemories().toList()

    // Commitments & Reminders
    suspend fun getCommitments(): List<CommitmentResponse> = api.getCommitments().toList()
    suspend fun updateCommitmentStatus(id: Int, status: String): CommitmentResponse =
        api.updateCommitmentStatus(id, CommitmentUpdateRequest(status))
    suspend fun getReminders(): List<ReminderResponse> = api.getReminders().toList()
    suspend fun createReminder(title: String, remindAt: String, priority: String = "normal"): ReminderResponse =
        api.createReminder(ReminderCreateRequest(title = title, remindAt = remindAt, priority = priority))
    suspend fun deleteReminder(id: Int) = api.deleteReminder(id)

    // Assistant
    suspend fun askAssistant(query: String): AssistantQueryResponse =
        api.askAssistant(AssistantQueryRequest(query))

    // Sync
    suspend fun triggerSync(): SyncResponse {
        val queue = offlineQueue.getQueue()
        val res = api.syncOfflineOperations(SyncRequest(clientSyncId = "sync_${System.currentTimeMillis()}", operations = queue))
        offlineQueue.clearQueue()
        return res
    }

    // Privacy
    suspend fun deleteUserData() = api.deleteUserData()
    suspend fun deleteAccount() {
        api.deleteAccount()
        storage.clearSession()
    }
}
