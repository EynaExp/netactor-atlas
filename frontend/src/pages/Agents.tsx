import { useEffect, useState } from 'react';
import {
  Save, Terminal, Eye, EyeOff, ChevronRight
} from 'lucide-react';
import { getAgentConfigs, updateAgentConfig, getToolStates } from '../services/api';
import { Wrench } from 'lucide-react';
import { AgentConfig } from '../types';
import { useLang } from '../i18n';

const agentIcons: Record<string, string> = {
  recon: '🔍',
  scanner: '🛡️',
  vuln_analyzer: '📊',
  exploit: '⚡',
  report: '📝',
};

export default function Agents() {
  const { t } = useLang();
  const [configs, setConfigs] = useState<AgentConfig[]>([]);
  const [selected, setSelected] = useState<string>('recon');
  const [editPrompt, setEditPrompt] = useState('');
  const [editTemp, setEditTemp] = useState(0.7);
  const [editMaxTokens, setEditMaxTokens] = useState(4096);
  const [editEnabled, setEditEnabled] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editAllowed, setEditAllowed] = useState<string[] | null>(null);

  // Effective per-agent allowed tools (null = all global tools allowed)
  const effectiveAllowed = (agentType: string): string[] => {
    const cfg = configs.find(c => c.agent_type === agentType);
    const all = toolStates.map(t => t.tool_name);
    if (!cfg || cfg.allowed_tools == null) return all;
    return cfg.allowed_tools.filter(t => all.includes(t));
  };
  const [loading, setLoading] = useState(true);
  const [toolStates, setToolStates] = useState<{ tool_name: string; enabled: boolean; description?: string }[]>([]);

  useEffect(() => {
    loadConfigs();
  }, []);

  useEffect(() => {
    const config = configs.find(c => c.agent_type === selected);
    if (config) {
      setEditPrompt(config.system_prompt);
      setEditTemp(config.temperature);
      setEditMaxTokens(config.max_tokens);
      setEditEnabled(config.enabled);
      setEditAllowed(config.allowed_tools ?? null);
    }
  }, [selected, configs]);

  const loadConfigs = async () => {
    try {
      const [data, tools] = await Promise.all([getAgentConfigs(), getToolStates()]);
      setConfigs(data);
      setToolStates(tools);
    } catch (e) {
      console.error('Failed to load configs:', e);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateAgentConfig(selected, {
        system_prompt: editPrompt,
        temperature: editTemp,
        max_tokens: editMaxTokens,
        enabled: editEnabled,
        allowed_tools: editAllowed,
      } as any);
      await loadConfigs();
    } catch (e) {
      console.error('Failed to save config:', e);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-neon-blue border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="h-full flex overflow-hidden">
      {/* Agent list sidebar */}
      <div className="w-64 border-r border-dark-800/50 bg-dark-950/50 p-4 flex flex-col overflow-hidden">
        <h2 className="text-lg font-semibold text-white mb-4">{t('agents')}</h2>
        <div className="space-y-2 overflow-auto">
          {configs.map(config => (
            <button
              key={config.agent_type}
              onClick={() => setSelected(config.agent_type)}
              className={`w-full flex items-center gap-3 p-3 rounded-xl transition-all text-left ${
                selected === config.agent_type
                  ? 'bg-neon-blue/10 border border-neon-blue/20'
                  : 'hover:bg-dark-800/50 border border-transparent'
              }`}
            >
              <span className="text-xl shrink-0">{agentIcons[config.agent_type] || '🤖'}</span>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-white capitalize truncate">
                    {config.agent_type.replace('_', ' ')}
                  </span>
                  {!config.enabled && (
                    <EyeOff className="w-3 h-3 text-dark-500 shrink-0" />
                  )}
                </div>
                <p className="text-[11px] text-dark-500 mt-0.5 leading-tight">
                  {config.agent_type === 'recon' && t('agentDescRecon')}
                  {config.agent_type === 'scanner' && t('agentDescScanner')}
                  {config.agent_type === 'vuln_analyzer' && t('agentDescAnalyzer')}
                  {config.agent_type === 'exploit' && t('agentDescExploit')}
                  {config.agent_type === 'report' && t('agentDescReport')}
                </p>
              </div>
              <ChevronRight className="w-4 h-4 text-dark-600 shrink-0" />
            </button>
          ))}
        </div>
      </div>

      {/* Editor */}
      <div className="flex-1 flex flex-col overflow-hidden p-6">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <span className="text-2xl">{agentIcons[selected] || '🤖'}</span>
            <div>
              <h2 className="text-xl font-bold text-white capitalize">
                {selected.replace('_', ' ')} Agent
              </h2>
              <p className="text-sm text-dark-400">{t('configureAgent')}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleSave}
              disabled={saving}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-neon-blue/10 text-neon-blue border border-neon-blue/20 hover:bg-neon-blue/20 transition-colors text-sm"
            >
              {saving ? (
                <div className="w-4 h-4 border-2 border-neon-blue border-t-transparent rounded-full animate-spin" />
              ) : (
                <Save className="w-4 h-4" />
              )}
              {t('saveChanges')}
            </button>
          </div>
        </div>

        <div className="flex-1 flex flex-col gap-6 overflow-auto">
          {/* Settings row */}
          <div className="grid grid-cols-3 gap-4">
            <div className="glass-card rounded-xl p-4">
              <label className="text-xs text-dark-400 mb-2 block">{t('temperature')}</label>
              <input
                type="range"
                min="0"
                max="2"
                step="0.1"
                value={editTemp}
                onChange={(e) => setEditTemp(parseFloat(e.target.value))}
                className="w-full accent-neon-blue"
              />
              <div className="flex justify-between text-xs text-dark-500 mt-1">
                <span>{t('precise')}</span>
                <span className="text-neon-blue font-mono">{editTemp}</span>
                <span>{t('creative')}</span>
              </div>
            </div>

            <div className="glass-card rounded-xl p-4">
              <label className="text-xs text-dark-400 mb-2 block">{t('maxTokens')}</label>
              <input
                type="number"
                value={editMaxTokens}
                onChange={(e) => setEditMaxTokens(parseInt(e.target.value))}
                className="w-full px-3 py-2 rounded-lg bg-dark-900 border border-dark-700 text-white text-sm font-mono focus:border-neon-blue outline-none"
              />
            </div>

            <div className="glass-card rounded-xl p-4">
              <label className="text-xs text-dark-400 mb-2 block">Status</label>
              <button
                onClick={() => setEditEnabled(!editEnabled)}
                className={`w-full flex items-center justify-center gap-2 px-4 py-2 rounded-lg transition-colors ${
                  editEnabled
                    ? 'bg-neon-green/10 text-neon-green border border-neon-green/20'
                    : 'bg-dark-700 text-dark-400 border border-dark-600'
                }`}
              >
                {editEnabled ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
                {editEnabled ? t('enabled') : t('disabled')}
              </button>
            </div>
          </div>


          {/* Tool permissions */}
          <div className="glass-card rounded-xl overflow-hidden">
            <div className="flex items-center justify-between px-5 py-3 border-b border-dark-800/50">
              <div className="flex items-center gap-2">
                <Wrench className="w-4 h-4 text-neon-blue" />
                <span className="text-sm font-medium text-white">Tool Permissions</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs text-dark-500">
                  {effectiveAllowed(selected).length} of {toolStates.filter(ts => ts.enabled).length} tools
                </span>
                <button
                  onClick={() => setEditAllowed(null)}
                  className="text-xs text-dark-400 hover:text-neon-blue transition-colors"
                  title="Reset to all tools"
                >
                  Reset
                </button>
              </div>
            </div>
            <div className="p-4 grid grid-cols-2 md:grid-cols-3 gap-2">
              {toolStates.map(ts => {
                const globallyOff = !ts.enabled;
                const isAllowed = effectiveAllowed(selected).includes(ts.tool_name);
                const effective = isAllowed && !globallyOff;
                return (
                  <button
                    key={ts.tool_name}
                    disabled={globallyOff}
                    onClick={() => {
                      const current = effectiveAllowed(selected);
                      if (isAllowed) {
                        setEditAllowed(current.filter(t => t !== ts.tool_name));
                      } else {
                        setEditAllowed([...current, ts.tool_name]);
                      }
                    }}
                    className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-left transition-all ${
                      globallyOff
                        ? 'border-dark-800 bg-dark-900 opacity-40 cursor-not-allowed'
                        : effective
                        ? 'border-neon-blue/30 bg-neon-blue/10 text-white'
                        : 'border-dark-700 bg-dark-800/50 text-dark-500 hover:border-dark-600'
                    }`}
                    title={globallyOff ? 'Disabled globally in Tools page' : isAllowed ? 'Click to disable for this agent' : 'Click to enable for this agent'}
                  >
                    <div className={`w-2 h-2 rounded-full shrink-0 ${
                      globallyOff ? 'bg-dark-600' : effective ? 'bg-neon-blue' : 'bg-dark-600'
                    }`} />
                    <span className="text-xs font-mono flex-1">{ts.tool_name}</span>
                    {globallyOff && (
                      <span className="text-[9px] uppercase text-dark-500">global off</span>
                    )}
                  </button>
                );
              })}
            </div>
            <div className="px-5 py-2.5 border-t border-dark-800/50">
              <p className="text-[11px] text-dark-500 leading-relaxed">
                Disabled tools are hidden from this agent's prompt and rejected if called. Global switches (Tools page) always win.
              </p>
            </div>
          </div>

          {/* System prompt editor */}
          <div className="flex-1 glass-card rounded-xl overflow-hidden flex flex-col">
            <div className="flex items-center justify-between px-5 py-3 border-b border-dark-800/50">
              <div className="flex items-center gap-2">
                <Terminal className="w-4 h-4 text-neon-blue" />
                <span className="text-sm font-medium text-white">{t('systemPrompt')}</span>
              </div>
              <span className="text-xs text-dark-500">{editPrompt.length} {t('characters')}</span>
            </div>
            <textarea
              value={editPrompt}
              onChange={(e) => setEditPrompt(e.target.value)}
              className="flex-1 w-full p-5 bg-transparent text-sm font-mono text-dark-200 placeholder-dark-600 resize-none focus:outline-none leading-relaxed"
              placeholder="Enter the system prompt for this agent..."
              spellCheck={false}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
