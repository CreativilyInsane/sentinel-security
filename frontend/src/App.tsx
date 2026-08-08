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
                <Route path={ROUTES.NETWORK_SCAN} element={<Placeholder title="Network Scan" description="Initiate and configure new network scans across your infrastructure." />} />
                <Route path={ROUTES.PREVIOUS_SCANS} element={<Placeholder title="Previous Scans" description="Review historical scan data and vulnerability evolution." />} />
                <Route path={ROUTES.ASSETS} element={<Placeholder title="Assets" description="Manage and monitor all discovered assets in your environment." />} />
                <Route path={ROUTES.REPORTS} element={<Placeholder title="Reports" description="Generate, view, and export detailed security reports." />} />
                <Route path={ROUTES.PROFILE} element={<Placeholder title="Profile" description="Manage your account profile and preferences." />} />
                <Route path={ROUTES.SETTINGS} element={<Placeholder title="Settings" description="Configure system-wide settings and integrations." />} />
                
                {/* Admin Only Routes */}
                <Route element={<AdminRoute />}>
                  <Route path={ROUTES.USERS} element={<Users />} />
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