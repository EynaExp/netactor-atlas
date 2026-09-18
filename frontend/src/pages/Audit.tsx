import { useEffect, useState } from 'react';
import { History, LogIn } from 'lucide-react';
import { getAuditLogs } from '../services/api';

const actionColors: Record<string, string> = {
  login: 'bg-dark-700 text-dark-300',
  scan_start: 'bg-neon-blue/20 text-neon-blue',
  scan_stop: 'bg-neon-yellow/20 text-neon-yellow',
  scan_retry: 'bg-neon-purple/20 text-neon-purple',
  tool_toggle: 'bg-neon-orange/20 text-neon-orange',
  agent_config_update: 'bg-neon-purple/20 text-neon-purple',
  llm_settings_update: 'bg-neon-purple/20 text-neon-purple',
  user_create: 'bg-neon-green/20 text-neon-green',
  user_delete: 'bg-neon-red/20 text-neon-red',
  user_update: 'bg-neon-yellow/20 text-neon-yellow',
  password_change: 'bg-neon-red/20 text-neon-red',
  engagement_delete: 'bg-neon-red/20 text-neon-red',
};

export default function Audit() {
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getAuditLogs().then(setLogs).catch(console.error).finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-neon-blue border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto p-6">
      <div className="flex items-center gap-3 mb-8">
        <History className="w-6 h-6 text-neon-blue" />
        <div>
          <h1 className="text-2xl font-bold text-white">Audit Log</h1>
          <p className="text-dark-400 text-sm mt-0.5">Security-relevant actions across the platform</p>
        </div>
      </div>

      <div className="glass-card rounded-xl overflow-hidden max-w-4xl">
        {logs.length === 0 ? (
          <p className="p-10 text-center text-dark-400">No audit events yet</p>
        ) : (
          <div className="divide-y divide-dark-800/50">
            {logs.map(log => (
              <div key={log.id} className="flex items-center gap-4 px-5 py-3 hover:bg-dark-800/30 transition-colors">
                <div className="w-8 h-8 rounded-lg bg-dark-800 flex items-center justify-center shrink-0">
                  <LogIn className="w-4 h-4 text-dark-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-white text-sm">{log.username}</span>
                    <span className={`px-1.5 py-0.5 text-[10px] rounded uppercase font-mono ${actionColors[log.action] || 'bg-dark-700 text-dark-300'}`}>
                      {log.action}
                    </span>
                  </div>
                  {log.details && Object.keys(log.details).length > 0 && (
                    <p className="text-xs text-dark-500 mt-0.5 truncate font-mono">
                      {JSON.stringify(log.details)}
                    </p>
                  )}
                </div>
                <span className="text-xs text-dark-500 shrink-0">
                  {log.created_at ? new Date(log.created_at + 'Z').toLocaleString() : ''}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
