package com.pcma.app.ui.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.*
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.google.gson.JsonParser
import com.pcma.app.data.models.*
import com.pcma.app.ui.theme.*
import com.pcma.app.ui.viewmodel.*

// ==========================================
// 1. LOGIN SCREEN
// ==========================================
@Composable
fun LoginScreen(onLoginSuccess: () -> Unit, mainViewModel: MainViewModel) {
    val context = androidx.compose.ui.platform.LocalContext.current

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(BackgroundDark)
            .padding(28.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Surface(
            color = PrimaryPurple.copy(alpha = 0.15f),
            shape = CircleShape,
            modifier = Modifier.size(96.dp)
        ) {
            Box(contentAlignment = Alignment.Center) {
                Icon(
                    imageVector = Icons.Default.GraphicEq,
                    contentDescription = null,
                    tint = PrimaryPurple,
                    modifier = Modifier.size(48.dp)
                )
            }
        }

        Spacer(modifier = Modifier.height(24.dp))

        Text(
            text = "PCMA",
            style = MaterialTheme.typography.headlineMedium,
            color = TextWhite,
            fontWeight = FontWeight.Bold
        )
        Text(
            text = "Personal Conversation Memory Assistant",
            style = MaterialTheme.typography.bodyMedium,
            color = TextMuted,
            textAlign = TextAlign.Center
        )

        Spacer(modifier = Modifier.height(36.dp))

        Card(
            modifier = Modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(containerColor = CardDark),
            border = BorderStroke(1.dp, CardBorder)
        ) {
            Column(modifier = Modifier.padding(20.dp)) {
                Text(
                    text = "Sign In",
                    style = MaterialTheme.typography.titleMedium,
                    color = TextWhite,
                    fontWeight = FontWeight.Bold
                )
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = "Sign in securely to manage your conversations and meeting notes.",
                    style = MaterialTheme.typography.bodySmall,
                    color = TextMuted
                )

                Spacer(modifier = Modifier.height(20.dp))

                Button(
                    onClick = {
                        mainViewModel.loginWithAuth0(context, onLoginSuccess)
                    },
                    modifier = Modifier.fillMaxWidth(),
                    colors = ButtonDefaults.buttonColors(containerColor = PrimaryPurple),
                    shape = RoundedCornerShape(8.dp)
                ) {
                    Icon(Icons.Default.Lock, contentDescription = null, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(8.dp))
                    Text("Sign In Securely", fontWeight = FontWeight.SemiBold)
                }

                if (com.pcma.app.BuildConfig.DEBUG) {
                    Spacer(modifier = Modifier.height(12.dp))
                    OutlinedButton(
                        onClick = {
                            mainViewModel.login(devMode = true)
                            onLoginSuccess()
                        },
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(8.dp),
                        border = BorderStroke(1.dp, SecondarySlate)
                    ) {
                        Text("Development Mode Login", color = TextMuted, fontSize = 13.sp)
                    }
                }
            }
        }
    }
}

// ==========================================
// 2. ONBOARDING & CONSENT SCREEN
// ==========================================
@Composable
fun OnboardingConsentScreen(onConsentConfirmed: () -> Unit, mainViewModel: MainViewModel) {
    var selectedJurisdiction by remember { mutableStateOf("US-CA") }
    val jurisdictions = listOf(
        "US-CA" to "California, USA (All-Party Consent)",
        "US-NY" to "New York, USA (One-Party Consent)",
        "EU-GDPR" to "European Union (GDPR Compliant)",
        "UK" to "United Kingdom (UK-GDPR)",
        "IN" to "India (DPDP Act 2023)",
        "GENERIC-ALL" to "All-Party Consent (Default Global)"
    )

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(BackgroundDark)
            .padding(20.dp)
    ) {
        Text("Recording Consent & Privacy", style = MaterialTheme.typography.titleLarge, color = TextWhite, fontWeight = FontWeight.Bold)
        Spacer(modifier = Modifier.height(4.dp))
        Text("Select your region to ensure local recording consent rules are applied.", style = MaterialTheme.typography.bodySmall, color = TextMuted)

        Spacer(modifier = Modifier.height(20.dp))

        Card(
            modifier = Modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(containerColor = CardDark),
            border = BorderStroke(1.dp, CardBorder)
        ) {
            Column(modifier = Modifier.padding(12.dp)) {
                jurisdictions.forEach { (id, label) ->
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable { selectedJurisdiction = id }
                            .padding(vertical = 10.dp, horizontal = 8.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        RadioButton(
                            selected = (selectedJurisdiction == id),
                            onClick = { selectedJurisdiction = id },
                            colors = RadioButtonDefaults.colors(selectedColor = PrimaryPurple)
                        )
                        Spacer(modifier = Modifier.width(10.dp))
                        Text(label, color = TextWhite, fontSize = 14.sp)
                    }
                }
            }
        }

        Spacer(modifier = Modifier.height(24.dp))

        Button(
            onClick = {
                mainViewModel.updateJurisdiction(selectedJurisdiction) {
                    onConsentConfirmed()
                }
            },
            modifier = Modifier.fillMaxWidth(),
            colors = ButtonDefaults.buttonColors(containerColor = PrimaryPurple),
            shape = RoundedCornerShape(8.dp)
        ) {
            Text("Confirm & Continue", fontWeight = FontWeight.SemiBold)
        }
    }
}

// ==========================================
// 3. RECORD SCREEN
// ==========================================
@Composable
fun RecordScreen(
    viewModel: RecordingViewModel,
    cacheDir: java.io.File,
    onOpenConversation: (Int) -> Unit,
    onNavigateChats: () -> Unit = {},
    onNavigateMom: () -> Unit = {},
    onNavigateAssistant: () -> Unit = {}
) {
    val state by viewModel.recordingState.collectAsState()
    val duration by viewModel.durationSeconds.collectAsState()
    val error by viewModel.errorMessage.collectAsState()
    val abandonedRec by viewModel.abandonedRecording.collectAsState()
    val isRecovering by viewModel.isRecovering.collectAsState()
    val stage by viewModel.processingStage.collectAsState()
    val context = androidx.compose.ui.platform.LocalContext.current
    var showConsentPrompt by remember { mutableStateOf(false) }
    var showDiscardDialog by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) {
        viewModel.refreshLatestStatus()
    }

    if (showDiscardDialog && abandonedRec != null) {
        AlertDialog(
            onDismissRequest = { showDiscardDialog = false },
            title = {
                Text(
                    "Discard Unfinalized Session?",
                    color = TextWhite,
                    fontWeight = FontWeight.Bold,
                    fontSize = 17.sp
                )
            },
            text = {
                Text(
                    "Discarding Session #${abandonedRec?.id} will cancel the open session on the server and allow you to begin a fresh recording session. Previously completed recordings will not be affected.",
                    color = TextMuted,
                    fontSize = 14.sp
                )
            },
            confirmButton = {
                Button(
                    onClick = {
                        showDiscardDialog = false
                        viewModel.discardAbandonedRecording()
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = AccentDanger),
                    shape = RoundedCornerShape(8.dp)
                ) {
                    Text("Discard Session")
                }
            },
            dismissButton = {
                TextButton(onClick = { showDiscardDialog = false }) {
                    Text("Keep Session", color = TextMuted)
                }
            },
            containerColor = CardDark
        )
    }

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .background(BackgroundDark)
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        item {
            Column {
                Text("Record Meeting", style = MaterialTheme.typography.titleLarge, color = TextWhite, fontWeight = FontWeight.Bold)
                Text("Capture conversations with secure, encrypted storage", style = MaterialTheme.typography.bodySmall, color = TextMuted)
            }
        }

        // Abandoned / Unfinalized Recording Recovery Card
        if (abandonedRec != null) {
            item {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = CardDark),
                    border = BorderStroke(1.dp, AccentWarning)
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.Default.Warning, contentDescription = null, tint = AccentWarning)
                            Spacer(Modifier.width(8.dp))
                            Text(
                                "Unsaved Recording Detected (#${abandonedRec?.id})",
                                color = TextWhite,
                                fontWeight = FontWeight.Bold,
                                fontSize = 15.sp
                            )
                        }
                        Spacer(modifier = Modifier.height(8.dp))
                        Text(
                            "A previous recording was interrupted. Recover it to process the conversation, or discard it to start fresh.",
                            color = TextMuted,
                            fontSize = 13.sp
                        )
                        Spacer(modifier = Modifier.height(14.dp))
                        if (isRecovering) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                CircularProgressIndicator(
                                    modifier = Modifier.size(18.dp),
                                    color = PrimaryPurple,
                                    strokeWidth = 2.dp
                                )
                                Spacer(Modifier.width(8.dp))
                                Text("Restoring previous recording...", color = TextMuted, fontSize = 13.sp)
                            }
                        } else {
                            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                Button(
                                    onClick = { viewModel.recoverAbandonedRecording(onOpenConversation) },
                                    colors = ButtonDefaults.buttonColors(containerColor = PrimaryPurple),
                                    modifier = Modifier.weight(1f),
                                    shape = RoundedCornerShape(8.dp)
                                ) {
                                    Icon(Icons.Default.Refresh, contentDescription = null, modifier = Modifier.size(16.dp))
                                    Spacer(Modifier.width(4.dp))
                                    Text("Recover", fontSize = 13.sp)
                                }
                                OutlinedButton(
                                    onClick = { showDiscardDialog = true },
                                    colors = ButtonDefaults.outlinedButtonColors(contentColor = AccentDanger),
                                    border = BorderStroke(1.dp, AccentDanger),
                                    modifier = Modifier.weight(1f),
                                    shape = RoundedCornerShape(8.dp)
                                ) {
                                    Icon(Icons.Default.Delete, contentDescription = null, modifier = Modifier.size(16.dp))
                                    Spacer(Modifier.width(4.dp))
                                    Text("Discard", fontSize = 13.sp)
                                }
                            }
                        }
                    }
                }
            }
        }

        // Main Recording Card
        item {
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = CardDark),
                border = BorderStroke(1.dp, if (state == "recording") AccentDanger else CardBorder)
            ) {
                Column(
                    modifier = Modifier.padding(24.dp),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    // Status Badge
                    val (badgeText, badgeColor) = when (state) {
                        "recording" -> "Recording" to AccentDanger
                        "paused" -> "Paused" to AccentWarning
                        "uploading" -> "Saving audio..." to PrimaryPurple
                        "processing" -> "Transcribing audio..." to PrimaryPurple
                        "ready" -> "Ready" to AccentSuccess
                        "failed" -> "Recording failed" to AccentDanger
                        else -> "Ready to record" to SecondarySlate
                    }

                    Surface(
                        color = badgeColor.copy(alpha = 0.15f),
                        shape = RoundedCornerShape(12.dp)
                    ) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp)
                        ) {
                            Surface(
                                color = badgeColor,
                                shape = CircleShape,
                                modifier = Modifier.size(8.dp)
                            ) {}
                            Spacer(Modifier.width(6.dp))
                            Text(
                                text = badgeText,
                                color = badgeColor,
                                fontSize = 11.sp,
                                fontWeight = FontWeight.Bold
                            )
                        }
                    }

                    Spacer(modifier = Modifier.height(16.dp))

                    // Timer Display
                    Text(
                        text = String.format("%02d:%02d", duration / 60, duration % 60),
                        fontSize = 48.sp,
                        fontWeight = FontWeight.Bold,
                        color = if (state == "recording") AccentDanger else TextWhite
                    )

                    Spacer(modifier = Modifier.height(20.dp))

                    // Recording Controls
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.Center
                    ) {
                        if (state == "idle" || state == "ready" || state == "failed") {
                            Button(
                                onClick = {
                                    if (abandonedRec != null) {
                                        viewModel.checkForAbandonedRecording()
                                    } else if (viewModel.repository.storage.consentAcknowledged) {
                                        viewModel.startRecording(cacheDir, context)
                                    } else {
                                        showConsentPrompt = true
                                    }
                                },
                                colors = ButtonDefaults.buttonColors(containerColor = AccentDanger),
                                shape = RoundedCornerShape(24.dp),
                                modifier = Modifier.height(48.dp)
                            ) {
                                Icon(Icons.Default.Mic, contentDescription = null)
                                Spacer(Modifier.width(8.dp))
                                Text("Start Recording", fontWeight = FontWeight.SemiBold)
                            }
                        }

                        if (state == "recording") {
                            OutlinedButton(
                                onClick = { viewModel.pauseRecording() },
                                colors = ButtonDefaults.outlinedButtonColors(contentColor = TextWhite),
                                border = BorderStroke(1.dp, SecondarySlate),
                                shape = RoundedCornerShape(24.dp)
                            ) {
                                Icon(Icons.Default.Pause, contentDescription = null, modifier = Modifier.size(18.dp))
                                Spacer(Modifier.width(6.dp))
                                Text("Pause")
                            }
                            Spacer(Modifier.width(12.dp))
                            Button(
                                onClick = { viewModel.stopRecording(cacheDir, context, onOpenConversation) },
                                colors = ButtonDefaults.buttonColors(containerColor = AccentDanger),
                                shape = RoundedCornerShape(24.dp)
                            ) {
                                Icon(Icons.Default.Stop, contentDescription = null, modifier = Modifier.size(18.dp))
                                Spacer(Modifier.width(6.dp))
                                Text("Finish Recording")
                            }
                        }

                        if (state == "paused") {
                            Button(
                                onClick = { viewModel.resumeRecording() },
                                colors = ButtonDefaults.buttonColors(containerColor = PrimaryPurple),
                                shape = RoundedCornerShape(24.dp)
                            ) {
                                Icon(Icons.Default.PlayArrow, contentDescription = null, modifier = Modifier.size(18.dp))
                                Spacer(Modifier.width(6.dp))
                                Text("Resume")
                            }
                            Spacer(Modifier.width(12.dp))
                            Button(
                                onClick = { viewModel.stopRecording(cacheDir, context, onOpenConversation) },
                                colors = ButtonDefaults.buttonColors(containerColor = AccentDanger),
                                shape = RoundedCornerShape(24.dp)
                            ) {
                                Icon(Icons.Default.Stop, contentDescription = null, modifier = Modifier.size(18.dp))
                                Spacer(Modifier.width(6.dp))
                                Text("Finish Recording")
                            }
                        }
                    }

                    // Processing Feedback Card
                    if (state == "processing" || state == "uploading") {
                        Spacer(modifier = Modifier.height(20.dp))
                        Surface(
                            color = BackgroundDark,
                            shape = RoundedCornerShape(8.dp),
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Row(
                                modifier = Modifier.padding(14.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                CircularProgressIndicator(
                                    modifier = Modifier.size(20.dp),
                                    color = PrimaryPurple,
                                    strokeWidth = 2.dp
                                )
                                Spacer(Modifier.width(12.dp))
                                Column {
                                    Text(
                                        text = stage ?: "Processing audio...",
                                        color = TextWhite,
                                        fontSize = 13.sp,
                                        fontWeight = FontWeight.Medium
                                    )
                                    Text(
                                        text = "Please keep app open while processing completes",
                                        color = TextMuted,
                                        fontSize = 11.sp
                                    )
                                }
                            }
                        }
                    }

                    // Error Message
                    error?.let {
                        Spacer(modifier = Modifier.height(14.dp))
                        Surface(
                            color = AccentDanger.copy(alpha = 0.1f),
                            shape = RoundedCornerShape(6.dp),
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text(
                                text = it,
                                color = AccentDanger,
                                fontSize = 12.sp,
                                modifier = Modifier.padding(10.dp)
                            )
                        }
                    }
                }
            }
        }

        // Quick Navigation Shortcuts
        item {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                OutlinedButton(
                    onClick = onNavigateChats,
                    modifier = Modifier.weight(1f),
                    shape = RoundedCornerShape(8.dp),
                    border = BorderStroke(1.dp, CardBorder)
                ) {
                    Icon(Icons.AutoMirrored.Filled.LibraryBooks, contentDescription = null, modifier = Modifier.size(14.dp), tint = PrimaryPurple)
                    Spacer(Modifier.width(6.dp))
                    Text("Chats", color = TextWhite, fontSize = 12.sp)
                }
                OutlinedButton(
                    onClick = onNavigateMom,
                    modifier = Modifier.weight(1f),
                    shape = RoundedCornerShape(8.dp),
                    border = BorderStroke(1.dp, CardBorder)
                ) {
                    Icon(Icons.Default.Description, contentDescription = null, modifier = Modifier.size(14.dp), tint = PrimaryPurple)
                    Spacer(Modifier.width(6.dp))
                    Text("Notes", color = TextWhite, fontSize = 12.sp)
                }
                OutlinedButton(
                    onClick = onNavigateAssistant,
                    modifier = Modifier.weight(1f),
                    shape = RoundedCornerShape(8.dp),
                    border = BorderStroke(1.dp, CardBorder)
                ) {
                    Icon(Icons.Default.SmartToy, contentDescription = null, modifier = Modifier.size(14.dp), tint = PrimaryPurple)
                    Spacer(Modifier.width(6.dp))
                    Text("Ask AI", color = TextWhite, fontSize = 12.sp)
                }
            }
        }

        // Privacy & Data Protection Card
        item {
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = CardDark),
                border = BorderStroke(1.dp, CardBorder)
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text("Privacy & Data Protection", color = TextWhite, fontWeight = FontWeight.Bold, fontSize = 13.sp)
                    Spacer(Modifier.height(8.dp))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.Security, contentDescription = null, tint = AccentSuccess, modifier = Modifier.size(14.dp))
                        Spacer(Modifier.width(6.dp))
                        Text("Audio recordings are encrypted and protected on device", color = TextMuted, fontSize = 12.sp)
                    }
                    Spacer(Modifier.height(4.dp))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.GraphicEq, contentDescription = null, tint = PrimaryPurple, modifier = Modifier.size(14.dp))
                        Spacer(Modifier.width(6.dp))
                        Text("Private on-device voice processing and speaker recognition", color = TextMuted, fontSize = 12.sp)
                    }
                }
            }
        }
    }

    if (showConsentPrompt) {
        AlertDialog(
            onDismissRequest = {
                showConsentPrompt = false
                viewModel.onConsentDeclined()
            },
            title = { Text("Recording Consent", color = TextWhite, fontWeight = FontWeight.Bold) },
            text = {
                Text(
                    "By continuing, you confirm that all participants in this conversation have consented to recording and AI transcription.",
                    color = TextMuted
                )
            },
            confirmButton = {
                Button(
                    onClick = {
                        viewModel.repository.storage.consentAcknowledged = true
                        showConsentPrompt = false
                        viewModel.startRecording(cacheDir, context, consentAcknowledged = true)
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = PrimaryPurple)
                ) {
                    Text("Confirm & Record")
                }
            },
            dismissButton = {
                TextButton(
                    onClick = {
                        showConsentPrompt = false
                        viewModel.onConsentDeclined()
                    }
                ) {
                    Text("Cancel", color = AccentDanger)
                }
            },
            containerColor = CardDark
        )
    }
}

