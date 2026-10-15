package com.pcma.app.data.models

import com.google.gson.annotations.SerializedName

data class UserResponse(
    val id: Int,
    @SerializedName("auth_id") val authId: String,
    @SerializedName("created_at") val createdAt: String
)

data class ProfileResponse(
    val id: Int,
    @SerializedName("user_id") val userId: Int,
    val jurisdiction: String?,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("updated_at") val updatedAt: String
)

data class ProfileUpdateRequest(
    val jurisdiction: String
)

data class RecordingStartRequest(
    @SerializedName("audio_source") val audioSource: String = "phone_microphone",
    @SerializedName("source_available") val sourceAvailable: Boolean = true,
    @SerializedName("microphone_permission_granted") val microphonePermissionGranted: Boolean = true,
    @SerializedName("consent_acknowledged") val consentAcknowledged: Boolean = false
)

data class AudioSourceChangeRequest(
    @SerializedName("audio_source") val audioSource: String,
    @SerializedName("source_available") val sourceAvailable: Boolean = true
)

data class RecordingResponse(
    val id: Int,
    @SerializedName("user_id") val userId: Int,
    val state: String?,
    val status: String = "active",
    @SerializedName("audio_source") val audioSource: String?,
    @SerializedName("started_at") val startedAt: String?,
    @SerializedName("stopped_at") val stoppedAt: String?,
    @SerializedName("duration_ms") val durationMs: Long?,
    @SerializedName("created_at") val createdAt: String
)

data class AudioFileResponse(
    val id: Int,
    @SerializedName("recording_id") val recordingId: Int,
    @SerializedName("storage_ref") val storageRef: String,
    @SerializedName("content_type") val contentType: String,
    @SerializedName("size_bytes") val sizeBytes: Long,
    @SerializedName("duration_ms") val durationMs: Long?,
    @SerializedName("created_at") val createdAt: String
)

data class TranscriptionStatusResponse(
    val id: Int,
    @SerializedName("recording_id") val recordingId: Int,
    val status: String,
    @SerializedName("attempts_count") val attemptsCount: Int = 0,
    @SerializedName("last_error_code") val lastErrorCode: String? = null,
    @SerializedName("last_error_message") val lastErrorMessage: String? = null,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("updated_at") val updatedAt: String
)

data class SegmentResponse(
    @SerializedName("id") val id: Int? = null,
    @SerializedName("speaker_id") val speakerId: Int? = null,
    @SerializedName("speaker_label") val speakerLabel: String? = null,
    @SerializedName("speaker_tag") val speakerTag: Int? = null,
    @SerializedName("start_ms") val startMs: Long,
    @SerializedName("end_ms") val endMs: Long,
    val text: String
)

data class SpeakerResponse(
    val id: Int,
    @SerializedName("speaker_tag") val speakerTag: Int? = null,
    val label: String? = null,
    val name: String? = null,
    @SerializedName("person_id") val personId: Int? = null,
    val confidence: Float? = null,
    val uncertain: Boolean? = null,
    @SerializedName("is_user") val isUser: Boolean? = null,
    val confirmed: Boolean? = null
)

data class SpeakerRelabelRequest(
    val label: String? = null,
    @SerializedName("person_id") val personId: Int? = null
)

data class SegmentCorrectionRequest(
    val text: String,
    @SerializedName("re_extract") val reExtract: Boolean = false
)

data class TranscriptResponse(
    val id: Int,
    @SerializedName("recording_id") val recordingId: Int,
    val language: String?,
    val segments: List<SegmentResponse> = emptyList(),
    val speakers: List<SpeakerResponse> = emptyList()
)

data class TopicResponse(
    val id: Int?,
    val name: String,
    val summary: String? = null,
    val confidence: Float? = null,
    @SerializedName("is_uncertain") val isUncertain: Boolean? = null
)

data class ActionItemResponse(
    val id: Int?,
    val title: String? = null,
    val description: String? = null,
    val text: String? = null,
    val assignee: String? = null,
    @SerializedName("assignee_name") val assigneeName: String? = null,
    val status: String = "open",
    val confidence: Float? = null,
    val provenance: String? = null,
    @SerializedName("is_uncertain") val isUncertain: Boolean? = false,
    @SerializedName("source_segment_ids") val sourceSegmentIds: List<Int> = emptyList()
)

