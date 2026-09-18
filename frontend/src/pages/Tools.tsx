import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Wrench, Search, Zap, Network, Shield, Globe, Radar } from 'lucide-react';
import { getToolStates, setToolState } from '../services/api';

const toolIcons: Record<string, any> = {
  nmap: Search,
  masscan: Radar,
  nxc: Network,
  searchsploit: Zap,
  adscan: Shield,
  adpeas: Shield,
  curl: Globe,
};

interface ToolState {
  tool_name: string;
  enabled: boolean;
  description?: string;
  category?: string;
}

export default function Tools() {
  const [tools, setTools] = useState<ToolState[]>([]);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState<string | null>(null);

  const load = async () => {
    try {
      setTools(await getToolStates());
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleToggle = async (name: string, enabled: boolean) => {
    setUpdating(name);
    try {
      await setToolState(name, enabled);
      setTools(prev => prev.map(t => t.tool_name === name ? { ...t, enabled } : t));
    } catch (e) {
      console.error(e);
    } finally {
      setUpdating(null);
    }
  };

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-neon-blue border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const enabledCount = tools.filter(t => t.enabled).length;

  return (
    <div className="h-full overflow-auto p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-3">
          <Wrench className="w-6 h-6 text-neon-blue" />
          <div>
            <h1 className="text-2xl font-bold text-white">Tool Management</h1>
            <p className="text-dark-400 text-sm mt-0.5">
              {enabledCount} of {tools.length} tools enabled — disabled tools are hidden from AI agents and blocked at execution
            </p>
          </div>
        </div>
      </div>

      {/* Tools grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-5xl">
        {tools.map((tool, i) => {
          const Icon = toolIcons[tool.tool_name] || Wrench;
          return (
            <motion.div
              key={tool.tool_name}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              className={`glass-card rounded-xl p-5 transition-all ${
                tool.enabled ? '' : 'opacity-60'
              }`}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-3 flex-1 min-w-0">
                  <div className={`w-10 h-10 rounded-lg flex items-center justify-center shrink-0 ${
                    tool.enabled ? 'bg-neon-blue/20 text-neon-blue' : 'bg-dark-700 text-dark-500'
                  }`}>
                    <Icon className="w-5 h-5" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className="font-medium text-white font-mono">{tool.tool_name}</h3>
                      {tool.category && (
                        <span className="px-1.5 py-0.5 text-[10px] rounded uppercase bg-dark-700 text-dark-400">
                          {tool.category}
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-dark-400 mt-1 leading-relaxed">
                      {tool.description}
                    </p>
                  </div>
                </div>

                {/* Toggle */}
                <button
                  onClick={() => handleToggle(tool.tool_name, !tool.enabled)}
                  disabled={updating === tool.tool_name}
                  className={`relative w-12 h-6 rounded-full transition-colors shrink-0 mt-1 ${
                    tool.enabled ? 'bg-neon-blue' : 'bg-dark-700'
                  } ${updating === tool.tool_name ? 'opacity-50' : ''}`}
                  title={tool.enabled ? 'Disable tool' : 'Enable tool'}
                >
                  {updating === tool.tool_name ? (
                    <div className="absolute inset-0 flex items-center justify-center">
                      <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    </div>
                  ) : (
                    <div
                      className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${
                        tool.enabled ? 'translate-x-7' : 'translate-x-1'
                      }`}
                    />
                  )}
                </button>
              </div>
            </motion.div>
          );
        })}
      </div>

      {/* Info note */}
      <div className="mt-6 max-w-5xl p-4 rounded-lg bg-neon-blue/5 border border-neon-blue/10">
        <p className="text-xs text-dark-400 leading-relaxed">
          Disabling a tool immediately removes it from the AI agents' available tools and any in-flight
          calls to it are rejected. Running scans are affected on their next tool call.
        </p>
      </div>
    </div>
  );
}
