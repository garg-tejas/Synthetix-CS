import { BrowserRouter, Routes, Route, Link } from 'react-router-dom'

import { AuthProvider, useAuth } from './auth/AuthContext'
import LoginPage from './routes/LoginPage'
import SignupPage from './routes/SignupPage'
import ProtectedRoute from './routes/ProtectedRoute'

function Home() {
  const { user, clearSession, status } = useAuth()
  return (
    <div style={{ padding: 24 }}>
      <h1>SLM RAG Skill Tracker</h1>
      <p>Welcome to the skill tracker frontend.</p>
      <div style={{ marginTop: 16 }}>
        {status === 'authenticated' && user ? (
          <>
            <div style={{ marginBottom: 8 }}>
              Signed in as <strong>{user.username}</strong>
            </div>
            <button onClick={clearSession} style={{ padding: 8, cursor: 'pointer' }}>
              Log out
            </button>
          </>
        ) : (
          <>
            <Link to="/login" style={{ marginRight: 12 }}>
              Log in
            </Link>
            <Link to="/signup">Sign up</Link>
          </>
        )}
      </div>
    </div>
  )
}

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<Home />} />
          </Route>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/signup" element={<SignupPage />} />
          <Route path="*" element={<div>404 - Not Found</div>} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}

export default App
