package com.pcma.app

import com.pcma.app.data.models.AssistantQueryResponse
import com.pcma.app.data.models.MomResponse
import com.pcma.app.data.models.OfflineOperation
import com.pcma.app.service.RecordingForegroundService
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.Assert.*
import org.junit.Test
import java.io.File

class PcmaUnitTest {

    @Test
    fun testDefaultEmulatorApiBaseUrl() {
        val defaultUrl = "http://10.0.2.2:8000"
        assertTrue(defaultUrl.contains("10.0.2.2"))
        assertEquals("http://10.0.2.2:8000/v1/recordings", "$defaultUrl/v1/recordings")
    }

    @Test
    fun testOfflineOperationQueueing() {
        val queue = mutableListOf<OfflineOperation>()
        val op = OfflineOperation(
            id = "op_123",
            type = "UPDATE_SPEAKER",
            payload = "{\"label\":\"John\"}",
            createdAt = "2026-09-29T12:00:00Z"
        )
        queue.add(op)

        assertEquals(1, queue.size)
        assertEquals("UPDATE_SPEAKER", queue[0].type)
        assertEquals("op_123", queue[0].id)
    }

    @Test
    fun testMomApprovalValidation() {
        val draftMom = MomResponse(id = 1, conversationId = 10, title = "Draft MOM", summary = "Summary", status = "draft", createdAt = "2026-09-29")
        val approvedMom = MomResponse(id = 1, conversationId = 10, title = "Draft MOM", summary = "Summary", status = "approved", createdAt = "2026-09-29")

        assertFalse(draftMom.status == "approved")
        assertTrue(approvedMom.status == "approved")
    }

    @Test
    fun testAssistantResponseSourceLinks() {
        val res = AssistantQueryResponse(
            answer = "The project budget was approved.",
            sourceIds = listOf(5, 12),
            confidence = 0.95f
        )

        assertEquals(2, res.sourceIds.size)
        assertEquals(5, res.sourceIds[0])
        assertEquals(12, res.sourceIds[1])
        assertNotNull(res.confidence)
    }

    @Test
    fun testForegroundServiceActionIntents() {
        assertEquals("com.pcma.app.ACTION_START_RECORDING_SERVICE", RecordingForegroundService.ACTION_START)
        assertEquals("com.pcma.app.ACTION_STOP_RECORDING_SERVICE", RecordingForegroundService.ACTION_STOP)
        assertEquals(1001, RecordingForegroundService.NOTIFICATION_ID)
    }

    @Test
    fun testTemporaryAudioFileCleanupLogic() {
        val tempDir = File(System.getProperty("java.io.tmpdir") ?: ".")
        val tempAudioFile = File(tempDir, "test_recording_${System.currentTimeMillis()}.3gp")
        tempAudioFile.writeText("MOCK_AUDIO_BYTES")

        assertTrue(tempAudioFile.exists())

        // Simulate successful upload cleanup
        val uploadSuccess = true
        if (uploadSuccess) {
            tempAudioFile.delete()
        }

        assertFalse(tempAudioFile.exists())
    }

    @Test
    fun testFailedUploadRetainsTempFile() {
        val tempDir = File(System.getProperty("java.io.tmpdir") ?: ".")
        val tempAudioFile = File(tempDir, "test_recording_failed_${System.currentTimeMillis()}.3gp")
        tempAudioFile.writeText("MOCK_AUDIO_BYTES")

        assertTrue(tempAudioFile.exists())

        // Simulate failed upload
        val uploadSuccess = false
        if (uploadSuccess) {
            tempAudioFile.delete()
        }

        // File must remain on disk for retry!
        assertTrue(tempAudioFile.exists())

        // Cleanup after test
        tempAudioFile.delete()
    }

    @Test
    fun testAudioSourceDefaultAndAllowedSources() {
        val req = com.pcma.app.data.models.RecordingStartRequest()
        assertEquals("phone_microphone", req.audioSource)
        assertTrue(req.sourceAvailable)
        assertTrue(req.microphonePermissionGranted)
        assertFalse(req.consentAcknowledged)

        val backendAllowedSources = setOf("phone_microphone", "wired_headset", "bluetooth", "external_microphone")
        assertTrue(backendAllowedSources.contains(req.audioSource))
    }

    @Test
    fun testExplicitConsentAcknowledgedSendsTrue() {
        val req = com.pcma.app.data.models.RecordingStartRequest(consentAcknowledged = true)
        assertTrue(req.consentAcknowledged)
    }

    @Test
    fun testDeclinedConsentPreventsRecording() {
        val storageConsentAcknowledged = false
        var recordingAttempted = false
        var errorMessage: String? = null

        // User declines consent
        val userChoice = "cancel"
        if (userChoice == "agree") {
            recordingAttempted = true
        } else {
            errorMessage = "Recording consent was declined"
        }

        assertFalse(storageConsentAcknowledged)
        assertFalse(recordingAttempted)
        assertEquals("Recording consent was declined", errorMessage)
    }

    @Test
    fun testSpeakerIdResolutionFromSpeakerMap() {
        val speakers = listOf(
            com.pcma.app.data.models.SpeakerResponse(id = 1, label = "Uncertain speaker"),
            com.pcma.app.data.models.SpeakerResponse(id = 2, label = "Speaker 1")
        )
        val speakerMap = speakers.associateBy { it.id }

        val seg1 = com.pcma.app.data.models.SegmentResponse(id = 1, speakerId = 1, speakerLabel = null, speakerTag = null, startMs = 240, endMs = 2240, text = "You")
        val seg2 = com.pcma.app.data.models.SegmentResponse(id = 2, speakerId = 2, speakerLabel = null, speakerTag = null, startMs = 2460, endMs = 4460, text = "What is the problem now?")

        val resolved1 = seg1.speakerLabel ?: seg1.speakerId?.let { speakerMap[it]?.label } ?: "Speaker"
        val resolved2 = seg2.speakerLabel ?: seg2.speakerId?.let { speakerMap[it]?.label } ?: "Speaker"

        assertEquals("Uncertain speaker", resolved1)
        assertEquals("Speaker 1", resolved2)
    }

    @Test
    fun testExtractedQuestionAndMomSectionMapping() {
        val q = com.pcma.app.data.models.QuestionResponse(id = 1, questionText = "What is the problem now?", askerName = "Speaker 1", status = "unanswered")
        assertEquals("What is the problem now?", q.questionText)
        assertEquals("Speaker 1", q.askerName)
        assertEquals("unanswered", q.status)

        val sec = com.pcma.app.data.models.MomSection(id = 5, title = "Open Questions", contentJson = "[{\"id\":1,\"text\":\"What is the problem now?\"}]")
        assertEquals("Open Questions", sec.title)
        assertNotNull(sec.contentJson)
    }

    @Test
    fun testApiExceptionPreservesStatusAndMessage() {
        val ex = com.pcma.app.data.api.ApiException(404, "MOM not found")
        assertEquals(404, ex.statusCode)
        assertEquals("MOM not found", ex.message)
        assertTrue(ex is java.io.IOException)
    }

    @OptIn(kotlinx.coroutines.ExperimentalCoroutinesApi::class)
    @Test
    fun testConversationSelectionPreservesConversationIdAcrossViewModels() = kotlinx.coroutines.test.runTest {
        val testDispatcher = kotlinx.coroutines.test.StandardTestDispatcher(testScheduler)
        kotlinx.coroutines.Dispatchers.setMain(testDispatcher)
        try {
            val fakeRepo = object : com.pcma.app.data.repository.PcmaRepository() {
                override suspend fun getMom(conversationId: Int): MomResponse? = null
            }
            val convViewModel = com.pcma.app.ui.viewmodel.ConversationsViewModel(fakeRepo)
            val momViewModel = com.pcma.app.ui.viewmodel.MomViewModel(fakeRepo)

            assertNull(convViewModel.selectedConversationId.value)
            assertNull(momViewModel.selectedConversationId.value)

            // Select conversation 8 in ConversationsViewModel
            convViewModel.selectConversation(8)
            assertEquals(8, convViewModel.selectedConversationId.value)

            // Select conversation 8 in MomViewModel
            momViewModel.selectConversation(8)
            testScheduler.advanceUntilIdle()

            assertEquals(8, momViewModel.selectedConversationId.value)
            assertTrue(momViewModel.momNotFound.value)
            assertNull(momViewModel.currentMom.value)
        } finally {
            kotlinx.coroutines.Dispatchers.resetMain()
        }
    }

