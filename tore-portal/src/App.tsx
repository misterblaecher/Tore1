import React from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { getToken } from './lib/auth'
import { hasOrgaHubAccess } from './lib/authz'
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
import MarketAdmin from './pages/MarketAdmin'
import MarketPublic from './pages/MarketPublic'
import EntryStaff from './pages/EntryStaff'
import EntryAdmin from './pages/EntryAdmin'
import EventControlHub from './pages/EventControlHub'
import WalletAdmin from './pages/WalletAdmin'
import PolymarketAdmin from './pages/PolymarketAdmin'
import BattlesLive from './pages/BattlesLive'
import CheckinsAdmin from './pages/CheckinsAdmin'
import AuditLogs from './pages/AuditLogs'
import WifiAdmin from './pages/WifiAdmin'
import SafetyAdmin from './pages/SafetyAdmin'
import ZonesAdmin from './pages/ZonesAdmin'
import Kitchen from './pages/Kitchen'
import BarDashboard from './pages/BarDashboard'
import CreateEventWizard from './pages/CreateEventWizard'
import EventQrPack from './pages/EventQrPack'
import StaffManagement from './pages/StaffManagement'
import OrgaBroadcast from './pages/OrgaBroadcast'

function RequireAuth({ children }: { children: React.ReactNode }) {
  const token = getToken()
  if (!token) return <Navigate to="/login" replace />
  return <>{children}</>
}

function RequireOrga({ children }: { children: React.ReactNode }) {
  if (!hasOrgaHubAccess()) return <Navigate to="/" replace />
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
        path="/bar-dashboard"
        element={
          <RequireAuth>
            <BarDashboard />
          </RequireAuth>
        }
      />
      <Route
        path="/kitchen"
        element={
          <RequireAuth>
            <Kitchen />
          </RequireAuth>
        }
      />
      <Route
        path="/battles-admin/:eventId"
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
      <Route
        path="/entry-staff"
        element={
          <RequireAuth>
            <EntryStaff />
          </RequireAuth>
        }
      />
      <Route
        path="/entry-admin"
        element={
          <RequireAuth>
            <EntryAdmin />
          </RequireAuth>
        }
      />
      <Route
        path="/event-control/:eventId"
        element={
          <RequireAuth>
            <RequireOrga>
              <EventControlHub />
            </RequireOrga>
          </RequireAuth>
        }
      />
      <Route
        path="/orga/create-event"
        element={
          <RequireAuth>
            <RequireOrga>
              <CreateEventWizard />
            </RequireOrga>
          </RequireAuth>
        }
      />
      <Route
        path="/orga/events/:eventId/staff"
        element={
          <RequireAuth>
            <RequireOrga>
              <StaffManagement />
            </RequireOrga>
          </RequireAuth>
        }
      />
      <Route
        path="/orga/events/:eventId/broadcast"
        element={
          <RequireAuth>
            <RequireOrga>
              <OrgaBroadcast />
            </RequireOrga>
          </RequireAuth>
        }
      />
      <Route
        path="/orga/events/:eventId/qr-pack"
        element={
          <RequireAuth>
            <RequireOrga>
              <EventQrPack />
            </RequireOrga>
          </RequireAuth>
        }
      />
      <Route
        path="/wallet-admin"
        element={
          <RequireAuth>
            <WalletAdmin />
          </RequireAuth>
        }
      />
      <Route
        path="/polymarket-admin/:eventId"
        element={
          <RequireAuth>
            <PolymarketAdmin />
          </RequireAuth>
        }
      />
      <Route
        path="/battles-live/:battleId"
        element={
          <RequireAuth>
            <BattlesLive />
          </RequireAuth>
        }
      />
      <Route
        path="/checkins-admin/:eventId"
        element={
          <RequireAuth>
            <CheckinsAdmin />
          </RequireAuth>
        }
      />
      <Route
        path="/audit/:eventId"
        element={
          <RequireAuth>
            <AuditLogs />
          </RequireAuth>
        }
      />
      <Route
        path="/wifi-admin/:eventId"
        element={
          <RequireAuth>
            <WifiAdmin />
          </RequireAuth>
        }
      />
      <Route
        path="/safety-admin/:eventId"
        element={
          <RequireAuth>
            <SafetyAdmin />
          </RequireAuth>
        }
      />
      <Route
        path="/zones-admin"
        element={
          <RequireAuth>
            <ZonesAdmin />
          </RequireAuth>
        }
      />
      <Route
        path="/market-admin"
        element={
          <RequireAuth>
            <MarketAdmin />
          </RequireAuth>
        }
      />
      <Route path="/menu/:barId" element={<MenuPublic />} />
      <Route path="/menu/:barId/item/:itemId" element={<MenuPublic />} />
      <Route path="/battles/:id" element={<BattlePublic />} />
      <Route path="/market/:barId" element={<MarketPublic />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