data class CommitmentResponse(
    val id: Int?,
    val title: String? = null,
    val text: String? = null,
    @SerializedName("commitment_text") val commitmentText: String? = null,
    @SerializedName("promiser_name") val promiserName: String? = null,
    val status: String = "open",
    @SerializedName("due_date") val dueDate: String? = null,
    val confidence: Float? = null,
    @SerializedName("is_uncertain") val isUncertain: Boolean? = false,
    @SerializedName("source_segment_ids") val sourceSegmentIds: List<Int> = emptyList()
)

data class CommitmentUpdateRequest(
    val status: String
)

data class DecisionResponse(
    val id: Int?,
    val description: String? = null,
    val text: String? = null,
    val confidence: Float? = null,
    @SerializedName("is_uncertain") val isUncertain: Boolean? = false,
    @SerializedName("source_segment_ids") val sourceSegmentIds: List<Int> = emptyList()
)

data class DeadlineResponse(
    val id: Int?,
    val title: String? = null,
    val description: String? = null,
    @SerializedName("raw_deadline_text") val rawDeadlineText: String? = null,
    @SerializedName("due_date") val dueDate: String? = null,
    val confidence: Float? = null,
    @SerializedName("is_uncertain") val isUncertain: Boolean? = false,
    @SerializedName("source_segment_ids") val sourceSegmentIds: List<Int> = emptyList()
)

data class QuestionResponse(
    val id: Int?,
    val question: String? = null,
    @SerializedName("question_text") val questionText: String? = null,
    @SerializedName("asker_name") val askerName: String? = null,
    @SerializedName("answer_text") val answerText: String? = null,
    val status: String? = null,
    val confidence: Float? = null,
    @SerializedName("is_uncertain") val isUncertain: Boolean? = false,
    @SerializedName("source_segment_ids") val sourceSegmentIds: List<Int> = emptyList()
)

data class AIExtractionInfo(
    val id: Int? = null,
    @SerializedName("conversation_id") val conversationId: Int? = null,
    val stage: String? = null,
    val status: String? = null,
    @SerializedName("model_used") val modelUsed: String? = null,
    val provider: String? = null,
    @SerializedName("prompt_tokens") val promptTokens: Int? = null,
    @SerializedName("completion_tokens") val completionTokens: Int? = null,
    @SerializedName("estimated_cost") val estimatedCost: Float? = null,
    @SerializedName("created_at") val createdAt: String? = null
)

data class ConversationExtractionsResponse(
    @SerializedName("conversation_id") val conversationId: Int,
    val topics: List<TopicResponse> = emptyList(),
    val decisions: List<DecisionResponse> = emptyList(),
    @SerializedName("action_items") val actionItems: List<ActionItemResponse> = emptyList(),
    val commitments: List<CommitmentResponse> = emptyList(),
    val deadlines: List<DeadlineResponse> = emptyList(),
    val questions: List<QuestionResponse> = emptyList(),
    val extraction: AIExtractionInfo? = null
)

data class PersonResponse(
    val id: Int,
    val name: String,
    val email: String? = null,
    val organization: String? = null,
    val title: String? = null
)

data class PersonCreateRequest(
    val name: String,
    val email: String? = null,
    val organization: String? = null,
    val title: String? = null
)

data class MergePeopleRequest(
    @SerializedName("source_person_id") val sourcePersonId: Int,
    @SerializedName("target_person_id") val targetPersonId: Int
)

data class ProjectResponse(
    val id: Int,
    val name: String,
    val description: String? = null
)

data class ProjectCreateRequest(
    val name: String,
    val description: String? = null
)

data class MergeTopicsRequest(
    @SerializedName("source_topic_id") val sourceTopicId: Int,
    @SerializedName("target_topic_id") val targetTopicId: Int
)