// ==========================================
// 4. CONVERSATIONS SCREEN (LIBRARY / CHATS)
// ==========================================
@Composable
fun ConversationsScreen(
    viewModel: ConversationsViewModel,
    selectedConversationId: Int? = null,
    onSelectConversation: (Int) -> Unit,
    onOpenMom: ((Int) -> Unit)? = null,
    onNavigateRecord: () -> Unit = {},
    onReauthenticate: (() -> Unit)? = null,
    onLogout: (() -> Unit)? = null
) {
    val conversations by viewModel.conversations.collectAsState()
    val isLoading by viewModel.isLoading.collectAsState()
    val errorMessage by viewModel.errorMessage.collectAsState()

    LaunchedEffect(Unit) { viewModel.loadConversations() }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(BackgroundDark)
            .padding(16.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text("Conversations", style = MaterialTheme.typography.titleLarge, color = TextWhite, fontWeight = FontWeight.Bold)
                Text("${conversations.size} recorded conversations", style = MaterialTheme.typography.bodySmall, color = TextMuted)
            }
            IconButton(onClick = { viewModel.loadConversations() }) {
                Icon(Icons.Default.Refresh, contentDescription = "Refresh", tint = PrimaryPurple)
            }
        }

        Spacer(modifier = Modifier.height(12.dp))

        if (isLoading && conversations.isEmpty()) {
            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator(color = PrimaryPurple)
            }
        } else if (errorMessage != null && conversations.isEmpty()) {
            val isAuthError = errorMessage?.contains("expired", ignoreCase = true) == true ||
                              errorMessage?.contains("unauthorized", ignoreCase = true) == true ||
                              errorMessage?.contains("401") == true

            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.padding(24.dp)) {
                    Icon(
                        if (isAuthError) Icons.Default.Lock else Icons.Default.Warning,
                        contentDescription = null,
                        tint = if (isAuthError) PrimaryPurple else AccentDanger,
                        modifier = Modifier.size(56.dp)
                    )
                    Spacer(modifier = Modifier.height(12.dp))
                    Text(
                        if (isAuthError) "Session Expired" else "Failed to Load Conversations",
                        color = TextWhite,
                        fontWeight = FontWeight.Bold,
                        fontSize = 16.sp
                    )
                    Spacer(modifier = Modifier.height(6.dp))
                    Text(
                        if (isAuthError) "Your login session has expired. Please sign in again to load your conversations." else (errorMessage ?: ""),
                        color = TextMuted,
                        fontSize = 13.sp,
                        textAlign = TextAlign.Center
                    )
                    Spacer(modifier = Modifier.height(16.dp))

                    if (isAuthError && onReauthenticate != null) {
                        Button(
                            onClick = onReauthenticate,
                            modifier = Modifier.fillMaxWidth(0.85f),
                            colors = ButtonDefaults.buttonColors(containerColor = PrimaryPurple)
                        ) {
                            Icon(Icons.Default.Lock, contentDescription = null, modifier = Modifier.size(16.dp))
                            Spacer(Modifier.width(6.dp))
                            Text("Sign In Again")
                        }
                        if (onLogout != null) {
                            Spacer(modifier = Modifier.height(8.dp))
                            OutlinedButton(
                                onClick = onLogout,
                                modifier = Modifier.fillMaxWidth(0.85f),
                                border = BorderStroke(1.dp, SecondarySlate)
                            ) {
                                Text("Log Out", color = TextMuted)
                            }
                        }
                    } else {
                        Button(
                            onClick = { viewModel.loadConversations() },
                            colors = ButtonDefaults.buttonColors(containerColor = PrimaryPurple)
                        ) {
                            Icon(Icons.Default.Refresh, contentDescription = null, modifier = Modifier.size(16.dp))
                            Spacer(Modifier.width(6.dp))
                            Text("Retry")
                        }
                    }
                }
            }
        } else if (conversations.isEmpty()) {
            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.padding(24.dp)) {
                    Icon(
                        Icons.AutoMirrored.Filled.LibraryBooks,
                        contentDescription = null,
                        tint = TextMuted,
                        modifier = Modifier.size(56.dp)
                    )
                    Spacer(modifier = Modifier.height(12.dp))
                    Text("No conversations recorded yet.", color = TextWhite, fontWeight = FontWeight.Medium, fontSize = 16.sp)
                    Spacer(modifier = Modifier.height(4.dp))
                    Text("Tap Record below to capture your first conversation.", color = TextMuted, fontSize = 13.sp, textAlign = TextAlign.Center)
                    Spacer(modifier = Modifier.height(16.dp))
                    Button(
                        onClick = onNavigateRecord,
                        colors = ButtonDefaults.buttonColors(containerColor = PrimaryPurple)
                    ) {
                        Icon(Icons.Default.Mic, contentDescription = null, modifier = Modifier.size(16.dp))
                        Spacer(Modifier.width(6.dp))
                        Text("Start Recording")
                    }
                }
            }
        } else {
            LazyColumn(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                items(conversations) { conv ->
                    val rawStatus = (conv.status ?: conv.state ?: "ready").lowercase()
                    val (statusColor, statusBg, displayStatus) = when (rawStatus) {
                        "processing", "running" -> Triple(AccentWarning, AccentWarning.copy(alpha = 0.15f), "Processing")
                        "uploading", "active" -> Triple(AccentWarning, AccentWarning.copy(alpha = 0.15f), "Recording")
                        "failed" -> Triple(AccentDanger, AccentDanger.copy(alpha = 0.15f), "Failed")
                        "draft" -> Triple(PrimaryPurple, PrimaryPurple.copy(alpha = 0.15f), "Draft Notes")
                        "approved" -> Triple(AccentSuccess, AccentSuccess.copy(alpha = 0.15f), "Approved")
                        else -> Triple(AccentSuccess, AccentSuccess.copy(alpha = 0.15f), "Ready")
                    }
                    val isSelected = (conv.id == selectedConversationId)

                    Card(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable { onSelectConversation(conv.id) },
                        colors = CardDefaults.cardColors(containerColor = CardDark),
                        border = BorderStroke(
                            1.dp,
                            if (isSelected) PrimaryPurple else CardBorder
                        ),
                        shape = RoundedCornerShape(10.dp)
                    ) {
                        Column(modifier = Modifier.padding(16.dp)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text(
                                    "Conversation #${conv.id}",
                                    color = TextWhite,
                                    fontWeight = FontWeight.Bold,
                                    fontSize = 15.sp
                                )
                                Spacer(modifier = Modifier.weight(1f))
                                Surface(
                                    color = statusBg,
                                    shape = RoundedCornerShape(4.dp)
                                ) {
                                    Text(
                                        text = displayStatus,
                                        color = statusColor,
                                        fontSize = 10.sp,
                                        fontWeight = FontWeight.Bold,
                                        modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                                    )
                                }
                            }

                            Spacer(modifier = Modifier.height(8.dp))

                            conv.snippet?.let {
                                Text(
                                    "“$it”",
                                    color = TextWhite.copy(alpha = 0.85f),
                                    fontSize = 13.sp,
                                    maxLines = 2,
                                    overflow = TextOverflow.Ellipsis
                                )
                                Spacer(modifier = Modifier.height(8.dp))
                            }

                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    "Date: ${conv.createdAt ?: conv.occurredAt ?: "Recently"}",
                                    color = TextMuted,
                                    fontSize = 11.sp
                                )
                                Spacer(modifier = Modifier.weight(1f))
                                if (onOpenMom != null) {
                                    Surface(
                                        color = PrimaryPurple.copy(alpha = 0.15f),
                                        shape = RoundedCornerShape(6.dp),
                                        modifier = Modifier.clickable { onOpenMom(conv.id) }
                                    ) {
                                        Row(
                                            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                                            verticalAlignment = Alignment.CenterVertically
                                        ) {
                                            Icon(Icons.Default.Description, contentDescription = null, tint = PrimaryPurple, modifier = Modifier.size(12.dp))
                                            Spacer(Modifier.width(4.dp))
                                            Text("Notes", color = PrimaryPurple, fontSize = 11.sp, fontWeight = FontWeight.Bold)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

// ==========================================
// 5. CONVERSATION DETAIL SCREEN
// ==========================================
@Composable
fun ConversationDetailScreen(
    conversationId: Int,
    viewModel: ConversationsViewModel,
    onBack: () -> Unit,
    onOpenMom: ((Int) -> Unit)? = null,
    onRefreshMom: ((Int) -> Unit)? = null
) {
    val detail by viewModel.activeConversation.collectAsState()
    val transcript by viewModel.transcript.collectAsState()
    val extractions by viewModel.extractions.collectAsState()
    val isLoading by viewModel.isLoading.collectAsState()
    val isExtracting by viewModel.isExtracting.collectAsState()
    val extractionError by viewModel.extractionError.collectAsState()
    var selectedTab by remember { mutableStateOf(0) }

    // Speaker relabeling dialog state
    var showRelabelDialog by remember { mutableStateOf(false) }
    var relabelSpeakerId by remember { mutableStateOf<Int?>(null) }
    var relabelSpeakerCurrentName by remember { mutableStateOf("") }
    var relabelSpeakerNewName by remember { mutableStateOf("") }

    // Segment correction dialog state
    var showEditSegmentDialog by remember { mutableStateOf(false) }
    var editSegmentId by remember { mutableStateOf<Int?>(null) }
    var editSegmentOriginalText by remember { mutableStateOf("") }
    var editSegmentNewText by remember { mutableStateOf("") }
    var editSegmentReExtract by remember { mutableStateOf(false) }

    LaunchedEffect(conversationId) { viewModel.loadConversationDetail(conversationId) }

    val speakerMap = remember(transcript) {
        transcript?.speakers?.associateBy { it.id } ?: emptyMap()
    }

    fun formatMs(ms: Long): String {
        val sec = ms / 1000
        val min = sec / 60
        val remainderSec = sec % 60
        val tenths = (ms % 1000) / 100
        return String.format("%02d:%02d.%d", min, remainderSec, tenths)
    }

    fun formatRecordedDate(iso: String?): String {
        if (iso.isNullOrBlank()) return "Recently"
        return try {
            val clean = iso.replace("Z", "").replace("T", " ")
            val parts = clean.split(".")
            val datePart = parts[0]
            val parser = java.text.SimpleDateFormat("yyyy-MM-dd HH:mm:ss", java.util.Locale.getDefault()).apply {
                timeZone = java.util.TimeZone.getTimeZone("UTC")
            }
            val date = parser.parse(datePart)
            if (date != null) {
                val formatter = java.text.SimpleDateFormat("MMM d, yyyy • h:mm a", java.util.Locale.getDefault())
                formatter.format(date)
            } else {
                iso
            }
        } catch (_: Exception) {
            iso
        }
    }

    val decisions = extractions?.decisions?.ifEmpty { null } ?: detail?.decisions ?: emptyList()
    val actionItems = extractions?.actionItems?.ifEmpty { null } ?: detail?.actionItems ?: emptyList()
    val commitments = extractions?.commitments?.ifEmpty { null } ?: detail?.commitments ?: emptyList()
    val deadlines = extractions?.deadlines?.ifEmpty { null } ?: detail?.deadlines ?: emptyList()
    val questions = extractions?.questions?.ifEmpty { null } ?: detail?.questions ?: emptyList()
    val topics = extractions?.topics?.ifEmpty { null } ?: detail?.topics ?: emptyList()
    val totalFactsCount = decisions.size + actionItems.size + commitments.size + deadlines.size + questions.size

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(BackgroundDark)
    ) {
        // Compact Conversation Metadata Card
        Card(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 8.dp),
            colors = CardDefaults.cardColors(containerColor = CardDark),
            border = BorderStroke(1.dp, CardBorder)
        ) {
            Column(modifier = Modifier.padding(12.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    val resolvedConvId = detail?.id
                    val displayId = resolvedConvId ?: conversationId
                    val titleDisplay = detail?.title?.takeIf { it.isNotBlank() && it != "Conversation" }
                        ?.let { "#$displayId • $it" } ?: "Conversation #$displayId"
                    Text(
                        text = titleDisplay,
                        fontWeight = FontWeight.Bold,
                        color = TextWhite,
                        fontSize = 15.sp,
                        modifier = Modifier.weight(1f)
                    )
                    if (onOpenMom != null) {
                        Button(
                            onClick = {
                                resolvedConvId?.let { onOpenMom(it) }
                            },
                            enabled = (resolvedConvId != null && !isLoading),
                            colors = ButtonDefaults.buttonColors(
                                containerColor = PrimaryPurple,
                                disabledContainerColor = CardBorder
                            ),
                            contentPadding = PaddingValues(horizontal = 10.dp, vertical = 4.dp),
                            shape = RoundedCornerShape(6.dp)
                        ) {
                            if (isLoading && resolvedConvId == null) {
                                CircularProgressIndicator(
                                    modifier = Modifier.size(13.dp),
                                    color = TextMuted,
                                    strokeWidth = 2.dp
                                )
                                Spacer(Modifier.width(4.dp))
                                Text("Loading...", fontSize = 11.sp, color = TextMuted)
                            } else {
                                Icon(Icons.Default.Description, contentDescription = null, modifier = Modifier.size(13.dp))
                                Spacer(Modifier.width(4.dp))
                                Text("Meeting Notes", fontSize = 11.sp, fontWeight = FontWeight.SemiBold)
                            }
                        }
                    }
                }
                Spacer(Modifier.height(4.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    val statusText = detail?.status?.replace("_", " ")?.replaceFirstChar { it.uppercase() } ?: "Completed"
                    Surface(
                        color = AccentSuccess.copy(alpha = 0.15f),
                        shape = RoundedCornerShape(4.dp)
                    ) {
                        Text(
                            text = statusText,
                            color = AccentSuccess,
                            fontSize = 10.sp,
                            fontWeight = FontWeight.Bold,
                            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                        )
                    }
                    Spacer(Modifier.width(8.dp))
                    Text(
                        text = "Recorded: ${formatRecordedDate(detail?.createdAt ?: detail?.occurredAt)}",
                        color = TextMuted,
                        fontSize = 11.sp
                    )
                }
            }
        }

        // Two Tab Selection with distinctive counts
        TabRow(
            selectedTabIndex = selectedTab,
            containerColor = CardDark,
            contentColor = PrimaryPurple
        ) {
            val segCount = transcript?.segments?.size ?: 0
            Tab(
                selected = selectedTab == 0,
                onClick = { selectedTab = 0 },
                text = { Text("Transcript ($segCount)", fontWeight = FontWeight.SemiBold) }
            )
            Tab(
                selected = selectedTab == 1,
                onClick = { selectedTab = 1 },
                text = { Text("Key Takeaways ($totalFactsCount)", fontWeight = FontWeight.SemiBold) }
            )
        }

        if (isLoading && transcript == null) {
            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator(color = PrimaryPurple)
            }
        } else if (selectedTab == 0) {
            // Transcript Tab
            val segs = transcript?.segments ?: emptyList()
            if (segs.isEmpty()) {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text("No transcript segments found for this recording.", color = TextMuted)
                }
            } else {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 8.dp, bottom = 88.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    itemsIndexed(segs) { index, seg ->
                        val resolvedLabel = seg.speakerLabel
                            ?: seg.speakerId?.let { speakerMap[it]?.label ?: speakerMap[it]?.name }
                            ?: (if (transcript?.speakers?.isNotEmpty() == true) transcript?.speakers?.firstOrNull()?.label else null)
                            ?: "Speaker 1"
                        val resolvedSegId = seg.id ?: (index + 1)

                        Card(
                            modifier = Modifier.fillMaxWidth(),
                            colors = CardDefaults.cardColors(containerColor = CardDark),
                            border = BorderStroke(1.dp, CardBorder)
                        ) {
                            Column(modifier = Modifier.padding(12.dp)) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Surface(
                                        color = PrimaryPurple.copy(alpha = 0.2f),
                                        shape = RoundedCornerShape(4.dp),
                                        modifier = Modifier.clickable {
                                            relabelSpeakerId = seg.speakerId ?: 0
                                            relabelSpeakerCurrentName = resolvedLabel
                                            relabelSpeakerNewName = resolvedLabel
                                            showRelabelDialog = true
                                        }
                                    ) {
                                        Row(
                                            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                                            verticalAlignment = Alignment.CenterVertically
                                        ) {
                                            Text(
                                                text = resolvedLabel,
                                                color = PrimaryPurple,
                                                fontWeight = FontWeight.Bold,
                                                fontSize = 11.sp
                                            )
                                            Spacer(Modifier.width(4.dp))
                                            Icon(
                                                Icons.Default.Edit,
                                                contentDescription = "Rename speaker",
                                                tint = PrimaryPurple,
                                                modifier = Modifier.size(10.dp)
                                            )
                                        }
                                    }
                                    Spacer(modifier = Modifier.weight(1f))
                                    Text(
                                        text = "[${formatMs(seg.startMs)} - ${formatMs(seg.endMs)}]",
                                        color = TextMuted,
                                        fontSize = 11.sp
                                    )
                                    Spacer(modifier = Modifier.width(6.dp))
                                    IconButton(
                                        onClick = {
                                            editSegmentId = resolvedSegId
                                            editSegmentOriginalText = seg.text
                                            editSegmentNewText = seg.text
                                            editSegmentReExtract = false
                                            showEditSegmentDialog = true
                                        },
                                        modifier = Modifier.size(24.dp)
                                    ) {
                                        Icon(
                                            Icons.Default.EditNote,
                                            contentDescription = "Edit Transcript",
                                            tint = PrimaryPurple,
                                            modifier = Modifier.size(16.dp)
                                        )
                                    }
                                }
                                Spacer(modifier = Modifier.height(8.dp))
                                Text(
                                    text = seg.text,
                                    color = TextWhite,
                                    fontSize = 14.sp,
                                    lineHeight = 20.sp
                                )
                                Spacer(modifier = Modifier.height(8.dp))
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.End,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Surface(
                                        color = PrimaryPurple.copy(alpha = 0.15f),
                                        shape = RoundedCornerShape(6.dp),
                                        border = BorderStroke(1.dp, PrimaryPurple.copy(alpha = 0.4f)),
                                        modifier = Modifier.clickable {
                                            editSegmentId = resolvedSegId
                                            editSegmentOriginalText = seg.text
                                            editSegmentNewText = seg.text
                                            editSegmentReExtract = false
                                            showEditSegmentDialog = true
                                        }
                                    ) {
                                        Row(
                                            modifier = Modifier.padding(horizontal = 10.dp, vertical = 5.dp),
                                            verticalAlignment = Alignment.CenterVertically
                                        ) {
                                            Icon(
                                                Icons.Default.EditNote,
                                                contentDescription = "Edit Transcript",
                                                tint = PrimaryPurple,
                                                modifier = Modifier.size(15.dp)
                                            )
                                            Spacer(Modifier.width(4.dp))
                                            Text(
                                                text = "Edit Transcript",
                                                color = PrimaryPurple,
                                                fontSize = 11.sp,
                                                fontWeight = FontWeight.SemiBold
                                            )
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        } else {
            // Extracted Facts Tab
            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 8.dp, bottom = 88.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                // Analysis Status & Action Card
                item {
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        colors = CardDefaults.cardColors(containerColor = CardDark),
                        border = BorderStroke(1.dp, CardBorder)
                    ) {
                        Column(modifier = Modifier.padding(12.dp)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                val statusLabel = extractions?.extraction?.status ?: (if (totalFactsCount > 0) "completed" else "not_started")
                                val (statusColor, statusTitle) = when (statusLabel) {
                                    "completed" -> AccentSuccess to "Analysis Complete"
                                    "failed" -> AccentDanger to "Analysis Failed"
                                    "running" -> PrimaryPurple to "Analyzing..."
                                    else -> AccentWarning to "Ready to Analyze"
                                }

                                Surface(
                                    color = statusColor.copy(alpha = 0.15f),
                                    shape = RoundedCornerShape(4.dp)
                                ) {
                                    Text(
                                        text = statusTitle,
                                        color = statusColor,
                                        fontSize = 11.sp,
                                        fontWeight = FontWeight.Bold,
                                        modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                                    )
                                }

                                Spacer(Modifier.weight(1f))

                                if (isExtracting) {
                                    CircularProgressIndicator(
                                        modifier = Modifier.size(16.dp),
                                        color = PrimaryPurple,
                                        strokeWidth = 2.dp
                                    )
                                } else {
                                    OutlinedButton(
                                        onClick = {
                                            viewModel.retryExtraction(conversationId)
                                            onRefreshMom?.invoke(conversationId)
                                        },
                                        contentPadding = PaddingValues(horizontal = 8.dp, vertical = 2.dp),
                                        border = BorderStroke(1.dp, PrimaryPurple),
                                        shape = RoundedCornerShape(4.dp)
                                    ) {
                                        Icon(Icons.Default.Refresh, contentDescription = null, tint = PrimaryPurple, modifier = Modifier.size(12.dp))
                                        Spacer(Modifier.width(4.dp))
                                        Text(
                                            text = if (totalFactsCount > 0) "Re-analyze" else "Analyze",
                                            color = PrimaryPurple,
                                            fontSize = 11.sp
                                        )
                                    }
                                }
                            }

                            Spacer(Modifier.height(6.dp))
                            Text(
                                text = "Automated Meeting Summary\nReview and edit action items as needed.",
                                color = TextMuted,
                                fontSize = 11.sp
                            )

                            extractionError?.let { err ->
                                Spacer(Modifier.height(4.dp))
                                Text(text = "Notice: $err", color = AccentDanger, fontSize = 11.sp)
                            }
                        }
                    }
                }

                if (totalFactsCount == 0 && !isExtracting) {
                    item {
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(vertical = 32.dp),
                            contentAlignment = Alignment.Center
                        ) {
                            Text(
                                "No action items or key takeaways found yet.\nTap 'Analyze' above to review the transcript.",
                                color = TextMuted,
                                textAlign = TextAlign.Center,
                                fontSize = 13.sp
                            )
                        }
                    }
                }

                // Decisions Section
                if (decisions.isNotEmpty()) {
                    item {
                        Text(
                            text = "DECISIONS (${decisions.size})",
                            color = PrimaryPurple,
                            fontWeight = FontWeight.Bold,
                            fontSize = 12.sp,
                            modifier = Modifier.padding(top = 4.dp)
                        )
                    }
                    items(decisions) { d ->
                        Card(
                            modifier = Modifier.fillMaxWidth(),
                            colors = CardDefaults.cardColors(containerColor = CardDark),
                            border = BorderStroke(1.dp, CardBorder)
                        ) {
                            Column(modifier = Modifier.padding(10.dp)) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Surface(
                                        color = PrimaryPurple.copy(alpha = 0.2f),
                                        shape = RoundedCornerShape(4.dp)
                                    ) {
                                        Text("DECISION", color = PrimaryPurple, fontSize = 10.sp, fontWeight = FontWeight.Bold, modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp))
                                    }
                                    if (d.isUncertain == true) {
                                        Spacer(Modifier.width(6.dp))
                                        Surface(
                                            color = AccentWarning.copy(alpha = 0.2f),
                                            shape = RoundedCornerShape(4.dp)
                                        ) {
                                            Text("REVIEW NEEDED", color = AccentWarning, fontSize = 9.sp, fontWeight = FontWeight.Bold, modifier = Modifier.padding(horizontal = 4.dp, vertical = 2.dp))
                                        }
                                    }
                                    Spacer(modifier = Modifier.weight(1f))
                                    d.confidence?.let { conf ->
                                        Text(text = "${(conf * 100).toInt()}% confidence", color = TextMuted, fontSize = 10.sp)
                                    }
                                }
                                Spacer(modifier = Modifier.height(6.dp))
                                Text(text = d.text ?: d.description ?: "", color = TextWhite, fontSize = 13.sp)
                                if (d.sourceSegmentIds.isNotEmpty()) {
                                    Spacer(modifier = Modifier.height(4.dp))
                                    Text(text = "Source: Segment #${d.sourceSegmentIds.joinToString(", ")}", color = TextMuted, fontSize = 10.sp)
                                }
                            }
                        }
                    }
                }

                // Action Items Section
                if (actionItems.isNotEmpty()) {
                    item {
                        Text(
                            text = "ACTION ITEMS (${actionItems.size})",
                            color = AccentSuccess,
                            fontWeight = FontWeight.Bold,
                            fontSize = 12.sp,
                            modifier = Modifier.padding(top = 4.dp)
                        )
                    }
                    items(actionItems) { ai ->
                        Card(
                            modifier = Modifier.fillMaxWidth(),
                            colors = CardDefaults.cardColors(containerColor = CardDark),
                            border = BorderStroke(1.dp, CardBorder)
                        ) {
                            Column(modifier = Modifier.padding(10.dp)) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Surface(
                                        color = AccentSuccess.copy(alpha = 0.2f),
                                        shape = RoundedCornerShape(4.dp)
                                    ) {
                                        Text("ACTION ITEM", color = AccentSuccess, fontSize = 10.sp, fontWeight = FontWeight.Bold, modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp))
                                    }
                                    if (ai.isUncertain == true) {
                                        Spacer(Modifier.width(6.dp))
                                        Surface(
                                            color = AccentWarning.copy(alpha = 0.2f),
                                            shape = RoundedCornerShape(4.dp)
                                        ) {
                                            Text("REVIEW NEEDED", color = AccentWarning, fontSize = 9.sp, fontWeight = FontWeight.Bold, modifier = Modifier.padding(horizontal = 4.dp, vertical = 2.dp))
                                        }
                                    }
                                    Spacer(modifier = Modifier.weight(1f))
                                    Text("Status: ${ai.status}", color = TextMuted, fontSize = 10.sp)
                                }
                                Spacer(modifier = Modifier.height(6.dp))
                                val rawText = ai.text ?: ai.description ?: ai.title ?: ""
                                val rawAssignee = ai.assigneeName ?: ai.assignee
                                val assignee = if (rawAssignee != null && (rawAssignee.equals("alice", ignoreCase = true) || rawAssignee.equals("allies", ignoreCase = true))) {
                                    "Alice"
                                } else {
                                    rawAssignee?.replaceFirstChar { it.uppercase() }
                                }
                                var displayText = rawText
                                if (displayText.startsWith("alice will", ignoreCase = true) || displayText.startsWith("allies will", ignoreCase = true)) {
                                    displayText = "Alice" + displayText.substring(5)
                                }
                                if (assignee == "Alice") {
                                    displayText = displayText.replace(Regex("\\ballies\\b", RegexOption.IGNORE_CASE), "Alice")
                                }
                                displayText = displayText.replaceFirstChar { it.uppercase() }

                                Text(text = displayText, color = TextWhite, fontSize = 13.sp)
                                assignee?.let { a ->
                                    Spacer(modifier = Modifier.height(4.dp))
                                    Text(text = "Assignee: $a", color = TextMuted, fontSize = 11.sp)
                                }
                                if (ai.sourceSegmentIds.isNotEmpty()) {
                                    Spacer(modifier = Modifier.height(4.dp))
                                    Text(text = "Source: Segment #${ai.sourceSegmentIds.joinToString(", ")}", color = TextMuted, fontSize = 10.sp)
                                }
                            }
                        }
                    }
                }

                // Commitments Section
                if (commitments.isNotEmpty()) {
                    item {
                        Text(
                            text = "COMMITMENTS (${commitments.size})",
                            color = AccentWarning,
                            fontWeight = FontWeight.Bold,
                            fontSize = 12.sp,
                            modifier = Modifier.padding(top = 4.dp)
                        )
                    }
                    items(commitments) { c ->
                        Card(
                            modifier = Modifier.fillMaxWidth(),
                            colors = CardDefaults.cardColors(containerColor = CardDark),
                            border = BorderStroke(1.dp, CardBorder)
                        ) {
                            Column(modifier = Modifier.padding(10.dp)) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Surface(
                                        color = AccentWarning.copy(alpha = 0.2f),
                                        shape = RoundedCornerShape(4.dp)
                                    ) {
                                        Text("COMMITMENT", color = AccentWarning, fontSize = 10.sp, fontWeight = FontWeight.Bold, modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp))
                                    }
                                    if (c.isUncertain == true) {
                                        Spacer(Modifier.width(6.dp))
                                        Surface(
                                            color = AccentWarning.copy(alpha = 0.2f),
                                            shape = RoundedCornerShape(4.dp)
                                        ) {
                                            Text("REVIEW NEEDED", color = AccentWarning, fontSize = 9.sp, fontWeight = FontWeight.Bold, modifier = Modifier.padding(horizontal = 4.dp, vertical = 2.dp))
                                        }
                                    }
                                    Spacer(modifier = Modifier.weight(1f))
                                    Text("Status: ${c.status}", color = TextMuted, fontSize = 10.sp)
                                }
                                Spacer(modifier = Modifier.height(6.dp))
                                Text(text = c.text ?: c.commitmentText ?: c.title ?: "", color = TextWhite, fontSize = 13.sp)
                                c.promiserName?.let { promiser ->
                                    Spacer(modifier = Modifier.height(4.dp))
                                    Text(text = "Promised by: $promiser", color = TextMuted, fontSize = 11.sp)
                                }
                                if (c.sourceSegmentIds.isNotEmpty()) {
                                    Spacer(modifier = Modifier.height(4.dp))
                                    Text(text = "Source: Segment #${c.sourceSegmentIds.joinToString(", ")}", color = TextMuted, fontSize = 10.sp)
                                }
                            }
                        }
                    }
                }

                // Deadlines Section
                if (deadlines.isNotEmpty()) {
                    item {
                        Text(
                            text = "DEADLINES (${deadlines.size})",
                            color = AccentDanger,
                            fontWeight = FontWeight.Bold,
                            fontSize = 12.sp,
                            modifier = Modifier.padding(top = 4.dp)
                        )
                    }
                    items(deadlines) { dl ->
                        Card(
                            modifier = Modifier.fillMaxWidth(),
                            colors = CardDefaults.cardColors(containerColor = CardDark),
                            border = BorderStroke(1.dp, CardBorder)
                        ) {
                            Column(modifier = Modifier.padding(10.dp)) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Surface(
                                        color = AccentDanger.copy(alpha = 0.2f),
                                        shape = RoundedCornerShape(4.dp)
                                    ) {
                                        Text("DEADLINE", color = AccentDanger, fontSize = 10.sp, fontWeight = FontWeight.Bold, modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp))
                                    }
                                    if (dl.isUncertain == true) {
                                        Spacer(Modifier.width(6.dp))
                                        Surface(
                                            color = AccentWarning.copy(alpha = 0.2f),
                                            shape = RoundedCornerShape(4.dp)
                                        ) {
                                            Text("REVIEW NEEDED", color = AccentWarning, fontSize = 9.sp, fontWeight = FontWeight.Bold, modifier = Modifier.padding(horizontal = 4.dp, vertical = 2.dp))
                                        }
                                    }
                                    Spacer(modifier = Modifier.weight(1f))
                                    dl.rawDeadlineText?.let { raw ->
                                        Text(text = raw, color = AccentDanger, fontSize = 10.sp, fontWeight = FontWeight.SemiBold)
                                    }
                                }
                                Spacer(modifier = Modifier.height(6.dp))
                                Text(text = dl.title ?: dl.description ?: dl.rawDeadlineText ?: "", color = TextWhite, fontSize = 13.sp)
                                dl.dueDate?.let { due ->
                                    Spacer(modifier = Modifier.height(4.dp))
                                    Text(text = "Due: $due", color = TextMuted, fontSize = 11.sp)
                                }
                                if (dl.sourceSegmentIds.isNotEmpty()) {
                                    Spacer(modifier = Modifier.height(4.dp))
                                    Text(text = "Source: Segment #${dl.sourceSegmentIds.joinToString(", ")}", color = TextMuted, fontSize = 10.sp)
                                }
                            }
                        }
                    }
                }

                // Questions Section
                if (questions.isNotEmpty()) {
                    item {
                        Text(
                            text = "QUESTIONS (${questions.size})",
                            color = PrimaryPurple,
                            fontWeight = FontWeight.Bold,
                            fontSize = 12.sp,
                            modifier = Modifier.padding(top = 4.dp)
                        )
                    }
                    items(questions) { q ->
                        Card(
                            modifier = Modifier.fillMaxWidth(),
                            colors = CardDefaults.cardColors(containerColor = CardDark),
                            border = BorderStroke(1.dp, CardBorder)
                        ) {
                            Column(modifier = Modifier.padding(10.dp)) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Surface(
                                        color = PrimaryPurple.copy(alpha = 0.2f),
                                        shape = RoundedCornerShape(4.dp)
                                    ) {
                                        Text("QUESTION", color = PrimaryPurple, fontSize = 10.sp, fontWeight = FontWeight.Bold, modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp))
                                    }
                                    if (q.isUncertain == true) {
                                        Spacer(Modifier.width(6.dp))
                                        Surface(
                                            color = AccentWarning.copy(alpha = 0.2f),
                                            shape = RoundedCornerShape(4.dp)
                                        ) {
                                            Text("REVIEW NEEDED", color = AccentWarning, fontSize = 9.sp, fontWeight = FontWeight.Bold, modifier = Modifier.padding(horizontal = 4.dp, vertical = 2.dp))
                                        }
                                    }
                                    Spacer(modifier = Modifier.weight(1f))
                                    Text("Status: ${q.status ?: "unanswered"}", color = TextMuted, fontSize = 10.sp)
                                }
                                Spacer(modifier = Modifier.height(6.dp))
                                Text(text = q.questionText ?: q.question ?: "", color = TextWhite, fontSize = 13.sp)
                                q.askerName?.let { asker ->
                                    Spacer(modifier = Modifier.height(4.dp))
                                    Text(text = "Asked by: $asker", color = TextMuted, fontSize = 11.sp)
                                }
                                if (q.sourceSegmentIds.isNotEmpty()) {
                                    Spacer(modifier = Modifier.height(4.dp))
                                    Text(text = "Source: Segment #${q.sourceSegmentIds.joinToString(", ")}", color = TextMuted, fontSize = 10.sp)
                                }
                            }
                        }
                    }
                }

                // Topics Section
                if (topics.isNotEmpty()) {
                    item {
                        Text(
                            text = "TOPICS (${topics.size})",
                            color = SecondarySlate,
                            fontWeight = FontWeight.Bold,
                            fontSize = 12.sp,
                            modifier = Modifier.padding(top = 4.dp)
                        )
                    }
                    item {
                        LazyRow(
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            items(topics) { top ->
                                Surface(
                                    color = CardDark,
                                    border = BorderStroke(1.dp, CardBorder),
                                    shape = RoundedCornerShape(16.dp)
                                ) {
                                    Text(
                                        text = "#${top.name}",
                                        color = TextWhite,
                                        fontSize = 12.sp,
                                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp)
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // Speaker Relabel Dialog
    if (showRelabelDialog) {
        AlertDialog(
            onDismissRequest = { showRelabelDialog = false },
            title = { Text("Rename Speaker", color = TextWhite, fontWeight = FontWeight.Bold) },
            text = {
                Column {
                    Text("Enter a name for $relabelSpeakerCurrentName:", color = TextMuted, fontSize = 13.sp)
                    Spacer(Modifier.height(10.dp))
                    OutlinedTextField(
                        value = relabelSpeakerNewName,
                        onValueChange = { relabelSpeakerNewName = it },
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true
                    )
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        val targetRecId = detail?.recordingId ?: conversationId
                        val spkId = relabelSpeakerId ?: 0
                        viewModel.relabelSpeaker(targetRecId, spkId, relabelSpeakerNewName.trim(), null)
                        showRelabelDialog = false
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = PrimaryPurple)
                ) {
                    Text("Save")
                }
            },
            dismissButton = {
                TextButton(onClick = { showRelabelDialog = false }) {
                    Text("Cancel", color = TextMuted)
                }
            },
            containerColor = CardDark
        )
    }

    // Segment Correction Dialog
    if (showEditSegmentDialog) {
        val isCorrecting by viewModel.isCorrectingSegment.collectAsState()
        val correctionErr by viewModel.correctionError.collectAsState()

        AlertDialog(
            onDismissRequest = { if (!isCorrecting) showEditSegmentDialog = false },
            title = {
                Text(
                    "Edit Transcript",
                    color = TextWhite,
                    fontWeight = FontWeight.Bold,
                    fontSize = 18.sp
                )
            },
            text = {
                Column {
                    Text(
                        "Original Text:",
                        color = TextMuted,
                        fontSize = 11.sp,
                        fontWeight = FontWeight.SemiBold
                    )
                    Spacer(Modifier.height(4.dp))
                    Surface(
                        color = BackgroundDark,
                        shape = RoundedCornerShape(6.dp),
                        border = BorderStroke(1.dp, CardBorder),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text(
                            text = editSegmentOriginalText,
                            color = TextMuted,
                            fontSize = 12.sp,
                            modifier = Modifier.padding(8.dp)
                        )
                    }

                    Spacer(Modifier.height(12.dp))
                    Text(
                        "Corrected Text:",
                        color = TextWhite,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.SemiBold
                    )
                    Spacer(Modifier.height(4.dp))
                    OutlinedTextField(
                        value = editSegmentNewText,
                        onValueChange = { editSegmentNewText = it },
                        modifier = Modifier.fillMaxWidth(),
                        maxLines = 4,
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = PrimaryPurple,
                            unfocusedBorderColor = CardBorder,
                            focusedTextColor = TextWhite,
                            unfocusedTextColor = TextWhite
                        )
                    )

                    Spacer(Modifier.height(12.dp))
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable { editSegmentReExtract = !editSegmentReExtract }
                            .padding(vertical = 4.dp)
                    ) {
                        Checkbox(
                            checked = editSegmentReExtract,
                            onCheckedChange = { editSegmentReExtract = it },
                            colors = CheckboxDefaults.colors(checkedColor = PrimaryPurple)
                        )
                        Spacer(Modifier.width(6.dp))
                        Column {
                            Text(
                                "Update action items & draft meeting notes",
                                color = TextWhite,
                                fontSize = 12.sp,
                                fontWeight = FontWeight.SemiBold
                            )
                            Text(
                                "Re-analyzes the conversation and updates meeting notes in place",
                                color = TextMuted,
                                fontSize = 10.sp
                            )
                        }
                    }

                    if (correctionErr != null) {
                        Spacer(Modifier.height(8.dp))
                        Text(
                            text = correctionErr ?: "",
                            color = AccentDanger,
                            fontSize = 12.sp
                        )
                    }
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        val targetRecId = detail?.recordingId ?: transcript?.recordingId ?: conversationId
                        val segId = editSegmentId ?: return@Button
                        viewModel.correctSegment(
                            recordingId = targetRecId,
                            segmentId = segId,
                            newText = editSegmentNewText.trim(),
                            reExtract = editSegmentReExtract
                        ) { success ->
                            if (success) {
                                showEditSegmentDialog = false
                                if (editSegmentReExtract) {
                                    onRefreshMom?.invoke(conversationId)
                                }
                            }
                        }
                    },
                    enabled = !isCorrecting && editSegmentNewText.isNotBlank(),
                    colors = ButtonDefaults.buttonColors(containerColor = PrimaryPurple)
                ) {
                    if (isCorrecting) {
                        CircularProgressIndicator(
                            color = Color.White,
                            modifier = Modifier.size(16.dp),
                            strokeWidth = 2.dp
                        )
                    } else {
                        Text("Save")
                    }
                }
            },
            dismissButton = {
                TextButton(
                    onClick = { showEditSegmentDialog = false },
                    enabled = !isCorrecting
                ) {
                    Text("Cancel", color = TextMuted)
                }
            },
            containerColor = CardDark
        )
    }
}

