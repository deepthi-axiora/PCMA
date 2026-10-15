package com.pcma.app.ui.navigation

sealed class Screen(val route: String, val title: String) {
    object Login : Screen("login", "Log In")
    object OnboardingConsent : Screen("consent", "Consent Setup")
    object Record : Screen("record", "Record")
    object Conversations : Screen("conversations", "Chats")
    object ConversationDetail : Screen("conversation_detail/{id}", "Conversation Detail") {
        fun createRoute(id: Int) = "conversation_detail/$id"
    }
    object Mom : Screen("mom", "Notes")
    object Search : Screen("search", "Search")
    object More : Screen("more", "More")
    object Entities : Screen("entities", "People")
    object Commitments : Screen("commitments", "Tasks")
    object Assistant : Screen("assistant", "Ask")
    object Settings : Screen("settings", "Settings")
}