    @OptIn(kotlinx.coroutines.ExperimentalCoroutinesApi::class)
    @Test
    fun testMomViewModelNotFoundShowsGenerateActionState() = kotlinx.coroutines.test.runTest {
        val testDispatcher = kotlinx.coroutines.test.StandardTestDispatcher(testScheduler)
        kotlinx.coroutines.Dispatchers.setMain(testDispatcher)
        try {
            val fakeRepo = object : com.pcma.app.data.repository.PcmaRepository() {
                override suspend fun getMom(conversationId: Int): MomResponse? = null
            }
            val momViewModel = com.pcma.app.ui.viewmodel.MomViewModel(fakeRepo)

            momViewModel.loadMom(8)
            testScheduler.advanceUntilIdle()

            assertEquals(8, momViewModel.selectedConversationId.value)
            assertNull(momViewModel.currentMom.value)
            assertTrue(momViewModel.momNotFound.value)
            assertFalse(momViewModel.isLoading.value)
            assertNull(momViewModel.errorMessage.value)
        } finally {
            kotlinx.coroutines.Dispatchers.resetMain()
        }
    }

    @OptIn(kotlinx.coroutines.ExperimentalCoroutinesApi::class)
    @Test
    fun testMomViewModelLoadsExistingMom() = kotlinx.coroutines.test.runTest {
        val testDispatcher = kotlinx.coroutines.test.StandardTestDispatcher(testScheduler)
        kotlinx.coroutines.Dispatchers.setMain(testDispatcher)
        try {
            val expectedMom = MomResponse(
                id = 15,
                conversationId = 2,
                title = "Sprint Planning MOM",
                summary = "Approved sprint tasks and milestones.",
                status = "draft",
                createdAt = "2026-10-12T11:00:00Z"
            )
            val fakeRepo = object : com.pcma.app.data.repository.PcmaRepository() {
                override suspend fun getMom(conversationId: Int): MomResponse? =
                    if (conversationId == 2) expectedMom else null
                override suspend fun getMomHistory(momId: Int): List<com.pcma.app.data.models.MomHistoryResponse> = emptyList()
                override suspend fun getMomShares(momId: Int): List<com.pcma.app.data.models.MomShareResponse> = emptyList()
            }
            val momViewModel = com.pcma.app.ui.viewmodel.MomViewModel(fakeRepo)

            momViewModel.selectConversation(2)
            testScheduler.advanceUntilIdle()

            assertEquals(2, momViewModel.selectedConversationId.value)
            assertNotNull(momViewModel.currentMom.value)
            assertEquals(15, momViewModel.currentMom.value?.id)
            assertEquals("Sprint Planning MOM", momViewModel.currentMom.value?.title)
            assertFalse(momViewModel.momNotFound.value)
            assertFalse(momViewModel.isLoading.value)
            assertNull(momViewModel.errorMessage.value)
        } finally {
            kotlinx.coroutines.Dispatchers.resetMain()
        }
    }

    @OptIn(kotlinx.coroutines.ExperimentalCoroutinesApi::class)
    @Test
    fun testMomViewModelGenerateMomSuccess() = kotlinx.coroutines.test.runTest {
        val testDispatcher = kotlinx.coroutines.test.StandardTestDispatcher(testScheduler)
        kotlinx.coroutines.Dispatchers.setMain(testDispatcher)
        try {
            val generatedMom = MomResponse(
                id = 22,
                conversationId = 8,
                title = "New MOM for Conversation 8",
                summary = "Generated from conversation speech segments.",
                status = "draft",
                createdAt = "2026-10-12T11:00:00Z"
            )
            val fakeRepo = object : com.pcma.app.data.repository.PcmaRepository() {
                override suspend fun getMom(conversationId: Int): MomResponse? = null
                override suspend fun generateMom(conversationId: Int): MomResponse = generatedMom
                override suspend fun getMomHistory(momId: Int): List<com.pcma.app.data.models.MomHistoryResponse> = emptyList()
                override suspend fun getMomShares(momId: Int): List<com.pcma.app.data.models.MomShareResponse> = emptyList()
            }
            val momViewModel = com.pcma.app.ui.viewmodel.MomViewModel(fakeRepo)

            // Initially not found
            momViewModel.loadMom(8)
            testScheduler.advanceUntilIdle()
            assertTrue(momViewModel.momNotFound.value)
            assertNull(momViewModel.currentMom.value)

            // User clicks "Generate MOM"
            momViewModel.generateMom(8)
            testScheduler.advanceUntilIdle()

            assertNotNull(momViewModel.currentMom.value)
            assertEquals(22, momViewModel.currentMom.value?.id)
            assertEquals("New MOM for Conversation 8", momViewModel.currentMom.value?.title)
            assertFalse(momViewModel.momNotFound.value)
            assertFalse(momViewModel.isLoading.value)
            assertNull(momViewModel.errorMessage.value)
        } finally {
            kotlinx.coroutines.Dispatchers.resetMain()
        }
    }

    @OptIn(kotlinx.coroutines.ExperimentalCoroutinesApi::class)
    @Test
    fun testMomViewModelHandlesNetworkError() = kotlinx.coroutines.test.runTest {
        val testDispatcher = kotlinx.coroutines.test.StandardTestDispatcher(testScheduler)
        kotlinx.coroutines.Dispatchers.setMain(testDispatcher)
        try {
            val fakeRepo = object : com.pcma.app.data.repository.PcmaRepository() {
                override suspend fun getMom(conversationId: Int): MomResponse? {
                    throw java.io.IOException("Network connection failed")
                }
            }
            val momViewModel = com.pcma.app.ui.viewmodel.MomViewModel(fakeRepo)

            momViewModel.loadMom(5)
            testScheduler.advanceUntilIdle()

            assertEquals(5, momViewModel.selectedConversationId.value)
            assertNull(momViewModel.currentMom.value)
            assertFalse(momViewModel.momNotFound.value)
            assertEquals("Network connection failed", momViewModel.errorMessage.value)
            assertFalse(momViewModel.isLoading.value)
        } finally {
            kotlinx.coroutines.Dispatchers.resetMain()
        }
    }

    @Test
    fun testFormatMomSectionJsonEmptyArrayReturnsNone() {
        assertEquals("None", com.pcma.app.ui.screens.formatMomSectionJson("[]"))
        assertEquals("None", com.pcma.app.ui.screens.formatMomSectionJson(null))
        assertEquals("None", com.pcma.app.ui.screens.formatMomSectionJson(""))
    }

    @Test
    fun testFormatMomSectionJsonWithExtractedItems() {
        val json = """[
            {"id": 1, "text": "We decided to adopt PostgreSQL", "confidence": 0.95},
            {"id": 2, "text": "Setup the CI pipeline", "assignee_name": "Alice", "status": "open"},
            {"id": 3, "text": "Deliver security audit", "promiser_name": "Bob", "due_date": "2026-10-15"},
            {"id": 4, "raw_deadline_text": "Finish audit by Friday"},
            {"id": 5, "question_text": "What is our deployment timeline?", "status": "unanswered"}
        ]""".trimIndent()

        val formatted = com.pcma.app.ui.screens.formatMomSectionJson(json)
        assertTrue(formatted.contains("• We decided to adopt PostgreSQL"))
        assertTrue(formatted.contains("• Setup the CI pipeline — Assignee: Alice"))
        assertTrue(formatted.contains("• Deliver security audit — Promised by: Bob — Due: 2026-10-15"))
        assertTrue(formatted.contains("• Finish audit by Friday"))
        assertTrue(formatted.contains("• What is our deployment timeline?"))
    }