// ==========================================
// 6. MOM SCREEN
// ==========================================
@Composable
fun MomScreen(
    viewModel: MomViewModel,
    onSelectOtherConversation: (() -> Unit)? = null
) {
    val selectedId by viewModel.selectedConversationId.collectAsState()
    val mom by viewModel.currentMom.collectAsState()
    val isLoading by viewModel.isLoading.collectAsState()
    val errorMessage by viewModel.errorMessage.collectAsState()
    val momNotFound by viewModel.momNotFound.collectAsState()

    LaunchedEffect(selectedId) {
        if (selectedId != null) {
            viewModel.loadMom(selectedId!!)
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(BackgroundDark)
            .padding(16.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text("Minutes of Meeting", style = MaterialTheme.typography.titleLarge, color = TextWhite, fontWeight = FontWeight.Bold)
                if (selectedId != null) {
                    Text("Conversation #$selectedId", style = MaterialTheme.typography.bodySmall, color = PrimaryPurple)
                }
            }
            if (selectedId != null) {
                IconButton(
                    onClick = { viewModel.loadMom(selectedId!!) },
                    modifier = Modifier.size(32.dp)
                ) {
                    Icon(
                        Icons.Default.Refresh,
                        contentDescription = "Refresh Notes",
                        tint = PrimaryPurple,
                        modifier = Modifier.size(20.dp)
                    )
                }
                Spacer(modifier = Modifier.width(6.dp))
            }
            if (selectedId != null && onSelectOtherConversation != null) {
                OutlinedButton(
                    onClick = onSelectOtherConversation,
                    contentPadding = PaddingValues(horizontal = 10.dp, vertical = 4.dp),
                    shape = RoundedCornerShape(6.dp)
                ) {
                    Text("Switch", color = PrimaryPurple, fontSize = 12.sp)
                }
            }
        }

        Spacer(modifier = Modifier.height(12.dp))

        when {
            selectedId == null -> {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.padding(24.dp)) {
                        Icon(Icons.Default.Description, contentDescription = null, tint = TextMuted, modifier = Modifier.size(56.dp))
                        Spacer(modifier = Modifier.height(12.dp))
                        Text("No conversation selected.", color = TextWhite, fontWeight = FontWeight.Medium, fontSize = 16.sp)
                        Spacer(modifier = Modifier.height(4.dp))
                        Text("Select a conversation from the Library to view or generate its meeting notes.", color = TextMuted, fontSize = 13.sp, textAlign = TextAlign.Center)
                        if (onSelectOtherConversation != null) {
                            Spacer(modifier = Modifier.height(16.dp))
                            Button(onClick = onSelectOtherConversation, colors = ButtonDefaults.buttonColors(containerColor = PrimaryPurple)) {
                                Text("Select from Library")
                            }
                        }
                    }
                }
            }

            isLoading -> {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        CircularProgressIndicator(color = PrimaryPurple)
                        Spacer(modifier = Modifier.height(12.dp))
                        Text("Preparing meeting notes...", color = TextMuted, fontSize = 13.sp)
                    }
                }
            }

            errorMessage != null -> {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = CardDark),
                    border = BorderStroke(1.dp, AccentDanger)
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.Default.Warning, contentDescription = null, tint = AccentDanger, modifier = Modifier.size(20.dp))
                            Spacer(modifier = Modifier.width(8.dp))
                            Text("Unable to Load Meeting Notes", color = AccentDanger, fontWeight = FontWeight.Bold)
                        }
                        Spacer(modifier = Modifier.height(8.dp))
                        Text(errorMessage ?: "An unexpected error occurred", color = TextWhite, fontSize = 13.sp)
                        Spacer(modifier = Modifier.height(12.dp))
                        Row {
                            Button(onClick = { viewModel.loadMom(selectedId!!) }, colors = ButtonDefaults.buttonColors(containerColor = PrimaryPurple)) {
                                Text("Retry")
                            }
                            if (onSelectOtherConversation != null) {
                                Spacer(modifier = Modifier.width(8.dp))
                                OutlinedButton(onClick = onSelectOtherConversation) {
                                    Text("Switch Conversation", color = TextMuted)
                                }
                            }
                        }
                    }
                }
            }

            mom == null && momNotFound -> {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = CardDark),
                    border = BorderStroke(1.dp, CardBorder)
                ) {
                    Column(
                        modifier = Modifier.padding(24.dp),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        Icon(Icons.Default.Description, contentDescription = null, tint = PrimaryPurple, modifier = Modifier.size(48.dp))
                        Spacer(modifier = Modifier.height(12.dp))
                        Text("No Meeting Notes Yet", color = TextWhite, fontWeight = FontWeight.Bold, fontSize = 16.sp)
                        Spacer(modifier = Modifier.height(6.dp))
                        Text(
                            "Generate structured meeting notes with action items, decisions, and deadlines.",
                            color = TextMuted,
                            fontSize = 13.sp,
                            textAlign = TextAlign.Center
                        )
                        Spacer(modifier = Modifier.height(16.dp))
                        Button(
                            onClick = { viewModel.generateMom(selectedId!!) },
                            modifier = Modifier.fillMaxWidth(),
                            colors = ButtonDefaults.buttonColors(containerColor = PrimaryPurple)
                        ) {
                            Icon(Icons.Default.SmartToy, contentDescription = null, modifier = Modifier.size(18.dp))
                            Spacer(modifier = Modifier.width(8.dp))
                            Text("Generate Meeting Notes")
                        }
                    }
                }
            }

            mom != null -> {
                val m = mom!!
                var showApproveConfirmDialog by remember { mutableStateOf(false) }

                if (showApproveConfirmDialog) {
                    val requiresReview = m.isUncertain == true
                    AlertDialog(
                        onDismissRequest = { showApproveConfirmDialog = false },
                        title = {
                            Text(
                                if (requiresReview) "Review Verification Required" else "Confirm Approval",
                                fontWeight = FontWeight.Bold,
                                color = TextWhite
                            )
                        },
                        text = {
                            Text(
                                if (requiresReview) {
                                    "These meeting notes contain uncertain or unconfirmed statements extracted from audio. By approving, you confirm that you have reviewed and verified the accuracy of these notes against the transcript."
                                } else {
                                    "Are you sure you want to approve these meeting notes? Once approved, the notes will be marked as official and finalized."
                                },
                                color = TextWhite,
                                fontSize = 13.sp
                            )
                        },
                        confirmButton = {
                            Button(
                                onClick = {
                                    showApproveConfirmDialog = false
                                    viewModel.approveMom(m.id, confirmedReview = true)
                                },
                                colors = ButtonDefaults.buttonColors(containerColor = AccentSuccess)
                            ) {
                                Text(if (requiresReview) "Verify & Approve" else "Approve")
                            }
                        },
                        dismissButton = {
                            OutlinedButton(onClick = { showApproveConfirmDialog = false }) {
                                Text("Cancel", color = TextMuted)
                            }
                        },
                        containerColor = CardDark,
                        shape = RoundedCornerShape(12.dp)
                    )
                }

                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(bottom = 88.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    item {
                        Card(
                            modifier = Modifier.fillMaxWidth(),
                            colors = CardDefaults.cardColors(containerColor = CardDark),
                            border = BorderStroke(1.dp, CardBorder)
                        ) {
                            Column(modifier = Modifier.padding(12.dp)) {
                                Text(m.title, fontWeight = FontWeight.Bold, color = TextWhite, fontSize = 16.sp)
                                Spacer(modifier = Modifier.height(6.dp))
                                val isApproved = m.status.lowercase() == "approved"
                                val statusBg = if (isApproved) AccentSuccess else (if (m.isUncertain == true) AccentWarning else PrimaryPurple)
                                val statusText = when {
                                    isApproved -> "Status: Approved"
                                    m.isUncertain == true -> "Status: Draft • Review Required"
                                    else -> "Status: Draft"
                                }
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Surface(
                                        color = statusBg.copy(alpha = 0.15f),
                                        shape = RoundedCornerShape(4.dp)
                                    ) {
                                        Text(
                                            statusText,
                                            color = statusBg,
                                            fontSize = 10.sp,
                                            fontWeight = FontWeight.Bold,
                                            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                                        )
                                    }
                                    if (m.confidence != null) {
                                        Spacer(Modifier.width(8.dp))
                                        Text(
                                            "${(m.confidence * 100).toInt()}% confidence",
                                            color = TextMuted,
                                            fontSize = 11.sp
                                        )
                                    }
                                }
                                Spacer(modifier = Modifier.height(10.dp))
                                Text("Executive Summary", color = PrimaryPurple, fontWeight = FontWeight.Bold, fontSize = 12.sp)
                                Spacer(modifier = Modifier.height(4.dp))
                                Text(m.summary, color = TextWhite, fontSize = 13.sp)

                                if (!isApproved) {
                                    Spacer(modifier = Modifier.height(12.dp))
                                    Button(
                                        onClick = { showApproveConfirmDialog = true },
                                        colors = ButtonDefaults.buttonColors(containerColor = AccentSuccess),
                                        shape = RoundedCornerShape(6.dp),
                                        contentPadding = PaddingValues(horizontal = 14.dp, vertical = 6.dp)
                                    ) {
                                        Icon(Icons.Default.CheckCircle, contentDescription = null, modifier = Modifier.size(15.dp))
                                        Spacer(modifier = Modifier.width(6.dp))
                                        Text(if (m.isUncertain == true) "Review & Approve Notes" else "Approve Notes", fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
                                    }
                                }
                            }
                        }
                    }

                    if (m.sections.isNotEmpty()) {
                        items(m.sections) { sec ->
                            Card(
                                modifier = Modifier.fillMaxWidth(),
                                colors = CardDefaults.cardColors(containerColor = CardDark),
                                border = BorderStroke(1.dp, CardBorder)
                            ) {
                                Column(modifier = Modifier.padding(12.dp)) {
                                    Text(
                                        sec.title ?: sec.heading ?: sec.sectionType ?: "Section",
                                        color = PrimaryPurple,
                                        fontWeight = FontWeight.Bold,
                                        fontSize = 13.sp
                                    )
                                    Spacer(modifier = Modifier.height(6.dp))
                                    val textContent = sec.content ?: formatMomSectionJson(sec.contentJson)
                                    Text(
                                        text = textContent,
                                        color = TextWhite,
                                        fontSize = 13.sp
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

fun formatMomSectionJson(rawJson: String?): String {
    if (rawJson.isNullOrBlank() || rawJson.trim() == "[]") return "None"
    return try {
        val array = JsonParser.parseString(rawJson).asJsonArray
        if (array.isEmpty) return "None"
        val lines = mutableListOf<String>()
        for (elem in array) {
            if (elem.isJsonObject) {
                val obj = elem.asJsonObject
                val rawText = obj.get("text")?.takeIf { !it.isJsonNull }?.asString
                    ?: obj.get("title")?.takeIf { !it.isJsonNull }?.asString
                    ?: obj.get("question_text")?.takeIf { !it.isJsonNull }?.asString
                    ?: obj.get("raw_deadline_text")?.takeIf { !it.isJsonNull }?.asString
                val rawAssignee = obj.get("assignee_name")?.takeIf { !it.isJsonNull }?.asString
                val assignee = if (rawAssignee != null && (rawAssignee.equals("alice", ignoreCase = true) || rawAssignee.equals("allies", ignoreCase = true))) {
                    "Alice"
                } else {
                    rawAssignee?.replaceFirstChar { it.uppercase() }
                }
                val text = if (rawText != null) {
                    var t = rawText
                    if (t.startsWith("alice will", ignoreCase = true) || t.startsWith("allies will", ignoreCase = true)) {
                        t = "Alice" + t.substring(5)
                    }
                    if (assignee == "Alice") {
                        t = t.replace(Regex("\\ballies\\b", RegexOption.IGNORE_CASE), "Alice")
                    }
                    t.replaceFirstChar { it.uppercase() }
                } else null
                val promiser = obj.get("promiser_name")?.takeIf { !it.isJsonNull }?.asString
                val status = obj.get("status")?.takeIf { !it.isJsonNull }?.asString
                val dueDate = obj.get("due_date")?.takeIf { !it.isJsonNull }?.asString
                val isUncertain = obj.get("is_uncertain")?.takeIf { !it.isJsonNull }?.asBoolean ?: false
                val sourceSegIds = obj.get("source_segment_ids")?.takeIf { !it.isJsonNull && it.isJsonArray }?.asJsonArray

                val prefix = if (isUncertain) "• [REVIEW] " else "• "
                val parts = mutableListOf<String>()
                if (!text.isNullOrBlank()) parts.add(text)
                if (!assignee.isNullOrBlank()) parts.add("Assignee: $assignee")
                if (!promiser.isNullOrBlank()) parts.add("Promised by: $promiser")
                if (!dueDate.isNullOrBlank()) parts.add("Due: $dueDate")
                if (!status.isNullOrBlank() && status != "open" && status != "unanswered") parts.add("[$status]")
                if (sourceSegIds != null && !sourceSegIds.isEmpty) {
                    val ids = sourceSegIds.map { it.asInt }.joinToString(", ")
                    parts.add("(Segment #$ids)")
                }

                lines.add(prefix + parts.joinToString(" — "))
            } else {
                lines.add("• ${elem.asString}")
            }
        }
        if (lines.isEmpty()) "None" else lines.joinToString("\n")
    } catch (_: Exception) {
        rawJson
    }
}

// ==========================================
// 7. SEARCH & MEMORY SCREEN
// ==========================================
@Composable
fun SearchMemoryScreen(viewModel: SearchViewModel, onSelectConversation: (Int) -> Unit) {
    var query by remember { mutableStateOf("") }
    val results by viewModel.searchResults.collectAsState()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(BackgroundDark)
            .padding(16.dp)
    ) {
        Text("Search Conversations", style = MaterialTheme.typography.titleLarge, color = TextWhite, fontWeight = FontWeight.Bold)
        Text("Search across meetings, key decisions, topics, and people", style = MaterialTheme.typography.bodySmall, color = TextMuted)

        Spacer(modifier = Modifier.height(14.dp))

        OutlinedTextField(
            value = query,
            onValueChange = {
                query = it
                viewModel.executeSearch(it)
            },
            placeholder = { Text("Search meetings, facts, or topics...", color = TextMuted) },
            modifier = Modifier.fillMaxWidth(),
            trailingIcon = {
                if (query.isNotEmpty()) {
                    IconButton(onClick = { query = ""; viewModel.executeSearch("") }) {
                        Icon(Icons.Default.Close, contentDescription = "Clear", tint = TextMuted)
                    }
                } else {
                    Icon(Icons.Default.Search, contentDescription = null, tint = PrimaryPurple)
                }
            },
            colors = OutlinedTextFieldDefaults.colors(
                focusedBorderColor = PrimaryPurple,
                unfocusedBorderColor = CardBorder,
                focusedTextColor = TextWhite,
                unfocusedTextColor = TextWhite
            ),
            shape = RoundedCornerShape(8.dp)
        )

        Spacer(modifier = Modifier.height(14.dp))

        if (results.isEmpty() && query.isNotEmpty()) {
            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text("No matching conversations found.", color = TextMuted)
            }
        } else if (results.isEmpty() && query.isEmpty()) {
            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.padding(24.dp)) {
                    Icon(Icons.Default.Search, contentDescription = null, tint = TextMuted, modifier = Modifier.size(48.dp))
                    Spacer(Modifier.height(12.dp))
                    Text("Search Conversations", color = TextWhite, fontWeight = FontWeight.Medium, fontSize = 15.sp)
                    Spacer(Modifier.height(4.dp))
                    Text("Type a keyword, person name, or topic above to find relevant discussions.", color = TextMuted, fontSize = 13.sp, textAlign = TextAlign.Center)
                }
            }
        } else {
            LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                items(results) { item ->
                    Card(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable { onSelectConversation(item.id) },
                        colors = CardDefaults.cardColors(containerColor = CardDark),
                        border = BorderStroke(1.dp, CardBorder)
                    ) {
                        Column(modifier = Modifier.padding(14.dp)) {
                            Text("Conversation #${item.id}", color = TextWhite, fontWeight = FontWeight.Bold)
                            item.snippet?.let {
                                Spacer(modifier = Modifier.height(4.dp))
                                Text(it, color = TextMuted, fontSize = 13.sp)
                            }
                        }
                    }
                }
            }
        }
    }
}

// ==========================================
// 8. MORE SCREEN (HUB)
// ==========================================
@Composable
fun MoreScreen(
    mainViewModel: MainViewModel,
    onNavigateAssistant: () -> Unit,
    onNavigateCommitments: () -> Unit,
    onNavigateEntities: () -> Unit,
    onNavigateSettings: () -> Unit
) {
    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .background(BackgroundDark)
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        item {
            Column {
                Text("Tools & Features", style = MaterialTheme.typography.titleLarge, color = TextWhite, fontWeight = FontWeight.Bold)
                Text("Access Meeting Assistant, Tasks, People & Projects, and Settings", style = MaterialTheme.typography.bodySmall, color = TextMuted)
            }
        }

        // Assistant Card
        item {
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { onNavigateAssistant() },
                colors = CardDefaults.cardColors(containerColor = CardDark),
                border = BorderStroke(1.dp, CardBorder)
            ) {
                Row(
                    modifier = Modifier.padding(16.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Surface(
                        color = PrimaryPurple.copy(alpha = 0.15f),
                        shape = CircleShape,
                        modifier = Modifier.size(44.dp)
                    ) {
                        Box(contentAlignment = Alignment.Center) {
                            Icon(Icons.Default.SmartToy, contentDescription = null, tint = PrimaryPurple)
                        }
                    }
                    Spacer(Modifier.width(16.dp))
                    Column(modifier = Modifier.weight(1f)) {
                        Text("Meeting Assistant", color = TextWhite, fontWeight = FontWeight.Bold, fontSize = 15.sp)
                        Text("Ask questions across meeting transcripts with citations", color = TextMuted, fontSize = 12.sp)
                    }
                    Icon(Icons.Default.ChevronRight, contentDescription = null, tint = TextMuted)
                }
            }
        }

        // Commitments Card
        item {
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { onNavigateCommitments() },
                colors = CardDefaults.cardColors(containerColor = CardDark),
                border = BorderStroke(1.dp, CardBorder)
            ) {
                Row(
                    modifier = Modifier.padding(16.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Surface(
                        color = AccentSuccess.copy(alpha = 0.15f),
                        shape = CircleShape,
                        modifier = Modifier.size(44.dp)
                    ) {
                        Box(contentAlignment = Alignment.Center) {
                            Icon(Icons.Default.CheckCircle, contentDescription = null, tint = AccentSuccess)
                        }
                    }
                    Spacer(Modifier.width(16.dp))
                    Column(modifier = Modifier.weight(1f)) {
                        Text("Tasks & Commitments", color = TextWhite, fontWeight = FontWeight.Bold, fontSize = 15.sp)
                        Text("Action items, commitments, and deadlines", color = TextMuted, fontSize = 12.sp)
                    }
                    Icon(Icons.Default.ChevronRight, contentDescription = null, tint = TextMuted)
                }
            }
        }

        // Entities Card
        item {
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { onNavigateEntities() },
                colors = CardDefaults.cardColors(containerColor = CardDark),
                border = BorderStroke(1.dp, CardBorder)
            ) {
                Row(
                    modifier = Modifier.padding(16.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Surface(
                        color = AccentWarning.copy(alpha = 0.15f),
                        shape = CircleShape,
                        modifier = Modifier.size(44.dp)
                    ) {
                        Box(contentAlignment = Alignment.Center) {
                            Icon(Icons.Default.People, contentDescription = null, tint = AccentWarning)
                        }
                    }
                    Spacer(Modifier.width(16.dp))
                    Column(modifier = Modifier.weight(1f)) {
                        Text("People & Projects", color = TextWhite, fontWeight = FontWeight.Bold, fontSize = 15.sp)
                        Text("People, organizations, projects, and topics", color = TextMuted, fontSize = 12.sp)
                    }
                    Icon(Icons.Default.ChevronRight, contentDescription = null, tint = TextMuted)
                }
            }
        }

        // Settings Card
        item {
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { onNavigateSettings() },
                colors = CardDefaults.cardColors(containerColor = CardDark),
                border = BorderStroke(1.dp, CardBorder)
            ) {
                Row(
                    modifier = Modifier.padding(16.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Surface(
                        color = SecondarySlate.copy(alpha = 0.3f),
                        shape = CircleShape,
                        modifier = Modifier.size(44.dp)
                    ) {
                        Box(contentAlignment = Alignment.Center) {
                            Icon(Icons.Default.Settings, contentDescription = null, tint = TextWhite)
                        }
                    }
                    Spacer(Modifier.width(16.dp))
                    Column(modifier = Modifier.weight(1f)) {
                        Text("Settings & Privacy", color = TextWhite, fontWeight = FontWeight.Bold, fontSize = 15.sp)
                        Text("Recording consent, storage management, and account", color = TextMuted, fontSize = 12.sp)
                    }
                    Icon(Icons.Default.ChevronRight, contentDescription = null, tint = TextMuted)
                }
            }
        }

        // System Diagnostic Info Card
        item {
            Spacer(modifier = Modifier.height(8.dp))
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = CardDark),
                border = BorderStroke(1.dp, CardBorder)
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text("About & Connection", color = TextWhite, fontWeight = FontWeight.Bold, fontSize = 13.sp)
                    Spacer(Modifier.height(8.dp))
                    Row {
                        Text("Server Connection: ", color = TextMuted, fontSize = 12.sp)
                        Text(com.pcma.app.BuildConfig.DEFAULT_API_BASE_URL, color = TextWhite, fontSize = 12.sp)
                    }
                    Spacer(Modifier.height(4.dp))
                    Row {
                        Text("Voice Engine: ", color = TextMuted, fontSize = 12.sp)
                        Text("On-Device Voice Processing", color = TextWhite, fontSize = 12.sp)
                    }
                    Spacer(Modifier.height(4.dp))
                    Row {
                        Text("Data Protection: ", color = TextMuted, fontSize = 12.sp)
                        Text("Secure On-Device Encryption", color = AccentSuccess, fontSize = 12.sp)
                    }
                }
            }
        }
    }
}

