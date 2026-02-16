import React from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { getToken } from './lib/auth'
import { hasBarModeAccess, hasGlobalAdmin, hasOrgaHubAccess, hasOrgaManagerAccess } from './lib/authz'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import EventDetail from './pages/EventDetail'
import PolymarketGlobal from './pages/PolymarketGlobal'
import PolymarketEvent from './pages/PolymarketEvent'
import PolymarketDetail from './pages/PolymarketDetail'
import MenuAdmin from './pages/MenuAdmin'
import MenuPublic from './pages/MenuPublic'
import OrdersQueue from './pages/OrdersQueue'
import BarOrdersLive from './pages/BarOrdersLive'
import BarMenuAdmin from './pages/BarMenuAdmin'
import BarAnalytics from './pages/BarAnalytics'
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
import OrgaEventHunts from './pages/OrgaEventHunts'
import OrgaEventBattles from './pages/OrgaEventBattles'
import SafetyAdmin from './pages/SafetyAdmin'
import ZonesAdmin from './pages/ZonesAdmin'
import Kitchen from './pages/Kitchen'
import BarDashboard from './pages/BarDashboard'
import CreateEventWizard from './pages/CreateEventWizard'
import EventQrPack from './pages/EventQrPack'
import StaffManagement from './pages/StaffManagement'
import OrgaBroadcast from './pages/OrgaBroadcast'
import OrgaIncidents from './pages/OrgaIncidents'
import OrgaProfitability from './pages/OrgaProfitability'
import OrgaEventSafety from './pages/OrgaEventSafety'
import OrgaEventMap from './pages/OrgaEventMap'
import AdminAuditGlobal from './pages/AdminAuditGlobal'
import AdminUsersGlobal from './pages/AdminUsersGlobal'
import AdminFlagsGlobal from './pages/AdminFlagsGlobal'
import CreateOrga from './pages/CreateOrga'
import OpenInApp from './pages/OpenInApp'
import PrintSharePack from './pages/PrintSharePack'

function RequireAuth({ children }: { children: React.ReactNode }) {
  const token = getToken()
  const location = useLocation()
  if (!token) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  return <>{children}</>
}

function RequireOrga({ children }: { children: React.ReactNode }) {
  if (!hasOrgaHubAccess()) return <Navigate to="/" replace />
  return <>{children}</>
}

function RequireOrgaManager({ children }: { children: React.ReactNode }) {
  if (!hasOrgaManagerAccess()) return <Navigate to="/" replace />
  return <>{children}</>
}

function RequireBarMode({ children }: { children: React.ReactNode }) {
  if (!hasBarModeAccess()) return <Navigate to="/" replace />
  return <>{children}</>
}

function RequireGlobalAdmin({ children }: { children: React.ReactNode }) {
  if (!hasGlobalAdmin()) return <Navigate to="/" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/open" element={<OpenInApp />} />
      <Route path="/share/event/:eventId/print" element={<PrintSharePack managed={false} />} />

      <Route
        path="/admin/audit"
        element={
          <RequireAuth>
            <RequireGlobalAdmin>
              <AdminAuditGlobal />
            </RequireGlobalAdmin>
          </RequireAuth>
        }
      />
      <Route
        path="/admin/users"
        element={
          <RequireAuth>
            <RequireGlobalAdmin>
              <AdminUsersGlobal />
            </RequireGlobalAdmin>
          </RequireAuth>
        }
      />
      <Route
        path="/admin/flags"
        element={
          <RequireAuth>
            <RequireGlobalAdmin>
              <AdminFlagsGlobal />
            </RequireGlobalAdmin>
          </RequireAuth>
        }
      />
      <Route
        path="/"
        element={
          <RequireAuth>
            <Dashboard />
          </RequireAuth>
        }
      />
      <Route
        path="/create-orga"
        element={
          <RequireAuth>
            <CreateOrga />
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
        path="/bar/events/:eventId/dashboard"
        element={
          <RequireAuth>
            <RequireBarMode>
              <BarDashboard />
            </RequireBarMode>
          </RequireAuth>
        }
      />
      <Route
        path="/bar/events/:eventId/menu"
        element={
          <RequireAuth>
            <RequireBarMode>
              <BarMenuAdmin />
            </RequireBarMode>
          </RequireAuth>
        }
      />
      <Route
        path="/bar/events/:eventId/orders"
        element={
          <RequireAuth>
            <RequireBarMode>
              <BarOrdersLive />
            </RequireBarMode>
          </RequireAuth>
        }
      />
      <Route
        path="/bar/events/:eventId/analytics"
        element={
          <RequireAuth>
            <RequireBarMode>
              <BarAnalytics />
            </RequireBarMode>
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
        path="/orga/events/:eventId/incidents"
        element={
          <RequireAuth>
            <RequireOrga>
              <OrgaIncidents />
            </RequireOrga>
          </RequireAuth>
        }
      />
      <Route
        path="/orga/events/:eventId/share-pack/print"
        element={
          <RequireAuth>
            <RequireOrga>
              <PrintSharePack managed={true} />
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
        path="/orga/events/:eventId/profitability"
        element={
          <RequireAuth>
            <RequireOrgaManager>
              <OrgaProfitability />
            </RequireOrgaManager>
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
        path="/orga/events/:eventId/wifi"
        element={
          <RequireAuth>
            <WifiAdmin />
          </RequireAuth>
        }
      />
      <Route
        path="/orga/events/:eventId/hunts"
        element={
          <RequireAuth>
            <RequireOrga>
              <OrgaEventHunts />
            </RequireOrga>
          </RequireAuth>
        }
      />
      <Route
        path="/orga/events/:eventId/map"
        element={
          <RequireAuth>
            <RequireOrga>
              <OrgaEventMap />
            </RequireOrga>
          </RequireAuth>
        }
      />
      <Route
        path="/orga/events/:eventId/safety"
        element={
          <RequireAuth>
            <RequireOrga>
              <OrgaEventSafety />
            </RequireOrga>
          </RequireAuth>
        }
      />
      <Route
        path="/orga/events/:eventId/battles"
        element={
          <RequireAuth>
            <RequireOrga>
              <OrgaEventBattles />
            </RequireOrga>
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
