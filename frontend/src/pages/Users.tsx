import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Plus, Trash2, Users as UsersIcon, Shield, User as UserIcon, KeyRound, X, Check } from 'lucide-react';
import { listUsers, createUser, deleteUser, updateUser } from '../services/api';

interface AppUser {
  id: string;
  username: string;
  role: string;
  created_at?: string;
}

export default function Users() {
  const [users, setUsers] = useState<AppUser[]>([]);
  const [showAdd, setShowAdd] = useState(false);
  const [newUser, setNewUser] = useState({ username: '', password: '', role: 'user' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [editingPw, setEditingPw] = useState<string | null>(null);
  const [newPassword, setNewPassword] = useState('');

  const load = async () => {
    try {
      setUsers(await listUsers());
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleCreate = async () => {
    setError('');
    try {
      await createUser(newUser.username, newUser.password, newUser.role);
      setNewUser({ username: '', password: '', role: 'user' });
      setShowAdd(false);
      load();
    } catch (e: any) {
      setError(e.message.includes('400') ? 'Username already exists' : 'Failed to create user');
    }
  };

  const handleDelete = async (id: string) => {
    if (confirm('Delete this user?')) {
      try {
        await deleteUser(id);
        load();
      } catch (e) { console.error(e); }
    }
  };

  const handleRoleChange = async (id: string, role: string) => {
    try {
      await updateUser(id, { role });
      load();
    } catch (e) { console.error(e); }
  };

  const handlePasswordChange = async (id: string) => {
    if (!newPassword) return;
    try {
      await updateUser(id, { password: newPassword });
      setEditingPw(null);
      setNewPassword('');
    } catch (e) { console.error(e); }
  };

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-neon-blue border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto p-6">
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-3">
          <UsersIcon className="w-6 h-6 text-neon-blue" />
          <h1 className="text-2xl font-bold text-white">User Management</h1>
        </div>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-gradient-to-r from-neon-blue to-cyber-600 text-white font-medium hover:shadow-lg hover:shadow-neon-blue/20 transition-all"
        >
          <Plus className="w-4 h-4" />
          Add User
        </button>
      </div>

      {showAdd && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-card rounded-xl p-5 mb-6 max-w-md"
        >
          <h3 className="font-medium text-white mb-4">New User</h3>
          <div className="space-y-3">
            <input
              type="text"
              placeholder="Username"
              value={newUser.username}
              onChange={(e) => setNewUser({ ...newUser, username: e.target.value })}
              className="w-full px-4 py-2.5 rounded-lg bg-dark-900 border border-dark-700 text-white placeholder-dark-500 focus:border-neon-blue outline-none text-sm"
            />
            <input
              type="password"
              placeholder="Password"
              value={newUser.password}
              onChange={(e) => setNewUser({ ...newUser, password: e.target.value })}
              className="w-full px-4 py-2.5 rounded-lg bg-dark-900 border border-dark-700 text-white placeholder-dark-500 focus:border-neon-blue outline-none text-sm"
            />
            <select
              value={newUser.role}
              onChange={(e) => setNewUser({ ...newUser, role: e.target.value })}
              className="w-full px-4 py-2.5 rounded-lg bg-dark-900 border border-dark-700 text-white focus:border-neon-blue outline-none text-sm"
            >
              <option value="user">user (scanner only)</option>
              <option value="admin">admin (full access)</option>
            </select>
            {error && <p className="text-xs text-neon-red">{error}</p>}
            <button
              onClick={handleCreate}
              disabled={!newUser.username || !newUser.password}
              className="w-full py-2.5 rounded-lg bg-neon-blue/10 text-neon-blue border border-neon-blue/20 hover:bg-neon-blue/20 transition-colors text-sm disabled:opacity-50"
            >
              Create User
            </button>
          </div>
        </motion.div>
      )}

      <div className="glass-card rounded-xl overflow-hidden">
        <div className="divide-y divide-dark-800/50">
          {users.map((u) => (
            <div key={u.id} className="flex items-center justify-between px-6 py-4 hover:bg-dark-800/30 transition-colors">
              <div className="flex items-center gap-4">
                <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                  u.role === 'admin' ? 'bg-neon-blue/20 text-neon-blue' : 'bg-dark-700 text-dark-300'
                }`}>
                  {u.role === 'admin' ? <Shield className="w-5 h-5" /> : <UserIcon className="w-5 h-5" />}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-medium text-white">{u.username}</h3>
                    <span className={`px-1.5 py-0.5 text-[10px] rounded uppercase ${
                      u.role === 'admin' ? 'bg-neon-blue/20 text-neon-blue' : 'bg-dark-700 text-dark-400'
                    }`}>
                      {u.role}
                    </span>
                  </div>
                  <p className="text-xs text-dark-500 mt-0.5">
                    {u.role === 'admin' ? 'Full access: agents, settings, users' : 'Scanner only'}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {editingPw === u.id && (
                  <div className="flex items-center gap-1.5">
                    <input
                      type="password"
                      placeholder="New password"
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      autoFocus
                      className="px-3 py-1.5 rounded-lg bg-dark-900 border border-dark-700 text-white text-xs outline-none focus:border-neon-blue w-40"
                      onKeyDown={(e) => e.key === 'Enter' && handlePasswordChange(u.id)}
                    />
                    <button
                      onClick={() => handlePasswordChange(u.id)}
                      disabled={!newPassword}
                      className="p-1.5 rounded-lg text-neon-green hover:bg-neon-green/10 disabled:opacity-30"
                    >
                      <Check className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => { setEditingPw(null); setNewPassword(''); }}
                      className="p-1.5 rounded-lg text-dark-400 hover:text-white"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                )}
                {editingPw !== u.id && (
                  <>
                    <button
                      onClick={() => setEditingPw(u.id)}
                      className="p-2 rounded-lg text-dark-500 hover:text-neon-blue hover:bg-neon-blue/10 transition-colors"
                      title="Change password"
                    >
                      <KeyRound className="w-4 h-4" />
                    </button>
                    <select
                      value={u.role}
                      onChange={(e) => handleRoleChange(u.id, e.target.value)}
                      disabled={u.username === 'admin'}
                      className="px-2 py-1.5 rounded-lg bg-dark-900 border border-dark-700 text-white text-xs outline-none disabled:opacity-40"
                    >
                      <option value="user">user</option>
                      <option value="admin">admin</option>
                    </select>
                    <button
                      onClick={() => handleDelete(u.id)}
                      disabled={u.username === 'admin'}
                      className="p-2 rounded-lg text-dark-500 hover:text-neon-red hover:bg-neon-red/10 transition-colors disabled:opacity-30"
                      title="Delete user"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
