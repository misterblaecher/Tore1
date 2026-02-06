import React from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { getToken } from './lib/auth'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import EventDetail from './pages/EventDetail'

function RequireAuth({ children }: { children: React.ReactNode }) {
  const token = getToken()
  if (!token) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <Dashboard />
          </RequireAuth>
        }
      />
      <Route
        path="/events/:eventId"
        element={
          <RequireAuth>
            <EventDetail />
          </RequireAuth>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
