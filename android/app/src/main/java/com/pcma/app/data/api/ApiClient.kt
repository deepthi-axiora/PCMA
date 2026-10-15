package com.pcma.app.data.api

import com.google.gson.Gson
import com.pcma.app.data.local.SecureTokenStorage
import com.pcma.app.data.models.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.File
import java.io.IOException

class ApiException(val statusCode: Int, message: String) : IOException(message)

class ApiClient(private val storage: SecureTokenStorage) {

    private val client = OkHttpClient.Builder().build()
    private val gson = Gson()
    private val jsonMediaType = "application/json; charset=utf-8".toMediaType()

    private fun buildUrl(endpoint: String): String {
        val base = storage.baseUrl.trimEnd('/')
        val path = if (endpoint.startsWith("/")) endpoint else "/$endpoint"
        return "$base$path"
    }

    private suspend fun <T> executeRequest(
        request: Request,
        responseClass: Class<T>
    ): T = withContext(Dispatchers.IO) {
        val requestWithAuth = request.newBuilder().apply {
            val token = storage.accessToken
            if (!token.isNullOrEmpty()) {
                header("Authorization", "Bearer $token")
            } else if (storage.isDevMode) {
                header("Authorization", "Bearer dev-mock-jwt-token")
            }
        }.build()

        val response = try {
            client.newCall(requestWithAuth).execute()
        } catch (e: java.net.ConnectException) {
            throw ApiException(0, "Unable to reach server at ${storage.baseUrl}. Verify backend is running.")
        } catch (e: java.net.SocketTimeoutException) {
            throw ApiException(0, "Connection timed out connecting to ${storage.baseUrl}.")
        } catch (e: IOException) {
            throw ApiException(0, "Network failure: ${e.message ?: "Connection error"}")
        }

        response.use { resp ->
            val bodyString = resp.body?.string() ?: ""

            if (!resp.isSuccessful) {
                var extractedMsg: String? = null
                try {
                    val jsonElem = com.google.gson.JsonParser.parseString(bodyString)
                    if (jsonElem.isJsonObject) {
                        val root = jsonElem.asJsonObject
                        if (root.has("detail")) {
                            val detail = root.get("detail")
                            if (detail.isJsonObject) {
                                val dObj = detail.asJsonObject
                                if (dObj.has("message") && !dObj.get("message").isJsonNull) {
                                    extractedMsg = dObj.get("message").asString
                                }
                            } else if (detail.isJsonPrimitive) {
                                extractedMsg = detail.asString
                            }
                        } else if (root.has("message") && !root.get("message").isJsonNull) {
                            extractedMsg = root.get("message").asString
                        }
                    }
                } catch (_: Exception) {}

                val finalMessage = when {
                    !extractedMsg.isNullOrBlank() && extractedMsg != "Not Found" -> extractedMsg
                    resp.code == 404 -> "Resource not found on server (404: ${request.url.encodedPath})"
                    resp.code == 401 -> "Session expired or unauthorized (401)"
                    resp.code == 403 -> "Access denied (403)"
                    resp.code in 500..599 -> "Server error (${resp.code})"
                    else -> extractedMsg ?: "Request failed (${resp.code})"
                }
                throw ApiException(resp.code, finalMessage)
            }

            if (responseClass == Unit::class.java) {
                @Suppress("UNCHECKED_CAST")
                return@withContext Unit as T
            }

            gson.fromJson(bodyString, responseClass)
        }
    }

    // Profile API
    suspend fun getMe(): UserResponse = executeRequest(
        Request.Builder().url(buildUrl("/v1/me")).get().build(),
        UserResponse::class.java
    )

    suspend fun getProfile(): ProfileResponse = executeRequest(
        Request.Builder().url(buildUrl("/v1/profile")).get().build(),
        ProfileResponse::class.java
    )

    suspend fun updateProfile(req: ProfileUpdateRequest): ProfileResponse = executeRequest(
        Request.Builder().url(buildUrl("/v1/profile"))
            .patch(gson.toJson(req).toRequestBody(jsonMediaType)).build(),
        ProfileResponse::class.java
    )

    // Recordings API
    suspend fun createRecording(req: RecordingStartRequest): RecordingResponse = executeRequest(
        Request.Builder().url(buildUrl("/v1/recordings"))
            .post(gson.toJson(req).toRequestBody(jsonMediaType)).build(),
        RecordingResponse::class.java
    )