// ==========================================
// 9. ENTITIES SCREEN (PEOPLE / PROJECTS / TOPICS)
// ==========================================
@Composable
fun EntitiesScreen(
    viewModel: EntitiesViewModel,
    onNavigateChats: () -> Unit = {}
) {
    val people by viewModel.people.collectAsState()
    val projects by viewModel.projects.collectAsState()
    val topics by viewModel.topics.collectAsState()
    var selectedEntityTab by remember { mutableStateOf(0) }
    var searchQuery by remember { mutableStateOf("") }

    LaunchedEffect(Unit) { viewModel.loadEntities() }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(BackgroundDark)
            .padding(16.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text("People & Projects", style = MaterialTheme.typography.titleLarge, color = TextWhite, fontWeight = FontWeight.Bold)
                Text("People, projects, and topics identified across conversations", style = MaterialTheme.typography.bodySmall, color = TextMuted)
            }
            IconButton(onClick = { viewModel.loadEntities() }) {
                Icon(Icons.Default.Refresh, contentDescription = "Refresh", tint = PrimaryPurple)
            }
        }

        Spacer(modifier = Modifier.height(12.dp))

        // Search Filter Field
        OutlinedTextField(
            value = searchQuery,
            onValueChange = { searchQuery = it },
            placeholder = { Text("Search people, projects, topics...", color = TextMuted) },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            trailingIcon = {
                if (searchQuery.isNotEmpty()) {
                    IconButton(onClick = { searchQuery = "" }) {
                        Icon(Icons.Default.Close, contentDescription = "Clear", tint = TextMuted)
                    }
                } else {
                    Icon(Icons.Default.Search, contentDescription = null, tint = PrimaryPurple)
                }
            },
            colors = OutlinedTextFieldDefaults.colors(
                focusedBorderColor = PrimaryPurple,
                unfocusedBorderColor = CardBorder,
                focusedTextColor = TextWhite,
                unfocusedTextColor = TextWhite
            ),
            shape = RoundedCornerShape(8.dp)
        )

        Spacer(modifier = Modifier.height(12.dp))

        // Tab Selector for People, Projects, Topics
        TabRow(
            selectedTabIndex = selectedEntityTab,
            containerColor = CardDark,
            contentColor = PrimaryPurple
        ) {
            Tab(
                selected = selectedEntityTab == 0,
                onClick = { selectedEntityTab = 0 },
                text = { Text("People (${people.size})", fontWeight = FontWeight.SemiBold) }
            )
            Tab(
                selected = selectedEntityTab == 1,
                onClick = { selectedEntityTab = 1 },
                text = { Text("Projects (${projects.size})", fontWeight = FontWeight.SemiBold) }
            )
            Tab(
                selected = selectedEntityTab == 2,
                onClick = { selectedEntityTab = 2 },
                text = { Text("Topics (${topics.size})", fontWeight = FontWeight.SemiBold) }
            )
        }

        Spacer(modifier = Modifier.height(12.dp))

        when (selectedEntityTab) {
            0 -> {
                // People Directory
                val filteredPeople = people.filter {
                    searchQuery.isBlank() || it.name.contains(searchQuery, ignoreCase = true) ||
                            (it.organization?.contains(searchQuery, ignoreCase = true) == true)
                }
                if (filteredPeople.isEmpty()) {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.padding(24.dp)) {
                            Icon(Icons.Default.People, contentDescription = null, tint = TextMuted, modifier = Modifier.size(56.dp))
                            Spacer(Modifier.height(12.dp))
                            Text("No People Listed Yet", color = TextWhite, fontWeight = FontWeight.Bold, fontSize = 16.sp)
                            Spacer(Modifier.height(6.dp))
                            Text(
                                "People are automatically identified as conversations are processed, or when you rename speakers in conversation details.",
                                color = TextMuted,
                                fontSize = 13.sp,
                                textAlign = TextAlign.Center
                            )
                            Spacer(Modifier.height(16.dp))
                            Button(
                                onClick = onNavigateChats,
                                colors = ButtonDefaults.buttonColors(containerColor = PrimaryPurple)
                            ) {
                                Text("View Conversations")
                            }
                        }
                    }
                } else {
                    LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        items(filteredPeople) { p ->
                            Card(
                                modifier = Modifier.fillMaxWidth(),
                                colors = CardDefaults.cardColors(containerColor = CardDark),
                                border = BorderStroke(1.dp, CardBorder)
                            ) {
                                Row(
                                    modifier = Modifier.padding(14.dp),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Surface(
                                        color = PrimaryPurple.copy(alpha = 0.2f),
                                        shape = CircleShape,
                                        modifier = Modifier.size(40.dp)
                                    ) {
                                        Box(contentAlignment = Alignment.Center) {
                                            Text(
                                                p.name.take(2).uppercase(),
                                                color = PrimaryPurple,
                                                fontWeight = FontWeight.Bold,
                                                fontSize = 14.sp
                                            )
                                        }
                                    }
                                    Spacer(Modifier.width(12.dp))
                                    Column {
                                        Text(p.name, color = TextWhite, fontWeight = FontWeight.Bold, fontSize = 15.sp)
                                        p.organization?.let {
                                            Text("Organization: $it", color = TextMuted, fontSize = 12.sp)
                                        }
                                        p.title?.let {
                                            Text("Title: $it", color = TextMuted, fontSize = 11.sp)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            1 -> {
                // Projects Directory
                val filteredProjects = projects.filter {
                    searchQuery.isBlank() || it.name.contains(searchQuery, ignoreCase = true) ||
                            (it.description?.contains(searchQuery, ignoreCase = true) == true)
                }
                if (filteredProjects.isEmpty()) {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.padding(24.dp)) {
                            Icon(Icons.Default.Folder, contentDescription = null, tint = TextMuted, modifier = Modifier.size(56.dp))
                            Spacer(Modifier.height(12.dp))
                            Text("No Projects Listed Yet", color = TextWhite, fontWeight = FontWeight.Bold, fontSize = 16.sp)
                            Spacer(Modifier.height(6.dp))
                            Text(
                                "Projects discussed across your meetings will be grouped here automatically as conversations are analyzed.",
                                color = TextMuted,
                                fontSize = 13.sp,
                                textAlign = TextAlign.Center
                            )
                        }
                    }
                } else {
                    LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        items(filteredProjects) { pr ->
                            Card(
                                modifier = Modifier.fillMaxWidth(),
                                colors = CardDefaults.cardColors(containerColor = CardDark),
                                border = BorderStroke(1.dp, CardBorder)
                            ) {
                                Column(modifier = Modifier.padding(14.dp)) {
                                    Text(pr.name, color = TextWhite, fontWeight = FontWeight.Bold, fontSize = 15.sp)
                                    pr.description?.let {
                                        Spacer(Modifier.height(4.dp))
                                        Text(it, color = TextMuted, fontSize = 12.sp)
                                    }
                                }
                            }
                        }
                    }
                }
            }

            2 -> {
                // Topics Directory
                val filteredTopics = topics.filter {
                    searchQuery.isBlank() || it.name.contains(searchQuery, ignoreCase = true)
                }
                if (filteredTopics.isEmpty()) {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.padding(24.dp)) {
                            Icon(Icons.Default.Tag, contentDescription = null, tint = TextMuted, modifier = Modifier.size(56.dp))
                            Spacer(Modifier.height(12.dp))
                            Text("No Topics Listed Yet", color = TextWhite, fontWeight = FontWeight.Bold, fontSize = 16.sp)
                            Spacer(Modifier.height(6.dp))
                            Text(
                                "Topics and discussion themes are identified automatically as your conversations are analyzed.",
                                color = TextMuted,
                                fontSize = 13.sp,
                                textAlign = TextAlign.Center
                            )
                        }
                    }
                } else {
                    LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        items(filteredTopics) { t ->
                            Card(
                                modifier = Modifier.fillMaxWidth(),
                                colors = CardDefaults.cardColors(containerColor = CardDark),
                                border = BorderStroke(1.dp, CardBorder)
                            ) {
                                Row(
                                    modifier = Modifier.padding(14.dp),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Icon(Icons.Default.Tag, contentDescription = null, tint = PrimaryPurple, modifier = Modifier.size(16.dp))
                                    Spacer(Modifier.width(8.dp))
                                    Text(t.name, color = TextWhite, fontWeight = FontWeight.Bold, fontSize = 14.sp)
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

// ==========================================
// 10. COMMITMENTS SCREEN (TASKS & REMINDERS)
// ==========================================
@Composable
fun CommitmentsScreen(
    viewModel: CommitmentsViewModel,
    onNavigateRecord: () -> Unit = {}
) {
    val commitments by viewModel.commitments.collectAsState()
    var selectedTaskTab by remember { mutableStateOf(0) }

    LaunchedEffect(Unit) { viewModel.loadData() }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(BackgroundDark)
            .padding(16.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text("Tasks & Commitments", style = MaterialTheme.typography.titleLarge, color = TextWhite, fontWeight = FontWeight.Bold)
                Text("Action items and promises tracked across conversations", style = MaterialTheme.typography.bodySmall, color = TextMuted)
            }
            IconButton(onClick = { viewModel.loadData() }) {
                Icon(Icons.Default.Refresh, contentDescription = "Refresh", tint = PrimaryPurple)
            }
        }

        Spacer(modifier = Modifier.height(12.dp))

        // Filter Tabs: All, Open, Completed
        val openTasks = commitments.filter { it.status.lowercase() != "completed" && it.status.lowercase() != "fulfilled" }
        val completedTasks = commitments.filter { it.status.lowercase() == "completed" || it.status.lowercase() == "fulfilled" }

        TabRow(
            selectedTabIndex = selectedTaskTab,
            containerColor = CardDark,
            contentColor = PrimaryPurple
        ) {
            Tab(
                selected = selectedTaskTab == 0,
                onClick = { selectedTaskTab = 0 },
                text = { Text("All (${commitments.size})", fontWeight = FontWeight.SemiBold) }
            )
            Tab(
                selected = selectedTaskTab == 1,
                onClick = { selectedTaskTab = 1 },
                text = { Text("Open (${openTasks.size})", fontWeight = FontWeight.SemiBold) }
            )
            Tab(
                selected = selectedTaskTab == 2,
                onClick = { selectedTaskTab = 2 },
                text = { Text("Completed (${completedTasks.size})", fontWeight = FontWeight.SemiBold) }
            )
        }

        Spacer(modifier = Modifier.height(14.dp))

        val currentTasks = when (selectedTaskTab) {
            1 -> openTasks
            2 -> completedTasks
            else -> commitments
        }

        if (currentTasks.isEmpty()) {
            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.padding(24.dp)) {
                    Icon(Icons.Default.CheckCircle, contentDescription = null, tint = TextMuted, modifier = Modifier.size(56.dp))
                    Spacer(Modifier.height(12.dp))
                    Text(
                        if (selectedTaskTab == 2) "No Completed Tasks" else "No Commitments or Tasks Found",
                        color = TextWhite,
                        fontWeight = FontWeight.Bold,
                        fontSize = 16.sp
                    )
                    Spacer(Modifier.height(6.dp))
                    Text(
                        "Action items, commitments, and deadlines are automatically tracked as your conversations are analyzed.",
                        color = TextMuted,
                        fontSize = 13.sp,
                        textAlign = TextAlign.Center
                    )
                    Spacer(Modifier.height(16.dp))
                    Button(
                        onClick = onNavigateRecord,
                        colors = ButtonDefaults.buttonColors(containerColor = PrimaryPurple)
                    ) {
                        Icon(Icons.Default.Mic, contentDescription = null, modifier = Modifier.size(16.dp))
                        Spacer(Modifier.width(6.dp))
                        Text("Record a Meeting")
                    }
                }
            }
        } else {
            LazyColumn(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                items(currentTasks) { c ->
                    val isDone = c.status.lowercase() == "completed" || c.status.lowercase() == "fulfilled"
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        colors = CardDefaults.cardColors(containerColor = CardDark),
                        border = BorderStroke(1.dp, CardBorder)
                    ) {
                        Column(modifier = Modifier.padding(14.dp)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                IconButton(
                                    onClick = {
                                        c.id?.let { id ->
                                            viewModel.updateStatus(id, if (isDone) "open" else "completed")
                                        }
                                    },
                                    modifier = Modifier.size(28.dp)
                                ) {
                                    Icon(
                                        if (isDone) Icons.Default.CheckCircle else Icons.Default.RadioButtonUnchecked,
                                        contentDescription = "Toggle status",
                                        tint = if (isDone) AccentSuccess else TextMuted
                                    )
                                }
                                Spacer(Modifier.width(8.dp))
                                Text(
                                    c.title ?: c.commitmentText ?: c.text ?: "Task Item",
                                    color = if (isDone) TextMuted else TextWhite,
                                    fontWeight = FontWeight.Bold,
                                    fontSize = 14.sp,
                                    modifier = Modifier.weight(1f)
                                )
                                Surface(
                                    color = if (isDone) AccentSuccess.copy(alpha = 0.15f) else AccentWarning.copy(alpha = 0.15f),
                                    shape = RoundedCornerShape(4.dp)
                                ) {
                                    Text(
                                        c.status.uppercase(),
                                        color = if (isDone) AccentSuccess else AccentWarning,
                                        fontSize = 10.sp,
                                        fontWeight = FontWeight.Bold,
                                        modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                                    )
                                }
                            }

                            c.promiserName?.let {
                                Spacer(Modifier.height(6.dp))
                                Text("Promised by: $it", color = TextMuted, fontSize = 12.sp)
                            }
                            c.dueDate?.let {
                                Spacer(Modifier.height(4.dp))
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Icon(Icons.Default.CalendarToday, contentDescription = null, tint = PrimaryPurple, modifier = Modifier.size(12.dp))
                                    Spacer(Modifier.width(4.dp))
                                    Text("Due: $it", color = PrimaryPurple, fontSize = 11.sp, fontWeight = FontWeight.Medium)
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

// ==========================================
// 11. ASSISTANT SCREEN (AI MEETING ASSISTANT)
// ==========================================
@Composable
fun AssistantScreen(viewModel: AssistantViewModel, onSelectConversation: (Int) -> Unit) {
    var query by remember { mutableStateOf("") }
    val messages by viewModel.messages.collectAsState()
    val isLoading by viewModel.isLoading.collectAsState()
    val listState = rememberLazyListState()

    // Auto-scroll to bottom when new message arrives
    LaunchedEffect(messages.size, isLoading) {
        if (messages.isNotEmpty()) {
            listState.animateScrollToItem(messages.size - 1)
        }
    }

    val suggestedPrompts = listOf(
        "What was discussed in our latest meeting?",
        "Are there any pending action items or tasks?",
        "What decisions were made recently?",
        "Who participated in the last discussion?"
    )

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(BackgroundDark)
            .padding(16.dp)
            .imePadding()
    ) {
        Column {
            Text("Meeting Assistant", style = MaterialTheme.typography.titleLarge, color = TextWhite, fontWeight = FontWeight.Bold)
            Text("Ask questions about discussions, tasks, and decisions across meetings", style = MaterialTheme.typography.bodySmall, color = TextMuted)
        }

        Spacer(modifier = Modifier.height(12.dp))

        LazyColumn(
            state = listState,
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            if (messages.isEmpty()) {
                item {
                    Column(
                        horizontalAlignment = Alignment.CenterHorizontally,
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(vertical = 20.dp)
                    ) {
                        Surface(
                            color = PrimaryPurple.copy(alpha = 0.15f),
                            shape = CircleShape,
                            modifier = Modifier.size(64.dp)
                        ) {
                            Box(contentAlignment = Alignment.Center) {
                                Icon(Icons.Default.SmartToy, contentDescription = null, tint = PrimaryPurple, modifier = Modifier.size(36.dp))
                            }
                        }
                        Spacer(Modifier.height(14.dp))
                        Text("Meeting Assistant", color = TextWhite, fontWeight = FontWeight.Bold, fontSize = 16.sp)
                        Spacer(Modifier.height(4.dp))
                        Text(
                            "I can help you review and search across all your recorded meetings and notes.",
                            color = TextMuted,
                            fontSize = 13.sp,
                            textAlign = TextAlign.Center
                        )

                        Spacer(Modifier.height(20.dp))
                        Text("Suggested Questions:", color = TextWhite, fontWeight = FontWeight.SemiBold, fontSize = 13.sp)
                        Spacer(Modifier.height(8.dp))

                        suggestedPrompts.forEach { prompt ->
                            Card(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(vertical = 4.dp)
                                    .clickable {
                                        viewModel.askQuery(prompt)
                                    },
                                colors = CardDefaults.cardColors(containerColor = CardDark),
                                border = BorderStroke(1.dp, CardBorder)
                            ) {
                                Row(
                                    modifier = Modifier.padding(12.dp),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Icon(Icons.Default.QuestionAnswer, contentDescription = null, tint = PrimaryPurple, modifier = Modifier.size(16.dp))
                                    Spacer(Modifier.width(8.dp))
                                    Text(prompt, color = TextWhite, fontSize = 13.sp)
                                }
                            }
                        }
                    }
                }
            }

            items(messages) { (q, ans) ->
                // User Question Bubble
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = PrimaryPurple.copy(alpha = 0.25f)),
                    border = BorderStroke(1.dp, PrimaryPurple.copy(alpha = 0.4f))
                ) {
                    Column(modifier = Modifier.padding(12.dp)) {
                        Text("You", color = PrimaryPurple, fontWeight = FontWeight.Bold, fontSize = 11.sp)
                        Spacer(Modifier.height(2.dp))
                        Text(q, color = TextWhite, fontSize = 14.sp)
                    }
                }

                // Assistant Answer Bubble
                if (ans != null) {
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        colors = CardDefaults.cardColors(containerColor = CardDark),
                        border = BorderStroke(1.dp, CardBorder)
                    ) {
                        Column(modifier = Modifier.padding(14.dp)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Icon(Icons.Default.SmartToy, contentDescription = null, tint = PrimaryPurple, modifier = Modifier.size(14.dp))
                                Spacer(Modifier.width(6.dp))
                                Text("Assistant", color = PrimaryPurple, fontWeight = FontWeight.Bold, fontSize = 11.sp)
                            }
                            Spacer(Modifier.height(6.dp))
                            Text(ans.answer, color = TextWhite, fontSize = 14.sp)
                            if (ans.sourceIds.isNotEmpty()) {
                                Spacer(modifier = Modifier.height(10.dp))
                                Row(
                                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Text("Sources:", color = TextMuted, fontSize = 11.sp)
                                    ans.sourceIds.forEach { srcId ->
                                        AssistChip(
                                            onClick = { onSelectConversation(srcId) },
                                            label = { Text("Meeting #$srcId", fontSize = 11.sp) }
                                        )
                                    }
                                }
                            }
                        }
                    }
                }
            }

            if (isLoading) {
                item {
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        colors = CardDefaults.cardColors(containerColor = CardDark),
                        border = BorderStroke(1.dp, CardBorder)
                    ) {
                        Row(
                            modifier = Modifier.padding(14.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(16.dp),
                                color = PrimaryPurple,
                                strokeWidth = 2.dp
                            )
                            Spacer(Modifier.width(10.dp))
                            Text("Finding answers in your meetings...", color = TextMuted, fontSize = 13.sp)
                        }
                    }
                }
            }
        }

        Spacer(modifier = Modifier.height(8.dp))

        // Message Composer
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            OutlinedTextField(
                value = query,
                onValueChange = { query = it },
                modifier = Modifier.weight(1f),
                placeholder = { Text("Ask about your meetings...", color = TextMuted) },
                shape = RoundedCornerShape(24.dp),
                singleLine = true,
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = PrimaryPurple,
                    unfocusedBorderColor = CardBorder,
                    focusedTextColor = TextWhite,
                    unfocusedTextColor = TextWhite
                )
            )
            Spacer(Modifier.width(8.dp))
            IconButton(
                onClick = {
                    if (query.isNotBlank() && !isLoading) {
                        viewModel.askQuery(query.trim())
                        query = ""
                    }
                },
                enabled = query.isNotBlank() && !isLoading
            ) {
                Icon(
                    imageVector = Icons.AutoMirrored.Filled.Send,
                    contentDescription = "Send",
                    tint = if (query.isNotBlank() && !isLoading) PrimaryPurple else TextMuted
                )
            }
        }
    }
}