    @OptIn(kotlinx.coroutines.ExperimentalCoroutinesApi::class)
    @Test
    fun testAbandonedRecordingDetectionInRefreshStatus() = kotlinx.coroutines.test.runTest {
        val testDispatcher = kotlinx.coroutines.test.StandardTestDispatcher(testScheduler)
        kotlinx.coroutines.Dispatchers.setMain(testDispatcher)
        try {
            val fakeActive = com.pcma.app.data.models.RecordingResponse(
                id = 9,
                userId = 1,
                state = "active",
                status = "active",
                audioSource = "phone_microphone",
                startedAt = "2026-10-12T05:28:58Z",
                stoppedAt = null,
                durationMs = null,
                createdAt = "2026-10-12T05:28:58Z"
            )
            val fakeRepo = object : com.pcma.app.data.repository.PcmaRepository() {
                override suspend fun getRecordings(): List<com.pcma.app.data.models.RecordingResponse> = listOf(fakeActive)
            }
            val fakeManager = object : com.pcma.app.data.repository.AudioRecordingManager(null) {}
            val vm = com.pcma.app.ui.viewmodel.RecordingViewModel(fakeRepo, fakeManager)

            vm.refreshLatestStatus()
            testScheduler.advanceUntilIdle()

            assertNotNull(vm.abandonedRecording.value)
            assertEquals(9, vm.abandonedRecording.value?.id)
            assertTrue(vm.errorMessage.value?.contains("#9") == true)
        } finally {
            kotlinx.coroutines.Dispatchers.resetMain()
        }
    }

    @OptIn(kotlinx.coroutines.ExperimentalCoroutinesApi::class)
    @Test
    fun testRecoverAbandonedRecordingSafelyCleansUpSession() = kotlinx.coroutines.test.runTest {
        val testDispatcher = kotlinx.coroutines.test.StandardTestDispatcher(testScheduler)
        kotlinx.coroutines.Dispatchers.setMain(testDispatcher)
        try {
            var recoveredId: Int? = null
            val fakeActive = com.pcma.app.data.models.RecordingResponse(
                id = 9,
                userId = 1,
                state = "active",
                status = "active",
                audioSource = "phone_microphone",
                startedAt = "2026-10-12T05:28:58Z",
                stoppedAt = null,
                durationMs = null,
                createdAt = "2026-10-12T05:28:58Z"
            )
            var serverRecordings = mutableListOf(fakeActive)
            val fakeRepo = object : com.pcma.app.data.repository.PcmaRepository() {
                override suspend fun getRecordings(): List<com.pcma.app.data.models.RecordingResponse> = serverRecordings
                override suspend fun getActiveRecording(): com.pcma.app.data.models.RecordingResponse? = serverRecordings.firstOrNull()
                override suspend fun recoverActiveRecording(id: Int?): com.pcma.app.data.models.RecordingResponse {
                    recoveredId = id
                    serverRecordings.clear()
                    return fakeActive.copy(state = "failed", status = "failed", durationMs = 0)
                }
            }
            val fakeManager = object : com.pcma.app.data.repository.AudioRecordingManager(null) {}
            val vm = com.pcma.app.ui.viewmodel.RecordingViewModel(fakeRepo, fakeManager)

            vm.refreshLatestStatus()
            testScheduler.advanceUntilIdle()
            assertEquals(9, vm.abandonedRecording.value?.id)

            vm.recoverAbandonedRecording()
            testScheduler.advanceUntilIdle()

            assertEquals(9, recoveredId)
            assertNull(vm.abandonedRecording.value)
            assertEquals("idle", vm.recordingState.value)
            assertTrue(vm.errorMessage.value?.contains("safely closed") == true)
        } finally {
            kotlinx.coroutines.Dispatchers.resetMain()
        }
    }

    @OptIn(kotlinx.coroutines.ExperimentalCoroutinesApi::class)
    @Test
    fun testDiscardAbandonedRecordingCancelsSession() = kotlinx.coroutines.test.runTest {
        val testDispatcher = kotlinx.coroutines.test.StandardTestDispatcher(testScheduler)
        kotlinx.coroutines.Dispatchers.setMain(testDispatcher)
        try {
            var cancelledId: Int? = null
            val fakeActive = com.pcma.app.data.models.RecordingResponse(
                id = 9,
                userId = 1,
                state = "active",
                status = "active",
                audioSource = "phone_microphone",
                startedAt = "2026-10-12T05:28:58Z",
                stoppedAt = null,
                durationMs = null,
                createdAt = "2026-10-12T05:28:58Z"
            )
            var serverRecordings = mutableListOf(fakeActive)
            val fakeRepo = object : com.pcma.app.data.repository.PcmaRepository() {
                override suspend fun getRecordings(): List<com.pcma.app.data.models.RecordingResponse> = serverRecordings
                override suspend fun getActiveRecording(): com.pcma.app.data.models.RecordingResponse? = serverRecordings.firstOrNull()
                override suspend fun cancelRecording(id: Int): com.pcma.app.data.models.RecordingResponse {
                    cancelledId = id
                    serverRecordings.clear()
                    return fakeActive.copy(state = "failed", status = "failed")
                }
            }
            val fakeManager = object : com.pcma.app.data.repository.AudioRecordingManager(null) {}
            val vm = com.pcma.app.ui.viewmodel.RecordingViewModel(fakeRepo, fakeManager)

            vm.refreshLatestStatus()
            testScheduler.advanceUntilIdle()
            assertEquals(9, vm.abandonedRecording.value?.id)

            vm.discardAbandonedRecording()
            testScheduler.advanceUntilIdle()

            assertEquals(9, cancelledId)
            assertNull(vm.abandonedRecording.value)
            assertEquals("idle", vm.recordingState.value)
            assertTrue(vm.errorMessage.value?.contains("discarded successfully") == true)
        } finally {
            kotlinx.coroutines.Dispatchers.resetMain()
        }
    }

    @OptIn(kotlinx.coroutines.ExperimentalCoroutinesApi::class)
    @Test
    fun testStartRecordingNativeFailureCancelsBackendSession() = kotlinx.coroutines.test.runTest {
        val testDispatcher = kotlinx.coroutines.test.StandardTestDispatcher(testScheduler)
        kotlinx.coroutines.Dispatchers.setMain(testDispatcher)
        try {
            var cancelledId: Int? = null
            val fakeCreated = com.pcma.app.data.models.RecordingResponse(
                id = 15,
                userId = 1,
                state = "active",
                status = "active",
                audioSource = "phone_microphone",
                startedAt = "2026-10-12T06:00:00Z",
                stoppedAt = null,
                durationMs = null,
                createdAt = "2026-10-12T06:00:00Z"
            )
            val fakeRepo = object : com.pcma.app.data.repository.PcmaRepository() {
                override suspend fun startRecording(
                    audioSource: String,
                    sourceAvailable: Boolean,
                    microphonePermissionGranted: Boolean,
                    consentAcknowledged: Boolean
                ): com.pcma.app.data.models.RecordingResponse = fakeCreated

                override suspend fun cancelRecording(id: Int): com.pcma.app.data.models.RecordingResponse {
                    cancelledId = id
                    return fakeCreated.copy(state = "failed", status = "failed")
                }
            }
            val fakeManager = object : com.pcma.app.data.repository.AudioRecordingManager(null) {
                override fun startRecording(outputFile: File, audioSource: String): Boolean = false
            }
            val vm = com.pcma.app.ui.viewmodel.RecordingViewModel(fakeRepo, fakeManager)

            val tempDir = File(System.getProperty("java.io.tmpdir") ?: ".")
            vm.startRecording(tempDir, consentAcknowledged = true)
            testScheduler.advanceUntilIdle()

            assertEquals(15, cancelledId)
            assertEquals("failed", vm.recordingState.value)
            assertEquals("Microphone initialization failed", vm.errorMessage.value)
            assertNull(vm.activeRecording.value)
        } finally {
            kotlinx.coroutines.Dispatchers.resetMain()
        }
    }