    suspend fun getRecordings(): Array<RecordingResponse> = executeRequest(
        Request.Builder().url(buildUrl("/v1/recordings")).get().build(),
        Array<RecordingResponse>::class.java
    )

    suspend fun getActiveRecording(): RecordingResponse? = withContext(Dispatchers.IO) {
        try {
            executeRequest(
                Request.Builder().url(buildUrl("/v1/recordings/active")).get().build(),
                RecordingResponse::class.java
            )
        } catch (e: ApiException) {
            if (e.statusCode == 404) null else throw e
        }
    }

    suspend fun pauseRecording(recordingId: Int): RecordingResponse = executeRequest(
        Request.Builder().url(buildUrl("/v1/recordings/$recordingId/pause"))
            .post("".toRequestBody(jsonMediaType)).build(),
        RecordingResponse::class.java
    )

    suspend fun resumeRecording(recordingId: Int): RecordingResponse = executeRequest(
        Request.Builder().url(buildUrl("/v1/recordings/$recordingId/resume"))
            .post("".toRequestBody(jsonMediaType)).build(),
        RecordingResponse::class.java
    )

    suspend fun stopRecording(recordingId: Int): RecordingResponse = executeRequest(
        Request.Builder().url(buildUrl("/v1/recordings/$recordingId/stop"))
            .post("".toRequestBody(jsonMediaType)).build(),
        RecordingResponse::class.java
    )

    suspend fun cancelRecording(recordingId: Int? = null): RecordingResponse {
        val url = if (recordingId != null) "/v1/recordings/$recordingId/cancel" else "/v1/recordings/cancel-active"
        return executeRequest(
            Request.Builder().url(buildUrl(url))
                .post("".toRequestBody(jsonMediaType)).build(),
            RecordingResponse::class.java
        )
    }

    suspend fun recoverActiveRecording(recordingId: Int? = null): RecordingResponse {
        val url = if (recordingId != null) "/v1/recordings/$recordingId/recover" else "/v1/recordings/recover-active"
        return executeRequest(
            Request.Builder().url(buildUrl(url))
                .post("".toRequestBody(jsonMediaType)).build(),
            RecordingResponse::class.java
        )
    }

    suspend fun setAudioSource(recordingId: Int, req: AudioSourceChangeRequest): RecordingResponse = executeRequest(
        Request.Builder().url(buildUrl("/v1/recordings/$recordingId/audio-source"))
            .patch(gson.toJson(req).toRequestBody(jsonMediaType)).build(),
        RecordingResponse::class.java
    )

    suspend fun uploadAudio(recordingId: Int, audioFile: File, durationMs: Long?): AudioFileResponse = withContext(Dispatchers.IO) {
        val fileBody = audioFile.asRequestBody("audio/wav".toMediaType())
        val multipart = MultipartBody.Builder()
            .setType(MultipartBody.FORM)
            .addFormDataPart("audio", audioFile.name, fileBody)
            .build()

        var url = buildUrl("/v1/recordings/$recordingId/audio")
        if (durationMs != null) {
            url += "?duration_ms=$durationMs"
        }

        val request = Request.Builder().url(url).post(multipart).build()
        executeRequest(request, AudioFileResponse::class.java)
    }

    // Transcription & Diarization API
    suspend fun getTranscriptionStatus(recordingId: Int): TranscriptionStatusResponse = executeRequest(
        Request.Builder().url(buildUrl("/v1/recordings/$recordingId/transcription-status")).get().build(),
        TranscriptionStatusResponse::class.java
    )

    suspend fun getTranscript(recordingId: Int): TranscriptResponse = executeRequest(
        Request.Builder().url(buildUrl("/v1/recordings/$recordingId/transcript")).get().build(),
        TranscriptResponse::class.java
    )

    suspend fun retryTranscription(recordingId: Int): TranscriptionStatusResponse = executeRequest(
        Request.Builder().url(buildUrl("/v1/recordings/$recordingId/transcription/retry"))
            .post("".toRequestBody(jsonMediaType)).build(),
        TranscriptionStatusResponse::class.java
    )