// ==========================================
// 12. SETTINGS SCREEN
// ==========================================
@Composable
fun SettingsScreen(viewModel: SettingsViewModel, mainViewModel: MainViewModel) {
    var showWipeConfirm by remember { mutableStateOf(false) }
    var showDeleteConfirm by remember { mutableStateOf(false) }
    var isWiping by remember { mutableStateOf(false) }
    var actionMessage by remember { mutableStateOf<String?>(null) }

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .background(BackgroundDark)
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        item {
            Column {
                Text("Settings & Privacy", style = MaterialTheme.typography.titleLarge, color = TextWhite, fontWeight = FontWeight.Bold)
                Text("Manage recording consent, storage, and account settings", style = MaterialTheme.typography.bodySmall, color = TextMuted)
            }
        }

        actionMessage?.let { msg ->
            item {
                Surface(
                    color = PrimaryPurple.copy(alpha = 0.15f),
                    shape = RoundedCornerShape(8.dp),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text(msg, color = TextWhite, fontSize = 13.sp, modifier = Modifier.padding(12.dp))
                }
            }
        }

        // Section 1: Legal Recording Compliance
        item {
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = CardDark),
                border = BorderStroke(1.dp, CardBorder)
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.Gavel, contentDescription = null, tint = PrimaryPurple, modifier = Modifier.size(18.dp))
                        Spacer(Modifier.width(8.dp))
                        Text("Recording Consent & Region", color = TextWhite, fontWeight = FontWeight.Bold, fontSize = 14.sp)
                    }
                    Spacer(Modifier.height(8.dp))
                    Text(
                        "Consent rules ensure all participants agree to recording based on your selected region.",
                        color = TextMuted,
                        fontSize = 12.sp
                    )
                    Spacer(Modifier.height(10.dp))
                    Surface(
                        color = BackgroundDark,
                        shape = RoundedCornerShape(6.dp),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Row(
                            modifier = Modifier.padding(10.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text("Consent Rule: ", color = TextMuted, fontSize = 12.sp)
                            Text("All-Party Consent (Default Global)", color = AccentSuccess, fontWeight = FontWeight.SemiBold, fontSize = 12.sp)
                        }
                    }
                }
            }
        }

        // Section 2: Audio & Local Storage (Privacy Controls)
        item {
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = CardDark),
                border = BorderStroke(1.dp, CardBorder)
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.Security, contentDescription = null, tint = AccentSuccess, modifier = Modifier.size(18.dp))
                        Spacer(Modifier.width(8.dp))
                        Text("Audio Storage & Privacy", color = TextWhite, fontWeight = FontWeight.Bold, fontSize = 14.sp)
                    }
                    Spacer(Modifier.height(8.dp))
                    Text(
                        "Audio recordings are securely encrypted. Clearing stored audio removes saved audio files from your device and server while preserving your transcripts, meeting notes, and action items.",
                        color = TextMuted,
                        fontSize = 12.sp
                    )
                    Spacer(Modifier.height(14.dp))
                    OutlinedButton(
                        onClick = { showWipeConfirm = true },
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(8.dp),
                        border = BorderStroke(1.dp, CardBorder)
                    ) {
                        Icon(Icons.Default.Delete, contentDescription = null, modifier = Modifier.size(16.dp), tint = AccentWarning)
                        Spacer(Modifier.width(8.dp))
                        Text("Clear Stored Audio Files", color = TextWhite, fontSize = 13.sp)
                    }
                }
            }
        }

        // Section 3: Account & Data Erasure
        item {
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = CardDark),
                border = BorderStroke(1.dp, CardBorder)
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.Warning, contentDescription = null, tint = AccentDanger, modifier = Modifier.size(18.dp))
                        Spacer(Modifier.width(8.dp))
                        Text("Delete Account & Data", color = TextWhite, fontWeight = FontWeight.Bold, fontSize = 14.sp)
                    }
                    Spacer(Modifier.height(8.dp))
                    Text(
                        "Permanently delete your account and all conversations, transcripts, meeting notes, and personal history. This action cannot be undone.",
                        color = TextMuted,
                        fontSize = 12.sp
                    )
                    Spacer(Modifier.height(14.dp))
                    OutlinedButton(
                        onClick = { showDeleteConfirm = true },
                        colors = ButtonDefaults.outlinedButtonColors(contentColor = AccentDanger),
                        border = BorderStroke(1.dp, AccentDanger.copy(alpha = 0.5f)),
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(8.dp)
                    ) {
                        Text("Delete Account & All Data", color = AccentDanger, fontSize = 13.sp)
                    }
                }
            }
        }

        // Section 4: Session Control
        item {
            Spacer(modifier = Modifier.height(12.dp))
            OutlinedButton(
                onClick = { mainViewModel.logout() },
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(8.dp),
                border = BorderStroke(1.dp, SecondarySlate)
            ) {
                Icon(Icons.AutoMirrored.Filled.ExitToApp, contentDescription = null, modifier = Modifier.size(16.dp), tint = TextMuted)
                Spacer(Modifier.width(8.dp))
                Text("Log Out", color = TextWhite)
            }
        }
    }

    if (showWipeConfirm) {
        AlertDialog(
            onDismissRequest = { showWipeConfirm = false },
            title = { Text("Clear Stored Audio?", color = TextWhite, fontWeight = FontWeight.Bold) },
            text = {
                Text(
                    "This will delete saved audio files from device and server storage. Your transcripts, meeting notes, action items, and decisions will remain intact.",
                    color = TextMuted
                )
            },
            confirmButton = {
                Button(
                    onClick = {
                        isWiping = true
                        viewModel.wipeData {
                            isWiping = false
                            showWipeConfirm = false
                            actionMessage = "Stored audio files successfully cleared."
                        }
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = AccentWarning)
                ) {
                    Text("Clear Stored Audio")
                }
            },
            dismissButton = {
                TextButton(onClick = { showWipeConfirm = false }) {
                    Text("Cancel", color = TextMuted)
                }
            },
            containerColor = CardDark
        )
    }

    if (showDeleteConfirm) {
        AlertDialog(
            onDismissRequest = { showDeleteConfirm = false },
            title = { Text("Delete Account & All Data?", color = AccentDanger, fontWeight = FontWeight.Bold) },
            text = {
                Text(
                    "This action is permanent and cannot be undone. All your recordings, transcripts, meeting notes, entities, and memories will be erased.",
                    color = TextMuted
                )
            },
            confirmButton = {
                Button(
                    onClick = {
                        viewModel.deleteAccount {
                            showDeleteConfirm = false
                            mainViewModel.logout()
                        }
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = AccentDanger)
                ) {
                    Text("Permanently Delete")
                }
            },
            dismissButton = {
                TextButton(onClick = { showDeleteConfirm = false }) {
                    Text("Cancel", color = TextMuted)
                }
            },
            containerColor = CardDark
        )
    }
}