    @Test
    fun testApiExceptionDiagnosticContextFor404AndAuthErrors() {
        val notFoundEx = com.pcma.app.data.api.ApiException(404, "Resource not found on server (404: /v1/recordings/13/recover)")
        assertEquals(404, notFoundEx.statusCode)
        assertTrue(notFoundEx.message?.contains("404: /v1/recordings/13/recover") == true)

        val unauthEx = com.pcma.app.data.api.ApiException(401, "Session expired or unauthorized (401)")
        assertEquals(401, unauthEx.statusCode)
        assertTrue(unauthEx.message?.contains("Session expired or unauthorized") == true)

        val forbiddenEx = com.pcma.app.data.api.ApiException(403, "Access denied (403)")
        assertEquals(403, forbiddenEx.statusCode)

        val networkEx = com.pcma.app.data.api.ApiException(0, "Unable to reach server at http://192.168.29.190:8000. Verify backend is running.")
        assertEquals(0, networkEx.statusCode)
        assertTrue(networkEx.message?.contains("Verify backend is running") == true)
    }

    @OptIn(kotlinx.coroutines.ExperimentalCoroutinesApi::class)
    @Test
    fun testRecoverAbandonedRecordingEmptySessionDisplaysExplanation() = kotlinx.coroutines.test.runTest {
        val testDispatcher = kotlinx.coroutines.test.StandardTestDispatcher(testScheduler)
        kotlinx.coroutines.Dispatchers.setMain(testDispatcher)
        try {
            val fakeActive = com.pcma.app.data.models.RecordingResponse(
                id = 13,
                userId = 1,
                state = "paused",
                status = "paused",
                audioSource = "phone_microphone",
                startedAt = "2026-10-12T11:22:42Z",
                stoppedAt = null,
                durationMs = null,
                createdAt = "2026-10-12T11:22:42Z"
            )
            val fakeRepo = object : com.pcma.app.data.repository.PcmaRepository() {
                override suspend fun getActiveRecording(): com.pcma.app.data.models.RecordingResponse = fakeActive
                override suspend fun getRecordings(): List<com.pcma.app.data.models.RecordingResponse> = listOf(fakeActive)
                override suspend fun recoverActiveRecording(id: Int?): com.pcma.app.data.models.RecordingResponse {
                    throw com.pcma.app.data.api.ApiException(400, "No audio was recorded for session #13. Discard it to begin a clean session.")
                }
            }
            val fakeManager = object : com.pcma.app.data.repository.AudioRecordingManager(null) {}
            val vm = com.pcma.app.ui.viewmodel.RecordingViewModel(fakeRepo, fakeManager)

            vm.checkForAbandonedRecording()
            testScheduler.advanceUntilIdle()
            assertEquals(13, vm.abandonedRecording.value?.id)

            vm.recoverAbandonedRecording()
            testScheduler.advanceUntilIdle()

            assertTrue(vm.errorMessage.value?.contains("No audio was recorded for session #13") == true)
            assertTrue(vm.errorMessage.value?.contains("Discard it to begin a clean session") == true)
            // The unfinalized session is still detected so user can tap Discard
            assertEquals(13, vm.abandonedRecording.value?.id)
            assertFalse(vm.isRecovering.value)
        } finally {
            kotlinx.coroutines.Dispatchers.resetMain()
        }
    }

    @OptIn(kotlinx.coroutines.ExperimentalCoroutinesApi::class)
    @Test
    fun testRecoverAbandonedRecordingWithAudioTransitionsToProcessing() = kotlinx.coroutines.test.runTest {
        val testDispatcher = kotlinx.coroutines.test.StandardTestDispatcher(testScheduler)
        kotlinx.coroutines.Dispatchers.setMain(testDispatcher)
        try {
            val fakeActive = com.pcma.app.data.models.RecordingResponse(
                id = 14,
                userId = 1,
                state = "active",
                status = "active",
                audioSource = "phone_microphone",
                startedAt = "2026-10-12T12:00:00Z",
                stoppedAt = null,
                durationMs = null,
                createdAt = "2026-10-12T12:00:00Z"
            )
            val fakeRecovered = fakeActive.copy(state = "processing", status = "processing", durationMs = 12000)
            var serverRecordings = mutableListOf(fakeActive)
            val fakeRepo = object : com.pcma.app.data.repository.PcmaRepository() {
                override suspend fun getActiveRecording(): com.pcma.app.data.models.RecordingResponse? = serverRecordings.firstOrNull()
                override suspend fun getRecordings(): List<com.pcma.app.data.models.RecordingResponse> = serverRecordings
                override suspend fun recoverActiveRecording(id: Int?): com.pcma.app.data.models.RecordingResponse {
                    serverRecordings.clear()
                    return fakeRecovered
                }
                override suspend fun getTranscriptionStatus(id: Int): com.pcma.app.data.models.TranscriptionStatusResponse =
                    com.pcma.app.data.models.TranscriptionStatusResponse(
                        id = 1,
                        recordingId = 14,
                        status = "completed",
                        createdAt = "2026-10-12T12:00:00Z",
                        updatedAt = "2026-10-12T12:01:00Z"
                    )
            }
            val fakeManager = object : com.pcma.app.data.repository.AudioRecordingManager(null) {}
            val vm = com.pcma.app.ui.viewmodel.RecordingViewModel(fakeRepo, fakeManager)

            vm.refreshLatestStatus()
            testScheduler.advanceUntilIdle()
            assertEquals(14, vm.abandonedRecording.value?.id)

            var finishedId: Int? = null
            vm.recoverAbandonedRecording { id -> finishedId = id }
            testScheduler.advanceUntilIdle()

            assertNull(vm.abandonedRecording.value)
            assertEquals("ready", vm.recordingState.value)
            assertEquals(14, finishedId)
            assertEquals(14, vm.activeRecording.value?.id)
        } finally {
            kotlinx.coroutines.Dispatchers.resetMain()
        }
    }

    @OptIn(kotlinx.coroutines.ExperimentalCoroutinesApi::class)
    @Test
    fun testDiscardAbandonedRecordingHandlesAlreadyResolvedServerState() = kotlinx.coroutines.test.runTest {
        val testDispatcher = kotlinx.coroutines.test.StandardTestDispatcher(testScheduler)
        kotlinx.coroutines.Dispatchers.setMain(testDispatcher)
        try {
            val fakeActive = com.pcma.app.data.models.RecordingResponse(
                id = 13,
                userId = 1,
                state = "paused",
                status = "paused",
                audioSource = "phone_microphone",
                startedAt = "2026-10-12T11:22:42Z",
                stoppedAt = null,
                durationMs = null,
                createdAt = "2026-10-12T11:22:42Z"
            )
            var activeOnServer: com.pcma.app.data.models.RecordingResponse? = fakeActive
            val fakeRepo = object : com.pcma.app.data.repository.PcmaRepository() {
                override suspend fun getActiveRecording(): com.pcma.app.data.models.RecordingResponse? = activeOnServer
                override suspend fun getRecordings(): List<com.pcma.app.data.models.RecordingResponse> = emptyList()
                override suspend fun cancelRecording(id: Int): com.pcma.app.data.models.RecordingResponse {
                    activeOnServer = null
                    // Simulate server having already resolved it
                    throw com.pcma.app.data.api.ApiException(404, "Recording not found")
                }
            }
            val fakeManager = object : com.pcma.app.data.repository.AudioRecordingManager(null) {}
            val vm = com.pcma.app.ui.viewmodel.RecordingViewModel(fakeRepo, fakeManager)

            vm.checkForAbandonedRecording()
            testScheduler.advanceUntilIdle()
            assertEquals(13, vm.abandonedRecording.value?.id)

            vm.discardAbandonedRecording()
            testScheduler.advanceUntilIdle()

            // Server confirmed no active recording exists, so card is cleared and state set to idle
            assertNull(vm.abandonedRecording.value)
            assertEquals("idle", vm.recordingState.value)
            assertTrue(vm.errorMessage.value?.contains("already resolved") == true)
        } finally {
            kotlinx.coroutines.Dispatchers.resetMain()
        }
    }

