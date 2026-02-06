import React from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { getToken } from '../utils/auth'
import LoginPage from './LoginPage'
import DashboardPage from './DashboardPage'
import EventPage from './EventPage'

function RequireAuth({ children }: { children: React.ReactNode }) {
  const token = getToken()
  if (!token) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <DashboardPage />
          </RequireAuth>
        }
      />
      <Route
        path="/events/:eventId"
        element={
          <RequireAuth>
            <EventPage />
          </RequireAuth>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
