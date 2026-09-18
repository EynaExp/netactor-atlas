import { BrowserRouter, Routes, Route, NavLink, useNavigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import {
  LayoutDashboard, Plus, Settings, Shield, Activity, Users as UsersIcon, Wrench, History, KeyRound, X,
  ChevronLeft, ChevronRight, Terminal, Globe, LogOut, Server
} from 'lucide-react';
import Dashboard from './pages/Dashboard';
import NewScan from './pages/NewScan';
import ScanDetail from './pages/ScanDetail';
import Agents from './pages/Agents';
import SettingsPage from './pages/Settings';
import Users from './pages/Users';
import Audit from './pages/Audit';
import Tools from './pages/Tools';
import Assets from './pages/Assets';
import Login from './pages/Login';
import { LanguageProvider, useLang } from './i18n';
import { getToken, getMe, onUnauthorized, changePassword } from './services/api';

function Shell({ role, username, onLogout }: { role: string; username: string; onLogout: () => void }) {
  const [collapsed, setCollapsed] = useState(false);
  const { lang, setLang, t } = useLang();
  const isAdmin = role === 'admin';
  const [pwOpen, setPwOpen] = useState(false);
  const [pwOld, setPwOld] = useState('');
  const [pwNew, setPwNew] = useState('');
  const [pwMsg, setPwMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [pwSaving, setPwSaving] = useState(false);

  const submitPassword = async () => {
    setPwSaving(true);
    setPwMsg(null);
    try {
      await changePassword(pwOld, pwNew);
      setPwMsg({ ok: true, text: 'Password changed' });
      setPwOld(''); setPwNew('');
      setTimeout(() => setPwOpen(false), 1200);
    } catch (e: any) {
      const txt = e.message || '';
      setPwMsg({ ok: false, text: txt.includes('incorrect') ? 'Current password is incorrect' : txt.includes('6 characters') ? 'New password must be at least 6 characters' : 'Failed to change password' });
    } finally { setPwSaving(false); }
  };

  const navItems = [
    { path: '/', icon: LayoutDashboard, key: 'dashboard', show: true },
    { path: '/new-scan', icon: Plus, key: 'newScan', show: true },
    { path: '/assets', icon: Server, key: 'assets', show: true },
    { path: '/agents', icon: Shield, key: 'agents', show: isAdmin },
    { path: '/tools', icon: Wrench, key: 'tools', show: isAdmin },
    { path: '/users', icon: UsersIcon, key: 'users', show: isAdmin },
    { path: '/settings', icon: Settings, key: 'settings', show: isAdmin },
    { path: '/audit', icon: History, key: 'audit', show: isAdmin },
  ].filter(i => i.show);

  return (
    <div className="flex h-screen bg-dark-950 overflow-hidden">
      {/* Sidebar */}
      <aside
        className={`relative flex flex-col border-r border-dark-800/50 bg-dark-950 transition-all duration-300 ${
          collapsed ? 'w-16' : 'w-60'
        }`}
      >
        {/* Logo */}
        <div className="flex items-center gap-3 px-4 h-16 border-b border-dark-800/50">
          <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-gradient-to-br from-neon-blue to-cyber-600 shrink-0">
            <Terminal className="w-5 h-5 text-white" />
          </div>
          {!collapsed && (
            <span className="text-lg font-bold gradient-text">NetActor</span>
          )}
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-4 px-2 space-y-1 overflow-auto">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 ${
                  isActive
                    ? 'bg-neon-blue/10 text-neon-blue border border-neon-blue/20'
                    : 'text-dark-400 hover:text-dark-200 hover:bg-dark-800/50'
                } ${collapsed ? 'justify-center' : ''}`
              }
            >
              <item.icon className="w-5 h-5 flex-shrink-0" />
              {!collapsed && <span className="text-sm font-medium">{t(item.key)}</span>}
            </NavLink>
          ))}
        </nav>

        {/* Language toggle */}
        <div className={`px-4 py-2 ${collapsed ? 'px-2' : ''}`}>
          <button
            onClick={() => setLang(lang === 'en' ? 'fa' : 'en')}
            className={`flex items-center gap-2 text-dark-400 hover:text-neon-blue transition-colors ${
              collapsed ? 'justify-center' : ''
            }`}
            title={t('language')}
          >
            <Globe className="w-4 h-4 shrink-0" />
            {!collapsed && (
              <span className="text-xs font-medium">
                {lang === 'en' ? 'فارسی' : 'English'}
              </span>
            )}
          </button>
        </div>

        {/* User info + logout */}
        <div className={`px-4 py-2 border-t border-dark-800/50 ${collapsed ? 'px-2' : ''}`}>
          <div className={`flex items-center gap-2 ${collapsed ? 'justify-center' : ''}`}>
            <div className="w-6 h-6 rounded-full bg-neon-blue/20 text-neon-blue flex items-center justify-center shrink-0">
              <span className="text-xs font-bold uppercase">{username[0]}</span>
            </div>
            {!collapsed && (
              <div className="min-w-0 flex-1">
                <p className="text-xs text-white truncate">{username}</p>
                <p className="text-[10px] text-dark-500 capitalize">{role}</p>
              </div>
            )}
            <button
              onClick={() => setPwOpen(true)}
              className="p-1.5 rounded-lg text-dark-400 hover:text-neon-blue hover:bg-neon-blue/10 transition-colors shrink-0"
              title="Change password"
            >
              <KeyRound className="w-4 h-4" />
            </button>
            <button
              onClick={onLogout}
              className="p-1.5 rounded-lg text-dark-400 hover:text-neon-red hover:bg-neon-red/10 transition-colors shrink-0"
              title="Logout"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Status indicator */}
        <div className={`px-4 py-2 ${collapsed ? 'px-2' : ''}`}>
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-neon-green animate-pulse" />
            {!collapsed && (
              <span className="text-xs text-dark-400">{t('systemOnline')}</span>
            )}
          </div>
        </div>

        {/* Collapse toggle */}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="absolute top-1/2 -right-3 w-6 h-6 rounded-full bg-dark-800 border border-dark-700 flex items-center justify-center text-dark-400 hover:text-white hover:bg-dark-700 transition-colors"
        >
          {collapsed ? <ChevronRight className="w-3 h-3" /> : <ChevronLeft className="w-3 h-3" />}
        </button>
      </aside>

      {/* Change password modal */}
      {pwOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={() => setPwOpen(false)}>
          <div className="glass-card rounded-2xl p-6 w-full max-w-sm mx-4" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <KeyRound className="w-4 h-4 text-neon-blue" />
                <h3 className="font-semibold text-white">Change Password</h3>
              </div>
              <button onClick={() => setPwOpen(false)} className="p-1 rounded-lg text-dark-400 hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="space-y-3">
              <input
                type="password"
                placeholder="Current password"
                value={pwOld}
                onChange={(e) => setPwOld(e.target.value)}
                autoFocus
                className="w-full px-4 py-2.5 rounded-lg bg-dark-900 border border-dark-700 text-white placeholder-dark-500 focus:border-neon-blue outline-none text-sm"
              />
              <input
                type="password"
                placeholder="New password (min 6 chars)"
                value={pwNew}
                onChange={(e) => setPwNew(e.target.value)}
                className="w-full px-4 py-2.5 rounded-lg bg-dark-900 border border-dark-700 text-white placeholder-dark-500 focus:border-neon-blue outline-none text-sm"
              />
              {pwMsg && (
                <p className={`text-xs ${pwMsg.ok ? 'text-neon-green' : 'text-neon-red'}`}>{pwMsg.text}</p>
              )}
              <button
                onClick={submitPassword}
                disabled={!pwOld || !pwNew || pwSaving}
                className="w-full py-2.5 rounded-lg bg-neon-blue/10 text-neon-blue border border-neon-blue/20 hover:bg-neon-blue/20 transition-colors text-sm disabled:opacity-50"
              >
                {pwSaving ? 'Saving...' : 'Change Password'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Main content */}
      <main className="flex-1 overflow-hidden">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/new-scan" element={<NewScan />} />
          <Route path="/scan/:id" element={<ScanDetail />} />
          <Route path="/assets" element={<Assets />} />
          <Route path="/agents" element={isAdmin ? <Agents /> : <Dashboard />} />
          <Route path="/users" element={isAdmin ? <Users /> : <Dashboard />} />
          <Route path="/audit" element={isAdmin ? <Audit /> : <Dashboard />} />
          <Route path="/tools" element={isAdmin ? <Tools /> : <Dashboard />} />
          <Route path="/settings" element={isAdmin ? <SettingsPage /> : <Dashboard />} />
        </Routes>
      </main>
    </div>
  );
}

function Root() {
  const [authState, setAuthState] = useState<'loading' | 'guest' | 'authed'>('loading');
  const [role, setRole] = useState('user');
  const [username, setUsername] = useState('');
  const navigate = useNavigate();
  const forceLogout = () => {
    setAuthState('guest');
    navigate('/');
  };

  useEffect(() => {
    onUnauthorized(forceLogout);
    const check = async () => {
      const token = getToken();
      if (!token) {
        setAuthState('guest');
        return;
      }
      try {
        const me = await getMe();
        setRole(me.role);
        setUsername(me.username);
        setAuthState('authed');
      } catch {
        setAuthState('guest');
      }
    };
    check();
  }, []);

  if (authState === 'loading') {
    return (
      <div className="h-screen flex items-center justify-center bg-dark-950">
        <div className="w-8 h-8 border-2 border-neon-blue border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (authState === 'guest') {
    return (
      <Login
        onSuccess={() => {
          // re-fetch username after login
          getMe().then(me => {
            setRole(me.role);
            setUsername(me.username);
            setAuthState('authed');
          }).catch(() => setAuthState('guest'));
        }}
      />
    );
  }

  const handleLogout = () => {
    localStorage.removeItem('netactor_token');
    setAuthState('guest');
  };

  return <Shell role={role} username={username} onLogout={handleLogout} />;
}

export default function App() {
  return (
    <LanguageProvider>
      <BrowserRouter>
        <Root />
      </BrowserRouter>
    </LanguageProvider>
  );
}
