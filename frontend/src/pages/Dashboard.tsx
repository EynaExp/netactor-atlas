import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Plus, Play, Trash2, Shield, Activity, AlertTriangle,
  CheckCircle2, Clock, Server, ChevronRight
} from 'lucide-react';
import { listEngagements, deleteEngagement, runEngagement } from '../services/api';
import { Engagement } from '../types';
import { useLang } from '../i18n';

const statusColors: Record<string, string> = {
  created: 'bg-dark-700 text-dark-300',
  running: 'bg-neon-blue/20 text-neon-blue',
  completed: 'bg-neon-green/20 text-neon-green',
  failed: 'bg-neon-red/20 text-neon-red',
  paused: 'bg-yellow-500/20 text-yellow-400',
};

const statusIcons: Record<string, any> = {
  created: Clock,
  running: Activity,
  completed: CheckCircle2,
  failed: AlertTriangle,
  paused: Clock,
};

export default function Dashboard() {
  const { t } = useLang();
  const [engagements, setEngagements] = useState<Engagement[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    loadEngagements();
    const interval = setInterval(loadEngagements, 5000);
    return () => clearInterval(interval);
  }, []);

  const loadEngagements = async () => {
    try {
      const data = await listEngagements();
      setEngagements(data);
    } catch (e) {
      console.error('Failed to load engagements:', e);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (confirm('Delete this engagement?')) {
      await deleteEngagement(id);
      loadEngagements();
    }
  };

  const handleRun = async (id: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    await runEngagement(id, false, true);
    loadEngagements();
  };

  const stats = {
    total: engagements.length,
    running: engagements.filter(e => e.status === 'running').length,
    completed: engagements.filter(e => e.status === 'completed').length,
    failed: engagements.filter(e => e.status === 'failed').length,
  };

  return (
    <div className="h-full overflow-auto p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">{t('dashboard')}</h1>
          <p className="text-dark-400 mt-1">Monitor your penetration testing engagements</p>
        </div>
        <Link
          to="/new-scan"
          className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-gradient-to-r from-neon-blue to-cyber-600 text-white font-medium hover:shadow-lg hover:shadow-neon-blue/20 transition-all duration-200"
        >
          <Plus className="w-4 h-4" />
          {t('newScan')}
        </Link>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        {[
          { label: t('totalScans'), value: stats.total, icon: Server, color: 'text-dark-400' },
          { label: t('running'), value: stats.running, icon: Activity, color: 'text-neon-blue' },
          { label: t('completed'), value: stats.completed, icon: CheckCircle2, color: 'text-neon-green' },
          { label: 'Failed', value: stats.failed, icon: AlertTriangle, color: 'text-neon-red' },
        ].map((stat, i) => (
          <motion.div
            key={stat.label}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.1 }}
            className="glass-card rounded-xl p-4"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-dark-400 text-sm">{stat.label}</p>
                <p className={`text-2xl font-bold mt-1 ${stat.color}`}>{stat.value}</p>
              </div>
              <stat.icon className={`w-8 h-8 ${stat.color} opacity-30`} />
            </div>
          </motion.div>
        ))}
      </div>

      {/* Engagements List */}
      <div className="glass-card rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-dark-800/50">
          <h2 className="text-lg font-semibold text-white">{t('recentEngagements')}</h2>
        </div>

        {loading ? (
          <div className="p-12 text-center">
            <div className="w-8 h-8 border-2 border-neon-blue border-t-transparent rounded-full animate-spin mx-auto" />
            <p className="text-dark-400 mt-4">Loading engagements...</p>
          </div>
        ) : engagements.length === 0 ? (
          <div className="p-12 text-center">
            <Shield className="w-12 h-12 text-dark-700 mx-auto mb-4" />
            <p className="text-dark-400">{t('noEngagements')}</p>
            <Link to="/new-scan" className="text-neon-blue hover:underline text-sm mt-2 inline-block">
              {t('newScan')}
            </Link>
          </div>
        ) : (
          <div className="divide-y divide-dark-800/50">
            <AnimatePresence>
              {engagements.map((eng, i) => {
                const StatusIcon = statusIcons[eng.status] || Clock;
                return (
                  <motion.div
                    key={eng.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ delay: i * 0.05 }}
                  >
                    <Link
                      to={`/scan/${eng.id}`}
                      className="flex items-center justify-between px-6 py-4 hover:bg-dark-800/30 transition-colors group"
                    >
                      <div className="flex items-center gap-4 flex-1 min-w-0">
                        <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${statusColors[eng.status]}`}>
                          <StatusIcon className="w-5 h-5" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <h3 className="font-medium text-white truncate">{eng.name}</h3>
                            {eng.enable_exploit && (
                              <span className="px-1.5 py-0.5 text-xs rounded bg-neon-red/20 text-neon-red">EXPLOIT</span>
                            )}
                          </div>
                          <div className="flex items-center gap-3 mt-1 text-sm text-dark-400">
                            <span>{eng.target_scope.map(t => t.value).join(', ')}</span>
                            <span>•</span>
                            <span className="capitalize">{eng.current_phase || 'pending'}</span>
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        {eng.status === 'created' && (
                          <button
                            onClick={(e) => handleRun(eng.id, e)}
                            className="p-2 rounded-lg text-neon-green hover:bg-neon-green/10 transition-colors"
                            title="Start scan"
                          >
                            <Play className="w-4 h-4" />
                          </button>
                        )}
                        <button
                          onClick={(e) => handleDelete(eng.id, e)}
                          className="p-2 rounded-lg text-dark-500 hover:text-neon-red hover:bg-neon-red/10 transition-colors"
                          title="Delete"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                        <ChevronRight className="w-4 h-4 text-dark-600 group-hover:text-dark-400 transition-colors" />
                      </div>
                    </Link>
                  </motion.div>
                );
              })}
            </AnimatePresence>
          </div>
        )}
      </div>
    </div>
  );
}
