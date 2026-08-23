// frontend/src/components/layout/Sidebar.tsx
import { NavLink } from 'react-router-dom';
import {
  HomeIcon,
  SignalIcon,
  ClockIcon,
  ServerStackIcon,
  DocumentChartBarIcon,
  UsersIcon,
  Cog6ToothIcon,
  ArrowLeftOnRectangleIcon,
  ShieldCheckIcon,
  BuildingOffice2Icon,
  Squares2X2Icon,
  ClipboardDocumentCheckIcon,
} from '@heroicons/react/24/outline';
import { useAuth } from '@/context/AuthContext';
import { useUnreadCount } from '@/hooks/useClients';
import { ROUTES } from '@/routes/paths';
import { cn } from '@/utils/cn';

export const Sidebar = () => {
  const { user, logout } = useAuth();
  const isAdmin = user?.role.name === 'Administrator';

  // Unread assignment count for the Targets badge (only relevant for users)
  const { data: unreadCount } = useUnreadCount();

  // Role-aware navigation.  Admin sees Clients; users see Targets.
  const navItems = isAdmin
    ? [
        { name: 'Dashboard', path: ROUTES.DASHBOARD, icon: HomeIcon },
        { name: 'Clients', path: ROUTES.CLIENTS, icon: BuildingOffice2Icon },
        { name: 'Network Scan', path: ROUTES.NETWORK_SCAN, icon: SignalIcon },
        { name: 'Previous Scans', path: ROUTES.PREVIOUS_SCANS, icon: ClockIcon },
        { name: 'Assets', path: ROUTES.ASSETS, icon: ServerStackIcon },
        { name: 'Reports', path: ROUTES.REPORTS, icon: DocumentChartBarIcon },
      ]
    : [
        { name: 'Dashboard', path: ROUTES.DASHBOARD, icon: HomeIcon },
        { name: 'Targets', path: ROUTES.TARGETS, icon: Squares2X2Icon, badge: unreadCount },
        { name: 'Network Scan', path: ROUTES.NETWORK_SCAN, icon: SignalIcon },
        { name: 'Previous Scans', path: ROUTES.PREVIOUS_SCANS, icon: ClockIcon },
        { name: 'Assets', path: ROUTES.ASSETS, icon: ServerStackIcon },
        { name: 'Reports', path: ROUTES.REPORTS, icon: DocumentChartBarIcon },
      ];

  return (
    <aside className="fixed top-0 left-0 z-40 h-screen w-64 glass-panel border-r border-dark-800 transition-transform -translate-x-full sm:translate-x-0">
      <div className="h-full flex flex-col">
        {/* Logo / Header */}
        <div className="flex items-center justify-center h-16 border-b border-dark-800 px-4">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 bg-gradient-cyber rounded-lg flex items-center justify-center shadow-glow">
              <ShieldCheckIcon className="w-5 h-5 text-white" />
            </div>
            <span className="text-lg font-display font-semibold text-gradient-cyber">SecureScan</span>
          </div>
        </div>

        {/* Navigation Links */}
        <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-1">
          {navItems.map((item) => (
            <NavLink
              key={item.name}
              to={item.path}
              className={({ isActive }) =>
                cn(
                  'group relative flex items-center px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200',
                  isActive
                    ? 'bg-primary-500/10 text-primary-300 border border-primary-500/30 shadow-glow-sm'
                    : 'text-dark-400 hover:text-dark-100 hover:bg-dark-800/70 border border-transparent',
                )
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <span className="absolute left-0 top-1/2 -translate-y-1/2 h-4 w-0.5 rounded-full bg-primary-400 shadow-glow-sm" />
                  )}
                  <item.icon className={cn('w-5 h-5 mr-3 transition-colors', isActive ? 'text-primary-400' : 'group-hover:text-primary-400')} />
                  <span className="flex-1">{item.name}</span>
                  {(item as any).badge ? (
                    <span className="ml-2 inline-flex items-center justify-center min-w-[1.25rem] h-5 px-1.5 text-[10px] font-bold rounded-full bg-primary-500/20 text-primary-200 border border-primary-500/40">
                      {(item as any).badge}
                    </span>
                  ) : null}
                </>
              )}
            </NavLink>
          ))}

          {/* Admin Only Section */}
          {isAdmin && (
            <div className="pt-4">
              <div className="pb-2 px-3 text-xs font-semibold text-dark-500 uppercase tracking-widest">
                Administration
              </div>
              <NavLink
                to={ROUTES.ASSIGNMENTS}
                className={({ isActive }) =>
                  cn(
                    'group relative flex items-center px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200',
                    isActive
                      ? 'bg-primary-500/10 text-primary-300 border border-primary-500/30 shadow-glow-sm'
                      : 'text-dark-400 hover:text-dark-100 hover:bg-dark-800/70 border border-transparent',
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    {isActive && (
                      <span className="absolute left-0 top-1/2 -translate-y-1/2 h-4 w-0.5 rounded-full bg-primary-400 shadow-glow-sm" />
                    )}
                    <ClipboardDocumentCheckIcon className={cn('w-5 h-5 mr-3 transition-colors', isActive ? 'text-primary-400' : 'group-hover:text-primary-400')} />
                    Assignments
                  </>
                )}
              </NavLink>
              <NavLink
                to={ROUTES.USERS}
                className={({ isActive }) =>
                  cn(
                    'group relative flex items-center px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200',
                    isActive
                      ? 'bg-primary-500/10 text-primary-300 border border-primary-500/30 shadow-glow-sm'
                      : 'text-dark-400 hover:text-dark-100 hover:bg-dark-800/70 border border-transparent',
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    {isActive && (
                      <span className="absolute left-0 top-1/2 -translate-y-1/2 h-4 w-0.5 rounded-full bg-primary-400 shadow-glow-sm" />
                    )}
                    <UsersIcon className={cn('w-5 h-5 mr-3 transition-colors', isActive ? 'text-primary-400' : 'group-hover:text-primary-400')} />
                    Users
                  </>
                )}
              </NavLink>
            </div>
          )}
        </nav>

        {/* Bottom Section */}
        <div className="p-3 border-t border-dark-800 space-y-1">
          <NavLink
            to={ROUTES.SETTINGS}
            className={({ isActive }) =>
              cn(
                'flex items-center px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200',
                isActive
                  ? 'bg-primary-500/10 text-primary-300'
                  : 'text-dark-400 hover:text-dark-100 hover:bg-dark-800/70',
              )
            }
          >
            <Cog6ToothIcon className="w-5 h-5 mr-3" />
            Settings
          </NavLink>
          <button
            onClick={logout}
            className="w-full flex items-center px-3 py-2.5 rounded-xl text-sm font-medium text-dark-400 hover:text-red-400 hover:bg-dark-800/70 transition-all duration-200"
          >
            <ArrowLeftOnRectangleIcon className="w-5 h-5 mr-3" />
            Logout
          </button>
        </div>
      </div>
    </aside>
  );
};
