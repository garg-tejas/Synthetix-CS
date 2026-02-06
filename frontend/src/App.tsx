import { BrowserRouter, Routes, Route } from 'react-router-dom'

import { AuthProvider } from './auth/AuthContext'
import LoginPage from './routes/LoginPage'
import SignupPage from './routes/SignupPage'

function Home() {
  return (
    <div>
      <h1>SLM RAG Skill Tracker</h1>
      <p>Welcome to the skill tracker frontend.</p>
    </div>
  )
}

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/signup" element={<SignupPage />} />
          <Route path="*" element={<div>404 - Not Found</div>} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}

export default App
