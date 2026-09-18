import { useState } from 'react';
import { motion } from 'framer-motion';
import { Terminal, Lock, User as UserIcon, LogIn, AlertCircle } from 'lucide-react';
import { login } from '../services/api';

export default function Login({ onSuccess }: { onSuccess: (role: string) => void }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const data = await login(username, password);
      onSuccess(data.role);
    } catch (err: any) {
      setError(err.message.includes('401') || err.message.includes('Invalid')
        ? 'نام کاربری یا رمز عبور اشتباه است / Invalid credentials'
        : 'Connection error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-screen w-screen flex items-center justify-center bg-dark-950 relative overflow-hidden">
      {/* Background glow */}
      <div className="absolute inset-0 opacity-40"
        style={{
          background: 'radial-gradient(ellipse at 50% 0%, rgba(59,141,255,0.15) 0%, transparent 60%)'
        }}
      />
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="glass-card rounded-2xl p-8 w-full max-w-sm relative z-10"
      >
        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-neon-blue to-cyber-600 flex items-center justify-center mb-4 glow-blue">
            <Terminal className="w-7 h-7 text-white" />
          </div>
          <h1 className="text-2xl font-bold gradient-text">NetActor</h1>
          <p className="text-dark-400 text-sm mt-1">AI Penetration Testing Platform</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="relative">
            <UserIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-500" />
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Username"
              autoFocus
              className="w-full pl-10 pr-4 py-3 rounded-lg bg-dark-900 border border-dark-700 text-white placeholder-dark-500 focus:border-neon-blue focus:ring-1 focus:ring-neon-blue/30 outline-none transition-all text-sm"
            />
          </div>
          <div className="relative">
            <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-500" />
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Password"
              className="w-full pl-10 pr-4 py-3 rounded-lg bg-dark-900 border border-dark-700 text-white placeholder-dark-500 focus:border-neon-blue focus:ring-1 focus:ring-neon-blue/30 outline-none transition-all text-sm"
            />
          </div>

          {error && (
            <div className="flex items-start gap-2 p-3 rounded-lg bg-neon-red/10 border border-neon-red/20">
              <AlertCircle className="w-4 h-4 text-neon-red mt-0.5 shrink-0" />
              <p className="text-xs text-neon-red/90">{error}</p>
            </div>
          )}

          <button
            type="submit"
            disabled={!username || !password || loading}
            className="w-full py-3 rounded-lg bg-gradient-to-r from-neon-blue to-cyber-600 text-white font-semibold hover:shadow-lg hover:shadow-neon-blue/20 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {loading ? (
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
            ) : (
              <>
                <LogIn className="w-4 h-4" />
                Sign In
              </>
            )}
          </button>
        </form>
      </motion.div>
    </div>
  );
}
