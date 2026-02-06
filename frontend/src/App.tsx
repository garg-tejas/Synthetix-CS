import { BrowserRouter, Routes, Route } from 'react-router-dom'

import { AuthProvider } from './auth/AuthContext'
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
            <Route path="/" element={<DashboardPage />} />
            <Route path="/review" element={<ReviewPage />} />
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