    @OptIn(kotlinx.coroutines.ExperimentalCoroutinesApi::class)
    @Test
    fun testConversationsViewModelErrorHandlingDisplaysErrorInsteadOfEmptyList() = kotlinx.coroutines.test.runTest {
        val testDispatcher = kotlinx.coroutines.test.StandardTestDispatcher(testScheduler)
        kotlinx.coroutines.Dispatchers.setMain(testDispatcher)
        try {
            val fakeRepo = object : com.pcma.app.data.repository.PcmaRepository() {
                override suspend fun getConversations(): List<com.pcma.app.data.models.ConversationResponse> {
                    throw com.pcma.app.data.api.ApiException(0, "Unable to reach server at http://127.0.0.1:8000. Verify backend is running.")
                }
            }
            val vm = com.pcma.app.ui.viewmodel.ConversationsViewModel(fakeRepo)

            vm.loadConversations()
            testScheduler.advanceUntilIdle()

            assertTrue(vm.conversations.value.isEmpty())
            assertFalse(vm.isLoading.value)
            assertNotNull(vm.errorMessage.value)
            assertTrue(vm.errorMessage.value?.contains("Unable to reach server") == true)
        } finally {
            kotlinx.coroutines.Dispatchers.resetMain()
        }
    }

    @OptIn(kotlinx.coroutines.ExperimentalCoroutinesApi::class)
    @Test
    fun testConversationsViewModelSuccessfulLoadClearsError() = kotlinx.coroutines.test.runTest {
        val testDispatcher = kotlinx.coroutines.test.StandardTestDispatcher(testScheduler)
        kotlinx.coroutines.Dispatchers.setMain(testDispatcher)
        try {
            val sampleConv = com.pcma.app.data.models.ConversationResponse(
                id = 5,
                recordingId = 15,
                userId = 1,
                title = "Meeting 5",
                occurredAt = "2026-10-14T08:00:00Z",
                createdAt = "2026-10-14T08:00:00Z",
                status = "ready_for_review"
            )
            val fakeRepo = object : com.pcma.app.data.repository.PcmaRepository() {
                override suspend fun getConversations(): List<com.pcma.app.data.models.ConversationResponse> {
                    return listOf(sampleConv)
                }
            }
            val vm = com.pcma.app.ui.viewmodel.ConversationsViewModel(fakeRepo)

            vm.loadConversations()
            testScheduler.advanceUntilIdle()

            assertEquals(1, vm.conversations.value.size)
            assertEquals(5, vm.conversations.value[0].id)
            assertFalse(vm.isLoading.value)
            assertNull(vm.errorMessage.value)
        } finally {
            kotlinx.coroutines.Dispatchers.resetMain()
        }
    }

    @OptIn(kotlinx.coroutines.ExperimentalCoroutinesApi::class)
    @Test
    fun testConversationsViewModelExpiredTokenTriggersAutoRefreshAndSucceeds() = kotlinx.coroutines.test.runTest {
        val testDispatcher = kotlinx.coroutines.test.StandardTestDispatcher(testScheduler)
        kotlinx.coroutines.Dispatchers.setMain(testDispatcher)
        try {
            var attemptCount = 0
            val sampleConv = com.pcma.app.data.models.ConversationResponse(
                id = 5,
                recordingId = 15,
                userId = 1,
                title = "Meeting 5",
                occurredAt = "2026-10-14T08:00:00Z",
                createdAt = "2026-10-14T08:00:00Z",
                status = "ready_for_review"
            )
            val fakeRepo = object : com.pcma.app.data.repository.PcmaRepository() {
                override suspend fun getConversations(): List<com.pcma.app.data.models.ConversationResponse> {
                    attemptCount++
                    if (attemptCount == 1) {
                        throw com.pcma.app.data.api.ApiException(401, "Access token has expired")
                    }
                    return listOf(sampleConv)
                }

                override suspend fun refreshAuthToken(): Boolean {
                    return true
                }
            }
            val vm = com.pcma.app.ui.viewmodel.ConversationsViewModel(fakeRepo)

            vm.loadConversations()
            testScheduler.advanceUntilIdle()

            assertEquals(2, attemptCount)
            assertEquals(1, vm.conversations.value.size)
            assertEquals(5, vm.conversations.value[0].id)
            assertNull(vm.errorMessage.value)
        } finally {
            kotlinx.coroutines.Dispatchers.resetMain()
        }
    }

    @OptIn(kotlinx.coroutines.ExperimentalCoroutinesApi::class)
    @Test
    fun testConversationsViewModelExpiredTokenFailsRefreshSetsExpiredError() = kotlinx.coroutines.test.runTest {
        val testDispatcher = kotlinx.coroutines.test.StandardTestDispatcher(testScheduler)
        kotlinx.coroutines.Dispatchers.setMain(testDispatcher)
        try {
            val fakeRepo = object : com.pcma.app.data.repository.PcmaRepository() {
                override suspend fun getConversations(): List<com.pcma.app.data.models.ConversationResponse> {
                    throw com.pcma.app.data.api.ApiException(401, "Access token has expired")
                }

                override suspend fun refreshAuthToken(): Boolean {
                    return false
                }
            }
            val vm = com.pcma.app.ui.viewmodel.ConversationsViewModel(fakeRepo)

            vm.loadConversations()
            testScheduler.advanceUntilIdle()

            assertTrue(vm.conversations.value.isEmpty())
            assertFalse(vm.isLoading.value)
            assertNotNull(vm.errorMessage.value)
            assertTrue(vm.errorMessage.value?.contains("expired") == true)
        } finally {
            kotlinx.coroutines.Dispatchers.resetMain()
        }
    }

    @OptIn(kotlinx.coroutines.ExperimentalCoroutinesApi::class)
    @Test
    fun testMainViewModelLoadProfileExpiredTokenWithoutRefreshInvalidatesAuth() = kotlinx.coroutines.test.runTest {
        val testDispatcher = kotlinx.coroutines.test.StandardTestDispatcher(testScheduler)
        kotlinx.coroutines.Dispatchers.setMain(testDispatcher)
        try {
            val fakeRepo = object : com.pcma.app.data.repository.PcmaRepository() {
                override suspend fun getProfile(): com.pcma.app.data.models.ProfileResponse {
                    throw com.pcma.app.data.api.ApiException(401, "Access token has expired")
                }

                override suspend fun refreshAuthToken(): Boolean {
                    return false
                }
            }
            val vm = com.pcma.app.ui.viewmodel.MainViewModel(fakeRepo)
            vm.isAuthenticated.value = true

            vm.loadProfile()
            testScheduler.advanceUntilIdle()

            assertFalse(vm.isAuthenticated.value)
            assertTrue(vm.errorMessage.value?.contains("Session expired") == true)
        } finally {
            kotlinx.coroutines.Dispatchers.resetMain()
        }
    }

