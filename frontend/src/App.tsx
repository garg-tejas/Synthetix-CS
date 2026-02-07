import { BrowserRouter, Routes, Route } from 'react-router-dom'

import { AuthProvider } from './auth/AuthContext'
import { AppShell } from './components/layout'
import DashboardPage from './routes/DashboardPage'
import ReviewPage from './routes/ReviewPage'
import LoginPage from './routes/LoginPage'
import SignupPage from './routes/SignupPage'
import ProtectedRoute from './routes/ProtectedRoute'

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<ProtectedRoute />}>
            <Route element={<AppShell mode="workspace" width="content" />}>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/review" element={<ReviewPage />} />
            </Route>
          </Route>
          <Route element={<AppShell mode="auth" width="content" />}>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/signup" element={<SignupPage />} />
          </Route>
          <Route element={<AppShell mode="plain" width="narrow" />}>
            <Route
              path="*"
              element={
                <div className="layout-stack layout-stack--sm">
                  <h1>404 - Not Found</h1>
                  <p className="u-muted">The requested page does not exist.</p>
                </div>
              }
            />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}

export default App
