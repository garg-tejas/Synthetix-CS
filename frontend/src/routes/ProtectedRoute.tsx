import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth as useClerkAuth } from '@clerk/react'

import { useAuth } from '../auth/AuthContext'

export default function ProtectedRoute() {
  const { status } = useAuth()
  const clerkAuth = useClerkAuth()
  const location = useLocation()

  // While Clerk is still initializing, show nothing (prevents flash)
  if (!clerkAuth.isLoaded || status === 'unknown') {
    return <div>Loading...</div>
  }

  // If Clerk says not signed in OR our local auth is not authenticated, redirect
  if (!clerkAuth.isSignedIn || status !== 'authenticated') {
    return <Navigate to="/login" replace state={{ from: location }} />
  }

  return <Outlet />
}
