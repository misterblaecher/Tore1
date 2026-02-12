import React from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { getToken } from './lib/auth'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import EventDetail from './pages/EventDetail'
import PolymarketGlobal from './pages/PolymarketGlobal'
import PolymarketEvent from './pages/PolymarketEvent'
import PolymarketDetail from './pages/PolymarketDetail'
import MenuAdmin from './pages/MenuAdmin'
import MenuPublic from './pages/MenuPublic'
import OrdersQueue from './pages/OrdersQueue'
import Analytics from './pages/Analytics'
import HuntAdmin from './pages/HuntAdmin'
import BattlesAdmin from './pages/BattlesAdmin'
import BattlePublic from './pages/BattlePublic'

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
      <Route
        path="/events/:eventId/polymarket"
        element={
          <RequireAuth>
            <PolymarketEvent />
          </RequireAuth>
        }
      />
      <Route
        path="/polymarket"
        element={
          <RequireAuth>
            <PolymarketGlobal />
          </RequireAuth>
        }
      />
      <Route
        path="/polymarket/:betId"
        element={
          <RequireAuth>
            <PolymarketDetail />
          </RequireAuth>
        }
      />
      <Route
        path="/menu-admin"
        element={
          <RequireAuth>
            <MenuAdmin />
          </RequireAuth>
        }
      />
      <Route
        path="/analytics"
        element={
          <RequireAuth>
            <Analytics />
          </RequireAuth>
        }
      />
      <Route
        path="/orders-queue"
        element={
          <RequireAuth>
            <OrdersQueue />
          </RequireAuth>
        }
      />
      <Route
        path="/battles-admin"
        element={
          <RequireAuth>
            <BattlesAdmin />
          </RequireAuth>
        }
      />
      <Route
        path="/hunt-admin"
        element={
          <RequireAuth>
            <HuntAdmin />
          </RequireAuth>
        }
      />
      <Route path="/menu/:barId" element={<MenuPublic />} />
      <Route path="/menu/:barId/item/:itemId" element={<MenuPublic />} />
      <Route path="/battles/:id" element={<BattlePublic />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