    suspend fun relabelSpeaker(recordingId: Int, speakerId: Int, req: SpeakerRelabelRequest): SpeakerResponse = executeRequest(
        Request.Builder().url(buildUrl("/v1/recordings/$recordingId/speakers/$speakerId"))
            .patch(gson.toJson(req).toRequestBody(jsonMediaType)).build(),
        SpeakerResponse::class.java
    )

    suspend fun correctSegment(recordingId: Int, segmentId: Int, req: SegmentCorrectionRequest): SegmentResponse = executeRequest(
        Request.Builder().url(buildUrl("/v1/recordings/$recordingId/segments/$segmentId"))
            .patch(gson.toJson(req).toRequestBody(jsonMediaType)).build(),
        SegmentResponse::class.java
    )

    // Conversations API
    suspend fun getConversations(): Array<ConversationResponse> = executeRequest(
        Request.Builder().url(buildUrl("/v1/conversations")).get().build(),
        Array<ConversationResponse>::class.java
    )

    suspend fun getConversationDetail(conversationId: Int): ConversationResponse = executeRequest(
        Request.Builder().url(buildUrl("/v1/conversations/$conversationId")).get().build(),
        ConversationResponse::class.java
    )

    suspend fun processExtraction(conversationId: Int): ConversationResponse = executeRequest(
        Request.Builder().url(buildUrl("/v1/conversations/$conversationId/process-extraction"))
            .post("".toRequestBody(jsonMediaType)).build(),
        ConversationResponse::class.java
    )

    suspend fun getExtractions(conversationId: Int): ConversationExtractionsResponse = executeRequest(
        Request.Builder().url(buildUrl("/v1/conversations/$conversationId/extractions")).get().build(),
        ConversationExtractionsResponse::class.java
    )

    // MOM API
    suspend fun generateMom(conversationId: Int): MomResponse = executeRequest(
        Request.Builder().url(buildUrl("/v1/conversations/$conversationId/mom/generate"))
            .post("".toRequestBody(jsonMediaType)).build(),
        MomResponse::class.java
    )

    suspend fun getMom(conversationId: Int): MomResponse = executeRequest(
        Request.Builder().url(buildUrl("/v1/conversations/$conversationId/mom")).get().build(),
        MomResponse::class.java
    )

    suspend fun updateMom(momId: Int, req: MomUpdateRequest): MomResponse = executeRequest(
        Request.Builder().url(buildUrl("/v1/moms/$momId"))
            .patch(gson.toJson(req).toRequestBody(jsonMediaType)).build(),
        MomResponse::class.java
    )

    suspend fun approveMom(momId: Int, confirmedReview: Boolean = false): MomResponse = executeRequest(
        Request.Builder().url(buildUrl("/v1/moms/$momId/approve"))
            .post(gson.toJson(ApproveMomRequest(confirmedReview = confirmedReview)).toRequestBody(jsonMediaType)).build(),
        MomResponse::class.java
    )

    suspend fun getMomHistory(momId: Int): Array<MomHistoryResponse> = executeRequest(
        Request.Builder().url(buildUrl("/v1/moms/$momId/history")).get().build(),
        Array<MomHistoryResponse>::class.java
    )

    suspend fun shareMom(momId: Int, req: MomShareRequest): MomShareResponse = executeRequest(
        Request.Builder().url(buildUrl("/v1/moms/$momId/share"))
            .post(gson.toJson(req).toRequestBody(jsonMediaType)).build(),
        MomShareResponse::class.java
    )

    suspend fun getMomShares(momId: Int): Array<MomShareResponse> = executeRequest(
        Request.Builder().url(buildUrl("/v1/moms/$momId/shares")).get().build(),
        Array<MomShareResponse>::class.java
    )

    suspend fun revokeMomShare(momId: Int, shareId: Int): Unit = executeRequest(
        Request.Builder().url(buildUrl("/v1/moms/$momId/shares/$shareId")).delete().build(),
        Unit::class.java
    )

    // Entities API
    suspend fun getPeople(): Array<PersonResponse> = executeRequest(
        Request.Builder().url(buildUrl("/v1/people")).get().build(),
        Array<PersonResponse>::class.java
    )

