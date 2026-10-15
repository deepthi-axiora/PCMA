package com.pcma.app.ui.navigation

import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.*
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.*
import androidx.navigation.navArgument
import com.pcma.app.ui.screens.*
import com.pcma.app.ui.theme.*
import com.pcma.app.ui.viewmodel.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PcmaNavHost(
    navController: NavHostController = rememberNavController(),
    mainViewModel: MainViewModel,
    recordingViewModel: RecordingViewModel,
    conversationsViewModel: ConversationsViewModel,
    momViewModel: MomViewModel,
    searchViewModel: SearchViewModel,
    entitiesViewModel: EntitiesViewModel,
    commitmentsViewModel: CommitmentsViewModel,
    assistantViewModel: AssistantViewModel,
    settingsViewModel: SettingsViewModel,
    cacheDir: java.io.File
) {
    // 5 primary mobile destinations with clean single-word labels that never wrap awkwardly
    val navItems = listOf(
        Screen.Record,
        Screen.Conversations,
        Screen.Mom,
        Screen.Search,
        Screen.More
    )

    val topLevelRoutes = navItems.map { it.route }.toSet()
    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = navBackStackEntry?.destination?.route

    val screenTitle = when {
        currentRoute == Screen.Record.route -> "Record"
        currentRoute == Screen.Conversations.route -> "Conversations"
        currentRoute?.startsWith("conversation_detail") == true -> "Conversation Detail"
        currentRoute == Screen.Mom.route -> "Minutes of Meeting"
        currentRoute == Screen.Search.route -> "Search Conversations"
        currentRoute == Screen.More.route -> "Tools & Features"
        currentRoute == Screen.Assistant.route -> "Meeting Assistant"
        currentRoute == Screen.Commitments.route -> "Tasks & Reminders"
        currentRoute == Screen.Entities.route -> "People & Projects"
        currentRoute == Screen.Settings.route -> "Settings & Privacy"
        else -> "PCMA"
    }

    val isTopLevel = currentRoute in topLevelRoutes

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        text = screenTitle,
                        style = MaterialTheme.typography.titleMedium,
                        color = TextWhite
                    )
                },
                navigationIcon = {
                    if (!isTopLevel) {
                        IconButton(onClick = { navController.popBackStack() }) {
                            Icon(
                                imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                                contentDescription = "Back",
                                tint = TextWhite
                            )
                        }
                    } else {
                        Icon(
                            imageVector = Icons.Default.GraphicEq,
                            contentDescription = "PCMA",
                            tint = PrimaryPurple,
                            modifier = Modifier
                                .padding(start = 16.dp, end = 8.dp)
                                .size(24.dp)
                        )
                    }
                },
                actions = {
                    if (isTopLevel) {
                        // Quick 1-tap shortcuts to Ask Assistant and Tasks from top bar
                        IconButton(
                            onClick = {
                                navController.navigate(Screen.Assistant.route) {
                                    launchSingleTop = true
                                }
                            }
                        ) {
                            Icon(
                                imageVector = Icons.Default.SmartToy,
                                contentDescription = "Meeting Assistant",
                                tint = if (currentRoute == Screen.Assistant.route) PrimaryPurple else TextMuted
                            )
                        }
                        IconButton(
                            onClick = {
                                navController.navigate(Screen.Commitments.route) {
                                    launchSingleTop = true
                                }
                            }
                        ) {
                            Icon(
                                imageVector = Icons.Default.CheckCircle,
                                contentDescription = "Tasks",
                                tint = if (currentRoute == Screen.Commitments.route) AccentSuccess else TextMuted
                            )
                        }
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = CardDark)
            )
        },
        bottomBar = {
            NavigationBar(containerColor = CardDark) {
                navItems.forEach { screen ->
                    val isSelected = currentRoute == screen.route
                    val icon = when (screen) {
                        Screen.Record -> Icons.Default.Mic
                        Screen.Conversations -> Icons.AutoMirrored.Filled.LibraryBooks
                        Screen.Mom -> Icons.Default.Description
                        Screen.Search -> Icons.Default.Search
                        Screen.More -> Icons.Default.MoreHoriz
                        else -> Icons.Default.Star
                    }

                    NavigationBarItem(
                        icon = { Icon(icon, contentDescription = screen.title) },
                        label = { Text(screen.title) },
                        selected = isSelected,
                        onClick = {
                            navController.navigate(screen.route) {
                                popUpTo(navController.graph.findStartDestination().id) {
                                    saveState = true
                                }
                                launchSingleTop = true
                                restoreState = true
                            }
                        },
                        colors = NavigationBarItemDefaults.colors(
                            selectedIconColor = PrimaryPurple,
                            selectedTextColor = PrimaryPurple,
                            unselectedIconColor = TextMuted,
                            unselectedTextColor = TextMuted,
                            indicatorColor = PrimaryPurple.copy(alpha = 0.15f)
                        )
                    )
                }
            }
        }
    ) { innerPadding ->
        NavHost(
            navController = navController,
            startDestination = Screen.Record.route,
            modifier = Modifier.padding(innerPadding)
        ) {
            composable(Screen.Record.route) {
                RecordScreen(
                    viewModel = recordingViewModel,
                    cacheDir = cacheDir,
                    onOpenConversation = { id ->
                        conversationsViewModel.selectConversation(id)
                        momViewModel.selectConversation(id)
                        navController.navigate(Screen.ConversationDetail.createRoute(id))
                    },
                    onNavigateChats = {
                        navController.navigate(Screen.Conversations.route)
                    },
                    onNavigateMom = {
                        navController.navigate(Screen.Mom.route)
                    },
                    onNavigateAssistant = {
                        navController.navigate(Screen.Assistant.route)
                    }
                )
            }

            composable(Screen.Conversations.route) {
                val context = androidx.compose.ui.platform.LocalContext.current
                val selectedId by momViewModel.selectedConversationId.collectAsState()
                ConversationsScreen(
                    viewModel = conversationsViewModel,
                    selectedConversationId = selectedId,
                    onSelectConversation = { id ->
                        conversationsViewModel.selectConversation(id)
                        momViewModel.selectConversation(id)
                        navController.navigate(Screen.ConversationDetail.createRoute(id))
                    },
                    onOpenMom = { id ->
                        conversationsViewModel.selectConversation(id)
                        momViewModel.selectConversation(id)
                        navController.navigate(Screen.Mom.route) {
                            popUpTo(navController.graph.findStartDestination().id) {
                                saveState = true
                            }
                            launchSingleTop = true
                            restoreState = true
                        }
                    },
                    onNavigateRecord = {
                        navController.navigate(Screen.Record.route)
                    },
                    onReauthenticate = {
                        mainViewModel.loginWithAuth0(context) {
                            conversationsViewModel.loadConversations()
                        }
                    },
                    onLogout = {
                        mainViewModel.logout()
                    }
                )
            }

            composable(
                route = Screen.ConversationDetail.route,
                arguments = listOf(navArgument("id") { type = NavType.IntType })
            ) { backStackEntry ->
                val id = backStackEntry.arguments?.getInt("id") ?: 0
                ConversationDetailScreen(
                    conversationId = id,
                    viewModel = conversationsViewModel,
                    onBack = { navController.popBackStack() },
                    onOpenMom = { convId ->
                        conversationsViewModel.selectConversation(convId)
                        momViewModel.selectConversation(convId)
                        navController.navigate(Screen.Mom.route) {
                            popUpTo(navController.graph.findStartDestination().id) {
                                saveState = true
                            }
                            launchSingleTop = true
                            restoreState = true
                        }
                    },
                    onRefreshMom = { convId ->
                        momViewModel.loadMom(convId)
                    }
                )
            }

            composable(Screen.Mom.route) {
                MomScreen(
                    viewModel = momViewModel,
                    onSelectOtherConversation = {
                        navController.navigate(Screen.Conversations.route) {
                            popUpTo(navController.graph.findStartDestination().id) {
                                saveState = true
                            }
                            launchSingleTop = true
                            restoreState = true
                        }
                    }
                )
            }

            composable(Screen.Search.route) {
                SearchMemoryScreen(
                    viewModel = searchViewModel,
                    onSelectConversation = { id ->
                        conversationsViewModel.selectConversation(id)
                        momViewModel.selectConversation(id)
                        navController.navigate(Screen.ConversationDetail.createRoute(id))
                    }
                )
            }

            composable(Screen.More.route) {
                MoreScreen(
                    mainViewModel = mainViewModel,
                    onNavigateAssistant = { navController.navigate(Screen.Assistant.route) },
                    onNavigateCommitments = { navController.navigate(Screen.Commitments.route) },
                    onNavigateEntities = { navController.navigate(Screen.Entities.route) },
                    onNavigateSettings = { navController.navigate(Screen.Settings.route) }
                )
            }

            composable(Screen.Entities.route) {
                EntitiesScreen(
                    viewModel = entitiesViewModel,
                    onNavigateChats = { navController.navigate(Screen.Conversations.route) }
                )
            }

            composable(Screen.Commitments.route) {
                CommitmentsScreen(
                    viewModel = commitmentsViewModel,
                    onNavigateRecord = { navController.navigate(Screen.Record.route) }
                )
            }

            composable(Screen.Assistant.route) {
                AssistantScreen(
                    viewModel = assistantViewModel,
                    onSelectConversation = { id ->
                        conversationsViewModel.selectConversation(id)
                        momViewModel.selectConversation(id)
                        navController.navigate(Screen.ConversationDetail.createRoute(id))
                    }
                )
            }

            composable(Screen.Settings.route) {
                SettingsScreen(
                    viewModel = settingsViewModel,
                    mainViewModel = mainViewModel
                )
            }
        }
    }
}