data class ConversationResponse(
    val id: Int,
    @SerializedName("recording_id") val recordingId: Int?,
    @SerializedName("user_id") val userId: Int,
    val title: String? = null,
    @SerializedName("occurred_at") val occurredAt: String?,
    @SerializedName("created_at") val createdAt: String? = null,
    val snippet: String? = null,
    val status: String? = null,
    val state: String? = null,
    val topics: List<TopicResponse> = emptyList(),
    @SerializedName("action_items") val actionItems: List<ActionItemResponse> = emptyList(),
    val commitments: List<CommitmentResponse> = emptyList(),
    val decisions: List<DecisionResponse> = emptyList(),
    val deadlines: List<DeadlineResponse> = emptyList(),
    val questions: List<QuestionResponse> = emptyList(),
    val people: List<PersonResponse> = emptyList(),
    val organizations: List<TopicResponse> = emptyList()
)

data class MomSection(
    val id: Int? = null,
    @SerializedName("mom_id") val momId: Int? = null,
    @SerializedName("section_type") val sectionType: String? = null,
    val title: String? = null,
    val heading: String? = null,
    @SerializedName("content_json") val contentJson: String? = null,
    val content: String? = null
)

data class MomResponse(
    val id: Int,
    @SerializedName("conversation_id") val conversationId: Int,
    val title: String,
    val summary: String,
    val status: String = "draft",
    val confidence: Float? = null,
    @SerializedName("is_uncertain") val isUncertain: Boolean? = null,
    @SerializedName("is_user_edited") val isUserEdited: Boolean? = null,
    val sections: List<MomSection> = emptyList(),
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("approved_at") val approvedAt: String? = null
)

data class ApproveMomRequest(
    @SerializedName("confirmed_review") val confirmedReview: Boolean = false
)

data class MomUpdateRequest(
    val title: String? = null,
    val summary: String? = null
)

data class MomHistoryResponse(
    val id: Int,
    @SerializedName("mom_id") val momId: Int,
    val summary: String,
    @SerializedName("edited_at") val editedAt: String?,
    @SerializedName("created_at") val createdAt: String?
)

data class MomShareRequest(
    @SerializedName("recipient_email") val recipientEmail: String
)

data class MomShareResponse(
    val id: Int,
    @SerializedName("mom_id") val momId: Int,
    @SerializedName("recipient_email") val recipientEmail: String,
    @SerializedName("created_at") val createdAt: String
)

data class MemoryResponse(
    val id: Int,
    @SerializedName("user_id") val userId: Int,
    @SerializedName("conversation_id") val conversationId: Int?,
    val content: String?,
    @SerializedName("memory_text") val memoryText: String?,
    @SerializedName("created_at") val createdAt: String
)

data class ReminderResponse(
    val id: Int,
    @SerializedName("user_id") val userId: Int,
    val title: String,
    @SerializedName("remind_at") val remindAt: String,
    val timezone: String = "UTC",
    val status: String = "pending",
    val priority: String = "normal"
)

data class ReminderCreateRequest(
    val title: String,
    @SerializedName("remind_at") val remindAt: String,
    val timezone: String = "UTC",
    val priority: String = "normal",
    @SerializedName("commitment_id") val commitmentId: Int? = null,
    @SerializedName("action_item_id") val actionItemId: Int? = null,
    @SerializedName("deadline_id") val deadlineId: Int? = null
)

data class ReminderUpdateRequest(
    val status: String
)

data class AssistantQueryRequest(
    val query: String
)

data class AssistantQueryResponse(
    val answer: String,
    @SerializedName("source_ids") val sourceIds: List<Int> = emptyList(),
    val confidence: Float? = null
)

data class OfflineOperation(
    val id: String,
    val type: String,
    val payload: String,
    @SerializedName("created_at") val createdAt: String
)

data class SyncRequest(
    @SerializedName("client_sync_id") val clientSyncId: String,
    val operations: List<OfflineOperation> = emptyList()
)

data class SyncResponse(
    val status: String = "success",
    @SerializedName("processed_operations_count") val processedOperationsCount: Int = 0
)

data class ErrorDetail(
    val code: String? = null,
    val message: String? = null
)

data class ApiErrorResponse(
    val detail: Any? = null
)