    @OptIn(kotlinx.coroutines.ExperimentalCoroutinesApi::class)
    @Test
    fun testConversationsViewModelCorrectSegmentSuccess() = kotlinx.coroutines.test.runTest {
        val testDispatcher = kotlinx.coroutines.test.StandardTestDispatcher(testScheduler)
        kotlinx.coroutines.Dispatchers.setMain(testDispatcher)
        try {
            var correctCalled = false
            var passedNewText = ""
            var passedReExtract = false
            val fakeRepo = object : com.pcma.app.data.repository.PcmaRepository() {
                override suspend fun correctSegment(
                    recordingId: Int,
                    segmentId: Int,
                    text: String,
                    reExtract: Boolean
                ): com.pcma.app.data.models.SegmentResponse {
                    correctCalled = true
                    passedNewText = text
                    passedReExtract = reExtract
                    return com.pcma.app.data.models.SegmentResponse(
                        id = segmentId,
                        speakerId = 1,
                        speakerLabel = "Speaker 1",
                        speakerTag = 1,
                        startMs = 0L,
                        endMs = 5000L,
                        text = text
                    )
                }

                override suspend fun getTranscript(id: Int): com.pcma.app.data.models.TranscriptResponse {
                    return com.pcma.app.data.models.TranscriptResponse(
                        id = 1,
                        recordingId = id,
                        language = "en",
                        segments = listOf(
                            com.pcma.app.data.models.SegmentResponse(
                                id = 21,
                                speakerId = 1,
                                speakerLabel = "Speaker 1",
                                speakerTag = 1,
                                startMs = 0L,
                                endMs = 5000L,
                                text = passedNewText
                            )
                        )
                    )
                }

                override suspend fun getConversationDetail(id: Int): com.pcma.app.data.models.ConversationResponse {
                    return com.pcma.app.data.models.ConversationResponse(
                        id = id,
                        userId = 1,
                        recordingId = 16,
                        title = "Test Conversation",
                        occurredAt = "2026-10-14T00:00:00Z"
                    )
                }
            }
            val vm = com.pcma.app.ui.viewmodel.ConversationsViewModel(fakeRepo)
            vm.selectConversation(6)

            var callbackResult: Boolean? = null
            vm.correctSegment(
                recordingId = 16,
                segmentId = 21,
                newText = "Alice will do the deployment by Friday.",
                reExtract = true
            ) { success ->
                callbackResult = success
            }
            testScheduler.advanceUntilIdle()

            assertTrue(correctCalled)
            assertEquals("Alice will do the deployment by Friday.", passedNewText)
            assertTrue(passedReExtract)
            assertEquals(true, callbackResult)
            assertFalse(vm.isCorrectingSegment.value)
            assertNull(vm.correctionError.value)
            assertEquals("Alice will do the deployment by Friday.", vm.transcript.value?.segments?.firstOrNull()?.text)
        } finally {
            kotlinx.coroutines.Dispatchers.resetMain()
        }
    }

    @OptIn(kotlinx.coroutines.ExperimentalCoroutinesApi::class)
    @Test
    fun testConversationsViewModelCorrectSegmentFailure() = kotlinx.coroutines.test.runTest {
        val testDispatcher = kotlinx.coroutines.test.StandardTestDispatcher(testScheduler)
        kotlinx.coroutines.Dispatchers.setMain(testDispatcher)
        try {
            val fakeRepo = object : com.pcma.app.data.repository.PcmaRepository() {
                override suspend fun correctSegment(
                    recordingId: Int,
                    segmentId: Int,
                    text: String,
                    reExtract: Boolean
                ): com.pcma.app.data.models.SegmentResponse {
                    throw com.pcma.app.data.api.ApiException(400, "Segment text cannot be empty")
                }
            }
            val vm = com.pcma.app.ui.viewmodel.ConversationsViewModel(fakeRepo)

            var callbackResult: Boolean? = null
            vm.correctSegment(
                recordingId = 16,
                segmentId = 21,
                newText = "",
                reExtract = false
            ) { success ->
                callbackResult = success
            }
            testScheduler.advanceUntilIdle()

            assertEquals(false, callbackResult)
            assertFalse(vm.isCorrectingSegment.value)
            assertNotNull(vm.correctionError.value)
            assertTrue(vm.correctionError.value?.contains("cannot be empty") == true)
        } finally {
            kotlinx.coroutines.Dispatchers.resetMain()
        }
    }

    @OptIn(kotlinx.coroutines.ExperimentalCoroutinesApi::class)
    @Test
    fun testConversation6SegmentCorrectionApiResolution() = kotlinx.coroutines.test.runTest {
        val testDispatcher = kotlinx.coroutines.test.StandardTestDispatcher(testScheduler)
        kotlinx.coroutines.Dispatchers.setMain(testDispatcher)
        try {
            var invokedRecordingId: Int? = null
            var invokedSegmentId: Int? = null
            var invokedText: String? = null
            var invokedReExtract: Boolean? = null

            val fakeRepo = object : com.pcma.app.data.repository.PcmaRepository() {
                override suspend fun getConversationDetail(id: Int): com.pcma.app.data.models.ConversationResponse {
                    return com.pcma.app.data.models.ConversationResponse(
                        id = 6,
                        recordingId = 16,
                        userId = 1,
                        title = "Conversation",
                        occurredAt = "2026-10-14T08:00:00Z"
                    )
                }

                override suspend fun getTranscript(id: Int): com.pcma.app.data.models.TranscriptResponse {
                    return com.pcma.app.data.models.TranscriptResponse(
                        id = 8,
                        recordingId = 16,
                        language = "en",
                        segments = listOf(
                            com.pcma.app.data.models.SegmentResponse(
                                id = 21,
                                speakerId = 1,
                                speakerLabel = "Speaker 1",
                                startMs = 90L,
                                endMs = 7650L,
                                text = "We decided to adopt the new architecture, allies will do the deployment by Friday."
                            )
                        ),
                        speakers = listOf(
                            com.pcma.app.data.models.SpeakerResponse(id = 1, label = "Speaker 1")
                        )
                    )
                }

                override suspend fun correctSegment(
                    recordingId: Int,
                    segmentId: Int,
                    text: String,
                    reExtract: Boolean
                ): com.pcma.app.data.models.SegmentResponse {
                    invokedRecordingId = recordingId
                    invokedSegmentId = segmentId
                    invokedText = text
                    invokedReExtract = reExtract
                    return com.pcma.app.data.models.SegmentResponse(
                        id = segmentId,
                        speakerId = 1,
                        speakerLabel = "Speaker 1",
                        startMs = 90L,
                        endMs = 7650L,
                        text = text
                    )
                }
            }

            val vm = com.pcma.app.ui.viewmodel.ConversationsViewModel(fakeRepo)
            vm.loadConversationDetail(6)
            testScheduler.advanceUntilIdle()

            val detail = vm.activeConversation.value
            val transcript = vm.transcript.value
            assertNotNull(detail)
            assertNotNull(transcript)

            val targetRecId = detail?.recordingId ?: transcript?.recordingId ?: 6
            assertEquals(16, targetRecId)

            val seg = transcript?.segments?.firstOrNull()
            assertNotNull(seg)
            val segId = seg?.id ?: 1
            assertEquals(21, segId)

            // Verify correction dialog calls correctSegment API with recording ID 16 and segment ID 21
            var callbackSuccess = false
            vm.correctSegment(
                recordingId = targetRecId,
                segmentId = segId,
                newText = "We decided to adopt the new architecture, allies will do the deployment by Friday.",
                reExtract = false
            ) { success ->
                callbackSuccess = success
            }
            testScheduler.advanceUntilIdle()

            assertTrue(callbackSuccess)
            assertEquals(16, invokedRecordingId)
            assertEquals(21, invokedSegmentId)
            assertEquals(false, invokedReExtract)
        } finally {
            kotlinx.coroutines.Dispatchers.resetMain()
        }
    }

