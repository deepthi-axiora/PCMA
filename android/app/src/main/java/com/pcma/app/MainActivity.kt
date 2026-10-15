package com.pcma.app

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.core.content.ContextCompat
import com.pcma.app.data.local.OfflineQueueManager
import com.pcma.app.data.local.SecureTokenStorage
import com.pcma.app.data.repository.AudioRecordingManager
import com.pcma.app.data.repository.PcmaRepository
import com.pcma.app.ui.navigation.PcmaNavHost
import com.pcma.app.ui.screens.LoginScreen
import com.pcma.app.ui.theme.PcmaTheme
import com.pcma.app.ui.viewmodel.*

class MainActivity : ComponentActivity() {

    private lateinit var storage: SecureTokenStorage
    private lateinit var offlineQueue: OfflineQueueManager
    private lateinit var repository: PcmaRepository
    private lateinit var recordingManager: AudioRecordingManager

    private lateinit var mainViewModel: MainViewModel
    private lateinit var recordingViewModel: RecordingViewModel
    private lateinit var conversationsViewModel: ConversationsViewModel
    private lateinit var momViewModel: MomViewModel
    private lateinit var searchViewModel: SearchViewModel
    private lateinit var entitiesViewModel: EntitiesViewModel
    private lateinit var commitmentsViewModel: CommitmentsViewModel
    private lateinit var assistantViewModel: AssistantViewModel
    private lateinit var settingsViewModel: SettingsViewModel

    private val requestPermissionsLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { permissions ->
        // Handle runtime permissions result
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // 1. Initialize Singletons & Repository
        storage = SecureTokenStorage(applicationContext)
        offlineQueue = OfflineQueueManager(applicationContext)
        repository = PcmaRepository(storage, offlineQueue)
        recordingManager = AudioRecordingManager(applicationContext)

        // 2. Initialize ViewModels
        mainViewModel = MainViewModel(repository)
        recordingViewModel = RecordingViewModel(repository, recordingManager)
        conversationsViewModel = ConversationsViewModel(repository)
        momViewModel = MomViewModel(repository)
        searchViewModel = SearchViewModel(repository)
        entitiesViewModel = EntitiesViewModel(repository)
        commitmentsViewModel = CommitmentsViewModel(repository)
        assistantViewModel = AssistantViewModel(repository)
        settingsViewModel = SettingsViewModel(repository)

        // 3. Request Runtime Permissions
        checkAndRequestPermissions()

        // 4. Render Jetpack Compose UI Content
        setContent {
            PcmaTheme {
                val isAuthenticated by mainViewModel.isAuthenticated.collectAsState()

                if (!isAuthenticated) {
                    LoginScreen(
                        onLoginSuccess = { mainViewModel.loadProfile() },
                        mainViewModel = mainViewModel
                    )
                } else {
                    PcmaNavHost(
                        mainViewModel = mainViewModel,
                        recordingViewModel = recordingViewModel,
                        conversationsViewModel = conversationsViewModel,
                        momViewModel = momViewModel,
                        searchViewModel = searchViewModel,
                        entitiesViewModel = entitiesViewModel,
                        commitmentsViewModel = commitmentsViewModel,
                        assistantViewModel = assistantViewModel,
                        settingsViewModel = settingsViewModel,
                        cacheDir = cacheDir
                    )
                }
            }
        }
    }

    private fun checkAndRequestPermissions() {
        val permissionsToRequest = mutableListOf<String>()

        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            permissionsToRequest.add(Manifest.permission.RECORD_AUDIO)
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                permissionsToRequest.add(Manifest.permission.POST_NOTIFICATIONS)
            }
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.BLUETOOTH_CONNECT) != PackageManager.PERMISSION_GRANTED) {
                permissionsToRequest.add(Manifest.permission.BLUETOOTH_CONNECT)
            }
        }

        if (permissionsToRequest.isNotEmpty()) {
            requestPermissionsLauncher.launch(permissionsToRequest.toTypedArray())
        }
    }
}
