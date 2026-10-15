import { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { useAuth0 } from '@auth0/auth0-react'
import { setAuthTokenGetter } from '../api/client'
import { getMe, getProfile } from '../api/profile'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const auth0 = useAuth0()
  const {
    isAuthenticated: isAuth0Authenticated,
    isLoading: isAuth0Loading,
    user: auth0User,
    loginWithRedirect,
    logout: auth0Logout,
    getAccessTokenSilently,
  } = auth0

  const [backendUser, setBackendUser] = useState(null)
  const [profile, setProfile] = useState(null)
  const [authError, setAuthError] = useState(null)
  const [isLoadingUser, setIsLoadingUser] = useState(true)
  const [devMode, setDevMode] = useState(false)

  // Token getter callback injected into apiFetch
  const tokenGetter = useCallback(async () => {
    if (devMode) {
      return 'dev-mock-jwt-token'
    }
    if (isAuth0Authenticated) {
      try {
        const audience = import.meta.env.VITE_AUTH0_AUDIENCE
        return await getAccessTokenSilently({
          authorizationParams: {
            audience: audience || 'https://pcma-api',
          },
        })
      } catch (err) {
        console.warn('Auth0 getAccessTokenSilently failed:', err)
        return null
      }
    }
    return null
  }, [isAuth0Authenticated, devMode, getAccessTokenSilently])

  useEffect(() => {
    setAuthTokenGetter(tokenGetter)
  }, [tokenGetter])

  const fetchUserData = useCallback(async () => {
    setIsLoadingUser(true)
    setAuthError(null)
    try {
      const meData = await getMe()
      setBackendUser(meData)

      try {
        const profileData = await getProfile()
        setProfile(profileData)
      } catch (profErr) {
        console.warn('Could not load profile:', profErr)
      }
    } catch (err) {
      console.error('Failed to load user data from backend:', err)
      setAuthError(err.message || 'Backend authentication failed')
    } finally {
      setIsLoadingUser(false)
    }
  }, [])

  useEffect(() => {
    if (isAuth0Authenticated) {
      fetchUserData()
    } else if (!isAuth0Loading) {
      // Check if dev environment wants mock login if Auth0 domain is not active
      const hasAuth0Config = Boolean(import.meta.env.VITE_AUTH0_DOMAIN && import.meta.env.VITE_AUTH0_CLIENT_ID)
      if (!hasAuth0Config) {
        // Fallback for local testing without Auth0 tenant setup
        setDevMode(true)
      } else {
        setIsLoadingUser(false)
      }
    }
  }, [isAuth0Authenticated, isAuth0Loading, fetchUserData])

  useEffect(() => {
    if (devMode) {
      fetchUserData()
    }
  }, [devMode, fetchUserData])

  const login = () => {
    if (import.meta.env.VITE_AUTH0_DOMAIN) {
      loginWithRedirect()
    } else {
      setDevMode(true)
    }
  }

  const logout = () => {
    setBackendUser(null)
    setProfile(null)
    setDevMode(false)
    if (isAuth0Authenticated) {
      auth0Logout({
        logoutParams: {
          returnTo: window.location.origin,
        },
      })
    }
  }

  const refreshProfile = async () => {
    try {
      const profData = await getProfile()
      setProfile(profData)
      return profData
    } catch (err) {
      console.error('Profile refresh failed:', err)
      throw err
    }
  }

  const value = {
    isAuthenticated: isAuth0Authenticated || devMode,
    isLoading: isAuth0Loading || isLoadingUser,
    user: auth0User || (backendUser ? { name: `User #${backendUser.id}`, email: `user_${backendUser.id}@pcma.local` } : null),
    backendUser,
    profile,
    authError,
    devMode,
    login,
    logout,
    refreshProfile,
    refetchUser: fetchUserData,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