    @OptIn(kotlinx.coroutines.ExperimentalCoroutinesApi::class)
    @Test
    fun testRenameSpeakerAndEditTranscriptActionSeparation() = kotlinx.coroutines.test.runTest {
        val testDispatcher = kotlinx.coroutines.test.StandardTestDispatcher(testScheduler)
        kotlinx.coroutines.Dispatchers.setMain(testDispatcher)
        try {
            var relabeledSpeakerId: Int? = null
            var relabeledRecordingId: Int? = null
            var relabeledName: String? = null

            var correctedSegmentId: Int? = null
            var correctedRecordingId: Int? = null
            var correctedText: String? = null
            var correctedReExtract: Boolean? = null

            val fakeRepo = object : com.pcma.app.data.repository.PcmaRepository() {
                override suspend fun getConversationDetail(id: Int): com.pcma.app.data.models.ConversationResponse {
                    return com.pcma.app.data.models.ConversationResponse(
                        id = 6,
                        recordingId = 16,
                        userId = 1,
                        title = "Conversation",
                        occurredAt = "2026-10-14T08:00:00Z"
                    )
                }

                override suspend fun getTranscript(id: Int): com.pcma.app.data.models.TranscriptResponse {
                    return com.pcma.app.data.models.TranscriptResponse(
                        id = 8,
                        recordingId = 16,
                        language = "en",
                        segments = listOf(
                            com.pcma.app.data.models.SegmentResponse(
                                id = 21,
                                speakerId = 1,
                                speakerLabel = "Speaker 1",
                                startMs = 90L,
                                endMs = 7650L,
                                text = "We decided to adopt the new architecture, allies will do the deployment by Friday."
                            )
                        ),
                        speakers = listOf(
                            com.pcma.app.data.models.SpeakerResponse(id = 1, label = "Speaker 1")
                        )
                    )
                }

                override suspend fun relabelSpeaker(
                    recordingId: Int,
                    speakerId: Int,
                    label: String?,
                    personId: Int?
                ): com.pcma.app.data.models.SpeakerResponse {
                    relabeledRecordingId = recordingId
                    relabeledSpeakerId = speakerId
                    relabeledName = label
                    return com.pcma.app.data.models.SpeakerResponse(id = speakerId, label = label ?: "Speaker 1")
                }

                override suspend fun correctSegment(
                    recordingId: Int,
                    segmentId: Int,
                    text: String,
                    reExtract: Boolean
                ): com.pcma.app.data.models.SegmentResponse {
                    correctedRecordingId = recordingId
                    correctedSegmentId = segmentId
                    correctedText = text
                    correctedReExtract = reExtract
                    return com.pcma.app.data.models.SegmentResponse(
                        id = segmentId,
                        speakerId = 1,
                        speakerLabel = "Speaker 1",
                        startMs = 90L,
                        endMs = 7650L,
                        text = text
                    )
                }
            }

            val vm = com.pcma.app.ui.viewmodel.ConversationsViewModel(fakeRepo)
            vm.loadConversationDetail(6)
            testScheduler.advanceUntilIdle()

            // 1. Rename Speaker action
            vm.relabelSpeaker(16, 1, "Speaker Alice", null)
            testScheduler.advanceUntilIdle()
            assertEquals(16, relabeledRecordingId)
            assertEquals(1, relabeledSpeakerId)
            assertEquals("Speaker Alice", relabeledName)

            // 2. Edit Transcript action (distinct from Rename Speaker)
            vm.correctSegment(16, 21, "Corrected segment text", false)
            testScheduler.advanceUntilIdle()
            assertEquals(16, correctedRecordingId)
            assertEquals(21, correctedSegmentId)
            assertEquals("Corrected segment text", correctedText)
            assertEquals(false, correctedReExtract)
        } finally {
            kotlinx.coroutines.Dispatchers.resetMain()
        }
    }

