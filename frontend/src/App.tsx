// frontend/src/App.tsx
import { Routes, Route } from 'react-router-dom'
import { ToastProvider } from '@/context/ToastContext'
import { AuthProvider } from '@/context/AuthContext'
import { ThemeProvider } from '@/context/ThemeContext'
import { ProtectedRoute } from '@/components/protected/ProtectedRoute'
import { AdminRoute } from '@/components/protected/AdminRoute'
import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { AmbientBackground } from '@/components/ui/AmbientBackground'
import { ThemeSwitcher } from '@/components/ui/ThemeSwitcher'
import { Login } from '@/pages/Login'
import { Dashboard } from '@/pages/Dashboard'
import { Users } from '@/pages/Users'
import { UserModuleSettings } from '@/pages/UserModuleSettings'
import { NetworkScan } from '@/pages/NetworkScan'
import { ScanDetails } from '@/pages/ScanDetails'
import { PreviousScans } from '@/pages/PreviousScans'
import { Assets } from '@/pages/Assets'
import { AssetDetails } from '@/pages/AssetDetails'
import { Reports } from '@/pages/Reports'
import { Clients } from '@/pages/Clients'
import { ClientDetail } from '@/pages/ClientDetail'
import { Assignments } from '@/pages/Assignments'
import { Targets } from '@/pages/Targets'
import { Settings } from '@/pages/Settings'
import { Placeholder } from '@/pages/Placeholders'
import { NotFound } from '@/pages/NotFound'
import { ROUTES } from '@/routes/paths'

function App() {
  return (
    <ThemeProvider>
      <ToastProvider>
        <AuthProvider>
          <AmbientBackground />
          <Routes>
            {/* Public Routes */}
            <Route path="/login" element={<Login />} />

            {/* Protected Routes */}
            <Route element={<ProtectedRoute />}>
              <Route element={<DashboardLayout />}>
                <Route path={ROUTES.DASHBOARD} element={<Dashboard />} />
                <Route path={ROUTES.NETWORK_SCAN} element={<NetworkScan />} />
                <Route path={ROUTES.SCAN_DETAILS} element={<ScanDetails />} />
                <Route path={ROUTES.PREVIOUS_SCANS} element={<PreviousScans />} />
                <Route path={ROUTES.ASSETS} element={<Assets />} />
                <Route path={ROUTES.ASSETS_BY_HOST} element={<AssetDetails />} />
                <Route path={ROUTES.REPORTS} element={<Reports />} />
                <Route path={ROUTES.TARGETS} element={<Targets />} />
                <Route path={ROUTES.PROFILE} element={<Placeholder title="Profile" description="Manage your account profile and preferences." />} />
                <Route path={ROUTES.SETTINGS} element={<Settings />} />

                {/* Admin Only Routes */}
                <Route element={<AdminRoute />}>
                  <Route path={ROUTES.CLIENTS} element={<Clients />} />
                  <Route path={ROUTES.CLIENT_DETAIL} element={<ClientDetail />} />
                  <Route path={ROUTES.ASSIGNMENTS} element={<Assignments />} />
                  <Route path={ROUTES.USERS} element={<Users />} />
                  <Route path={ROUTES.USER_MODULE_SETTINGS} element={<UserModuleSettings />} />
                </Route>

                {/* 404 */}
                <Route path="*" element={<NotFound />} />
              </Route>
            </Route>
          </Routes>
          <ThemeSwitcher />
        </AuthProvider>
      </ToastProvider>
    </ThemeProvider>
  )
}

export default App