    suspend fun createPerson(req: PersonCreateRequest): PersonResponse = executeRequest(
        Request.Builder().url(buildUrl("/v1/people"))
            .post(gson.toJson(req).toRequestBody(jsonMediaType)).build(),
        PersonResponse::class.java
    )

    suspend fun mergePeople(req: MergePeopleRequest): PersonResponse = executeRequest(
        Request.Builder().url(buildUrl("/v1/people/merge"))
            .post(gson.toJson(req).toRequestBody(jsonMediaType)).build(),
        PersonResponse::class.java
    )

    suspend fun getProjects(): Array<ProjectResponse> = executeRequest(
        Request.Builder().url(buildUrl("/v1/projects")).get().build(),
        Array<ProjectResponse>::class.java
    )

    suspend fun createProject(req: ProjectCreateRequest): ProjectResponse = executeRequest(
        Request.Builder().url(buildUrl("/v1/projects"))
            .post(gson.toJson(req).toRequestBody(jsonMediaType)).build(),
        ProjectResponse::class.java
    )

    suspend fun getTopics(): Array<TopicResponse> = executeRequest(
        Request.Builder().url(buildUrl("/v1/topics")).get().build(),
        Array<TopicResponse>::class.java
    )

    suspend fun mergeTopics(req: MergeTopicsRequest): TopicResponse = executeRequest(
        Request.Builder().url(buildUrl("/v1/topics/merge"))
            .post(gson.toJson(req).toRequestBody(jsonMediaType)).build(),
        TopicResponse::class.java
    )

    // Search & Memory API
    suspend fun searchConversations(query: String?): Array<ConversationResponse> {
        var url = buildUrl("/v1/search")
        if (!query.isNullOrEmpty()) url += "?query=${java.net.URLEncoder.encode(query, "UTF-8")}"
        return executeRequest(Request.Builder().url(url).get().build(), Array<ConversationResponse>::class.java)
    }

    suspend fun getPersonalMemories(): Array<MemoryResponse> = executeRequest(
        Request.Builder().url(buildUrl("/v1/memory")).get().build(),
        Array<MemoryResponse>::class.java
    )

    // Commitments & Reminders API
    suspend fun getCommitments(): Array<CommitmentResponse> = executeRequest(
        Request.Builder().url(buildUrl("/v1/commitments")).get().build(),
        Array<CommitmentResponse>::class.java
    )

    suspend fun updateCommitmentStatus(id: Int, req: CommitmentUpdateRequest): CommitmentResponse = executeRequest(
        Request.Builder().url(buildUrl("/v1/commitments/$id"))
            .patch(gson.toJson(req).toRequestBody(jsonMediaType)).build(),
        CommitmentResponse::class.java
    )

    suspend fun getReminders(): Array<ReminderResponse> = executeRequest(
        Request.Builder().url(buildUrl("/v1/reminders")).get().build(),
        Array<ReminderResponse>::class.java
    )

    suspend fun createReminder(req: ReminderCreateRequest): ReminderResponse = executeRequest(
        Request.Builder().url(buildUrl("/v1/reminders"))
            .post(gson.toJson(req).toRequestBody(jsonMediaType)).build(),
        ReminderResponse::class.java
    )

    suspend fun deleteReminder(id: Int): Unit = executeRequest(
        Request.Builder().url(buildUrl("/v1/reminders/$id")).delete().build(),
        Unit::class.java
    )

    // Assistant API
    suspend fun askAssistant(req: AssistantQueryRequest): AssistantQueryResponse = executeRequest(
        Request.Builder().url(buildUrl("/v1/query"))
            .post(gson.toJson(req).toRequestBody(jsonMediaType)).build(),
        AssistantQueryResponse::class.java
    )

    // Sync API
    suspend fun syncOfflineOperations(req: SyncRequest): SyncResponse = executeRequest(
        Request.Builder().url(buildUrl("/v1/sync"))
            .post(gson.toJson(req).toRequestBody(jsonMediaType)).build(),
        SyncResponse::class.java
    )

    // Privacy API
    suspend fun deleteUserData(): Unit = executeRequest(
        Request.Builder().url(buildUrl("/v1/me/data")).delete().build(),
        Unit::class.java
    )

    suspend fun deleteAccount(): Unit = executeRequest(
        Request.Builder().url(buildUrl("/v1/me/account")).delete().build(),
        Unit::class.java
    )
}