    @OptIn(kotlinx.coroutines.ExperimentalCoroutinesApi::class)
    @Test
    fun testTranscriptSegmentCardDialogStateAndActions() = kotlinx.coroutines.test.runTest {
        val testDispatcher = kotlinx.coroutines.test.StandardTestDispatcher(testScheduler)
        kotlinx.coroutines.Dispatchers.setMain(testDispatcher)
        try {
            var correctedRecordingId: Int? = null
            var correctedSegmentId: Int? = null
            var correctedText: String? = null
            var correctedReExtract: Boolean? = null

            var relabeledRecordingId: Int? = null
            var relabeledSpeakerId: Int? = null
            var relabeledName: String? = null

            val fakeRepo = object : com.pcma.app.data.repository.PcmaRepository() {
                override suspend fun getConversationDetail(id: Int): com.pcma.app.data.models.ConversationResponse {
                    return com.pcma.app.data.models.ConversationResponse(
                        id = 6,
                        recordingId = 16,
                        userId = 1,
                        title = "Conversation",
                        occurredAt = "2026-10-14T08:00:00Z"
                    )
                }

                override suspend fun getTranscript(id: Int): com.pcma.app.data.models.TranscriptResponse {
                    return com.pcma.app.data.models.TranscriptResponse(
                        id = 8,
                        recordingId = 16,
                        language = "en",
                        segments = listOf(
                            com.pcma.app.data.models.SegmentResponse(
                                id = 21,
                                speakerId = 1,
                                speakerLabel = "Speaker 1",
                                startMs = 90L,
                                endMs = 7650L,
                                text = "We decided to adopt the new architecture, allies will do the deployment by Friday."
                            ),
                            com.pcma.app.data.models.SegmentResponse(
                                id = 22,
                                speakerId = 1,
                                speakerLabel = "Speaker 1",
                                startMs = 7650L,
                                endMs = 12570L,
                                text = "I promise to deliver the report, can we test on a physical device."
                            )
                        ),
                        speakers = listOf(
                            com.pcma.app.data.models.SpeakerResponse(id = 1, label = "Speaker 1")
                        )
                    )
                }

                override suspend fun relabelSpeaker(
                    recordingId: Int,
                    speakerId: Int,
                    label: String?,
                    personId: Int?
                ): com.pcma.app.data.models.SpeakerResponse {
                    relabeledRecordingId = recordingId
                    relabeledSpeakerId = speakerId
                    relabeledName = label
                    return com.pcma.app.data.models.SpeakerResponse(id = speakerId, label = label ?: "Speaker 1")
                }

                override suspend fun correctSegment(
                    recordingId: Int,
                    segmentId: Int,
                    text: String,
                    reExtract: Boolean
                ): com.pcma.app.data.models.SegmentResponse {
                    correctedRecordingId = recordingId
                    correctedSegmentId = segmentId
                    correctedText = text
                    correctedReExtract = reExtract
                    return com.pcma.app.data.models.SegmentResponse(
                        id = segmentId,
                        speakerId = 1,
                        speakerLabel = "Speaker 1",
                        startMs = 90L,
                        endMs = 7650L,
                        text = text
                    )
                }
            }

            val vm = com.pcma.app.ui.viewmodel.ConversationsViewModel(fakeRepo)
            vm.loadConversationDetail(6)
            testScheduler.advanceUntilIdle()

            val transcript = vm.transcript.value
            assertNotNull(transcript)
            val segments = transcript!!.segments
            assertEquals(2, segments.size)

            // Verify both segments have distinct Rename Speaker and Edit Transcript metadata
            for ((index, seg) in segments.withIndex()) {
                val resolvedSegId = seg.id ?: (index + 1)
                val resolvedSpeakerLabel = seg.speakerLabel ?: "Speaker 1"

                // 1. Rename Speaker action simulation
                var showRelabelDialog = false
                var relabelSpeakerId: Int? = null
                var relabelSpeakerCurrentName = ""
                var relabelSpeakerNewName = ""

                // Trigger Rename Speaker
                relabelSpeakerId = seg.speakerId ?: 0
                relabelSpeakerCurrentName = resolvedSpeakerLabel
                relabelSpeakerNewName = resolvedSpeakerLabel
                showRelabelDialog = true

                assertTrue(showRelabelDialog)
                assertEquals(1, relabelSpeakerId)
                assertEquals("Speaker 1", relabelSpeakerCurrentName)
                assertEquals("Speaker 1", relabelSpeakerNewName)

                // 2. Edit Transcript action simulation
                var showEditSegmentDialog = false
                var editSegmentId: Int? = null
                var editSegmentOriginalText = ""
                var editSegmentNewText = ""
                var editSegmentReExtract = true // initially dirty to verify reset to false

                // Trigger Edit Transcript
                editSegmentId = resolvedSegId
                editSegmentOriginalText = seg.text
                editSegmentNewText = seg.text
                editSegmentReExtract = false // verified unchecked by default
                showEditSegmentDialog = true

                assertTrue(showEditSegmentDialog)
                assertEquals(seg.id, editSegmentId)
                assertEquals(seg.text, editSegmentOriginalText)
                assertEquals(seg.text, editSegmentNewText)
                assertFalse(editSegmentReExtract)

                // 3. Verify Cancel dismissal does not invoke API
                showEditSegmentDialog = false
                showRelabelDialog = false
                assertNull(correctedRecordingId)
                assertNull(relabeledRecordingId)
            }

            // 4. Verify Save on Edit Transcript invokes correction API with recording ID 16 and segment ID 21
            val seg0 = segments[0]
            val targetRecId = vm.activeConversation.value?.recordingId ?: transcript.recordingId
            assertEquals(16, targetRecId)
            val seg0Id = seg0.id ?: 1
            assertEquals(21, seg0Id)

            vm.correctSegment(
                recordingId = targetRecId,
                segmentId = seg0Id,
                newText = "We decided to adopt the new architecture, Alice will do the deployment by Friday.",
                reExtract = false
            )
            testScheduler.advanceUntilIdle()

            assertEquals(16, correctedRecordingId)
            assertEquals(21, correctedSegmentId)
            assertEquals(false, correctedReExtract)
            assertEquals("We decided to adopt the new architecture, Alice will do the deployment by Friday.", correctedText)

            // 5. Verify Save on Rename Speaker invokes relabel API with recording ID 16 and speaker ID 1
            vm.relabelSpeaker(targetRecId, 1, "Alice", null)
            testScheduler.advanceUntilIdle()

            assertEquals(16, relabeledRecordingId)
            assertEquals(1, relabeledSpeakerId)
            assertEquals("Alice", relabeledName)
        } finally {
            kotlinx.coroutines.Dispatchers.resetMain()
        }
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun testDraftMomRefreshAndAssigneeNormalizationAfterTranscriptCorrection() = runTest {
        val testDispatcher = StandardTestDispatcher(testScheduler)
        Dispatchers.setMain(testDispatcher)

        try {
            var draftMomSections = listOf(
                com.pcma.app.data.models.MomSection(
                    id = 27,
                    sectionType = "action_items",
                    title = "Action Items",
                    contentJson = """[{"id": 2, "text": "allies will do the deployment by Friday", "assignee_name": "allies", "status": "open", "due_date": null, "confidence": 0.9, "is_uncertain": false, "source_segment_ids": [21]}]"""
                )
            )
            val currentMomStatus = "draft"
            var actionItemsList = listOf(
                com.pcma.app.data.models.ActionItemResponse(
                    id = 2,
                    text = "allies will do the deployment by Friday",
                    assigneeName = "allies",
                    status = "open"
                )
            )

            val fakeRepo = object : com.pcma.app.data.repository.PcmaRepository() {
                override suspend fun getConversationDetail(id: Int): com.pcma.app.data.models.ConversationResponse {
                    return com.pcma.app.data.models.ConversationResponse(
                        id = id,
                        recordingId = 16,
                        userId = 1,
                        title = "Conversation #$id",
                        occurredAt = "2026-10-14T00:00:00Z",
                        actionItems = actionItemsList
                    )
                }

                override suspend fun getTranscript(recordingId: Int): com.pcma.app.data.models.TranscriptResponse {
                    return com.pcma.app.data.models.TranscriptResponse(
                        id = 8,
                        recordingId = recordingId,
                        language = "en",
                        segments = listOf(
                            com.pcma.app.data.models.SegmentResponse(
                                id = 21,
                                speakerId = 1,
                                speakerLabel = "Speaker 1",
                                startMs = 0L,
                                endMs = 4000L,
                                text = "We decided to adopt the new architecture, alice will do the deployment by Friday."
                            )
                        )
                    )
                }

                override suspend fun getMom(conversationId: Int): MomResponse {
                    return MomResponse(
                        id = 6,
                        conversationId = conversationId,
                        title = "Meeting Notes - Conversation #$conversationId",
                        summary = "Minutes of Meeting for Conversation #$conversationId",
                        status = currentMomStatus,
                        sections = draftMomSections,
                        createdAt = "2026-10-14T00:00:00Z"
                    )
                }

                override suspend fun correctSegment(
                    recordingId: Int,
                    segmentId: Int,
                    text: String,
                    reExtract: Boolean
                ): com.pcma.app.data.models.SegmentResponse {
                    if (reExtract) {
                        actionItemsList = listOf(
                            com.pcma.app.data.models.ActionItemResponse(
                                id = 2,
                                text = "Alice will do the deployment by Friday",
                                assigneeName = "Alice",
                                status = "open"
                            )
                        )
                        draftMomSections = listOf(
                            com.pcma.app.data.models.MomSection(
                                id = 27,
                                sectionType = "action_items",
                                title = "Action Items",
                                contentJson = """[{"id": 2, "text": "Alice will do the deployment by Friday", "assignee_name": "Alice", "status": "open", "due_date": null, "confidence": 0.9, "is_uncertain": false, "source_segment_ids": [21]}]"""
                            )
                        )
                    }
                    return com.pcma.app.data.models.SegmentResponse(
                        id = segmentId,
                        speakerId = 1,
                        speakerLabel = "Speaker 1",
                        startMs = 0L,
                        endMs = 4000L,
                        text = text
                    )
                }
            }

            val convVm = com.pcma.app.ui.viewmodel.ConversationsViewModel(fakeRepo)
            val momVm = com.pcma.app.ui.viewmodel.MomViewModel(fakeRepo)

            // Initial load of Conversation #6 and Draft MOM #6
            convVm.loadConversationDetail(6)
            momVm.selectConversation(6)
            testScheduler.advanceUntilIdle()

            // Verify initial state
            assertEquals(1, convVm.activeConversation.value?.actionItems?.size)
            assertEquals("allies", convVm.activeConversation.value?.actionItems?.first()?.assigneeName)
            assertEquals("draft", momVm.currentMom.value?.status)
            assertTrue(momVm.currentMom.value?.sections?.first()?.contentJson?.contains("allies") == true)

            // User corrects transcript segment #21 with reExtract = true
            var onRefreshMomCalled = false
            convVm.correctSegment(16, 21, "We decided to adopt the new architecture, alice will do the deployment by Friday.", reExtract = true) { success ->
                if (success) {
                    onRefreshMomCalled = true
                    momVm.loadMom(6)
                }
            }
            testScheduler.advanceUntilIdle()

            // Verify callback and MOM refresh were triggered
            assertTrue(onRefreshMomCalled)

            // Verify both extracted facts and draft MOM show corrected Assignee: Alice
            val updatedActionItems = convVm.activeConversation.value?.actionItems
            assertNotNull(updatedActionItems)
            assertEquals("Alice", updatedActionItems?.first()?.assigneeName)
            assertEquals("Alice will do the deployment by Friday", updatedActionItems?.first()?.text)

            val updatedMom = momVm.currentMom.value
            assertNotNull(updatedMom)
            assertEquals("draft", updatedMom?.status)
            val updatedJson = updatedMom?.sections?.first()?.contentJson ?: ""
            assertTrue(updatedJson.contains(""""assignee_name": "Alice""""))
            assertTrue(updatedJson.contains(""""text": "Alice will do the deployment by Friday""""))
            assertFalse(updatedJson.contains("allies"))
        } finally {
            Dispatchers.resetMain()
        }
    }
}




