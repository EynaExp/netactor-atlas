import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import {
  Settings as SettingsIcon, Save, TestTube, Plus, Trash2,
  Server, Link, Wifi, KeyRound, Copy, RefreshCw
} from 'lucide-react';
import {
  getLLMSettings, updateLLMSettings, testLLMConnection, listToolboxes, addToolbox,
  deleteToolbox, testToolbox, getAtlasKey, generateAtlasKey, revokeAtlasKey,
  getNvdKey, saveNvdKey, revokeNvdKey
} from '../services/api';
import { LLMSettings, ToolboxConfig } from '../types';

const LLM_PROVIDERS: Record<string, { base_url: string; model: string }> = {
  'OpenRouter': { base_url: 'https://openrouter.ai/api/v1', model: '' },
  'OpenAI': { base_url: 'https://api.openai.com/v1', model: 'gpt-4' },
  'Ollama (Local)': { base_url: 'http://localhost:11434/v1', model: 'llama3.2' },
  'LM Studio (Local)': { base_url: 'http://localhost:1234/v1', model: '' },
  'vLLM (Local)': { base_url: 'http://localhost:8080/v1', model: '' },
  'Custom': { base_url: '', model: '' },
};

export default function SettingsPage() {
  const [llm, setLlm] = useState<LLMSettings>({ base_url: '', api_key: '', model: '' });
  const [toolboxes, setToolboxes] = useState<ToolboxConfig[]>([]);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<{ name: string; ok: boolean } | null>(null);
  const [showAddToolbox, setShowAddToolbox] = useState(false);
  const [newToolbox, setNewToolbox] = useState({
    name: '',
    executor_type: 'docker',
    container_name: '',
    mcp_url: '',
    working_dir: '/workspace',
  });
  const [provider, setProvider] = useState('OpenRouter');
  const [llmStatus, setLlmStatus] = useState<'idle' | 'testing' | 'active' | 'failed'>('idle');
  const [llmTestError, setLlmTestError] = useState('');
  const [llmSaved, setLlmSaved] = useState(false);
  const [atlasKey, setAtlasKey] = useState('');
  const [atlasConfigured, setAtlasConfigured] = useState(false);
  const [atlasBusy, setAtlasBusy] = useState(false);
  const [keyCopied, setKeyCopied] = useState(false);
  const [nvdKey, setNvdKey] = useState('');
  const [nvdConfigured, setNvdConfigured] = useState(false);

  useEffect(() => {
    loadData();
    loadAtlas();
  }, []);

  const loadAtlas = async () => {
    try {
      const [a, n] = await Promise.all([getAtlasKey(), getNvdKey()]);
      setAtlasKey(a.key || '');
      setAtlasConfigured(a.configured);
      setNvdKey(n.key || '');
      setNvdConfigured(n.configured);
    } catch (e) {
      console.error('Failed to load ATLAS settings:', e);
    }
  };

  const handleGenerateKey = async () => {
    setAtlasBusy(true);
    try {
      const res = await generateAtlasKey();
      setAtlasKey(res.key);
      setAtlasConfigured(true);
    } catch (e) {
      console.error('Failed to generate ATLAS key:', e);
    } finally {
      setAtlasBusy(false);
    }
  };

  const handleRevokeKey = async () => {
    if (!confirm('Revoke the ATLAS API key? External ATLAS clients will stop working until a new key is generated.')) return;
    setAtlasBusy(true);
    try {
      await revokeAtlasKey();
      setAtlasKey('');
      setAtlasConfigured(false);
    } catch (e) {
      console.error('Failed to revoke ATLAS key:', e);
    } finally {
      setAtlasBusy(false);
    }
  };

  const handleCopyKey = async () => {
    try {
      await navigator.clipboard.writeText(atlasKey);
      setKeyCopied(true);
      setTimeout(() => setKeyCopied(false), 2000);
    } catch (e) {
      console.error('Failed to copy key:', e);
    }
  };

  const handleSaveNvdKey = async () => {
    setAtlasBusy(true);
    try {
      await saveNvdKey(nvdKey);
      setNvdConfigured(true);
    } catch (e) {
      console.error('Failed to save NVD key:', e);
    } finally {
      setAtlasBusy(false);
    }
  };

  const handleRevokeNvdKey = async () => {
    setAtlasBusy(true);
    try {
      await revokeNvdKey();
      setNvdKey('');
      setNvdConfigured(false);
    } catch (e) {
      console.error('Failed to clear NVD key:', e);
    } finally {
      setAtlasBusy(false);
    }
  };

  const loadData = async () => {
    try {
      const [llmData, tbData] = await Promise.all([getLLMSettings(), listToolboxes()]);
      setLlm(llmData);
      setToolboxes(tbData);
      // Detect provider from base_url
      if (llmData.base_url?.includes('openrouter')) setProvider('OpenRouter');
      else if (llmData.base_url?.includes('openai.com')) setProvider('OpenAI');
      else if (llmData.base_url?.includes('localhost:11434')) setProvider('Ollama (Local)');
      else if (llmData.base_url?.includes('localhost:1234')) setProvider('LM Studio (Local)');
      else if (llmData.base_url?.includes('localhost:8080')) setProvider('vLLM (Local)');
      else setProvider('Custom');
      setLlmStatus('idle');
    } catch (e) {
      console.error('Failed to load settings:', e);
    }
  };

  const handleProviderChange = (name: string) => {
    setProvider(name);
    const preset = LLM_PROVIDERS[name];
    if (preset) {
      setLlm({ ...llm, base_url: preset.base_url, model: preset.model || llm.model });
    }
  };

  const handleSaveLLM = async () => {
    setSaving(true);
    try {
      await updateLLMSettings(llm);
      setLlmSaved(true);
      setLlmStatus('active');
      setLlmTestError('');
      setTimeout(() => setLlmSaved(false), 3000);
    } catch (e) {
      console.error('Failed to save LLM settings:', e);
      setLlmSaved(false);
    } finally {
      setSaving(false);
    }
  };

  const handleTestLLM = async () => {
    setLlmStatus('testing');
    setLlmTestError('');
    try {
      const result = await testLLMConnection();
      if (result.success) {
        setLlmStatus('active');
      } else {
        setLlmStatus('failed');
        setLlmTestError(result.error || 'Connection failed');
      }
    } catch (e) {
      setLlmStatus('failed');
      setLlmTestError(String(e));
    }
  };

  const handleTestToolbox = async (name: string) => {
    setTesting(name);
    setTestResult(null);
    try {
      const result = await testToolbox(name, 'echo "Connection OK"');
      setTestResult({ name, ok: result.success !== false });
    } catch (e) {
      setTestResult({ name, ok: false });
    } finally {
      setTesting(null);
    }
  };

  const handleAddToolbox = async () => {
    try {
      await addToolbox(newToolbox);
      setShowAddToolbox(false);
      setNewToolbox({ name: '', executor_type: 'docker', container_name: '', mcp_url: '', working_dir: '/workspace' });
      loadData();
    } catch (e) {
      console.error('Failed to add toolbox:', e);
    }
  };

  const handleDeleteToolbox = async (name: string) => {
    if (confirm(`Delete toolbox "${name}"?`)) {
      await deleteToolbox(name);
      loadData();
    }
  };

  return (
    <div className="h-full overflow-auto p-6">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center gap-3 mb-8">
          <SettingsIcon className="w-6 h-6 text-neon-blue" />
          <div>
            <h1 className="text-2xl font-bold text-white">Settings</h1>
            <p className="text-dark-400 mt-1">Configure LLM provider and toolboxes</p>
          </div>
        </div>

        {/* LLM Settings */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-card rounded-xl p-6"
        >
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-2">
              <Wifi className="w-5 h-5 text-neon-blue" />
              <h2 className="text-lg font-semibold text-white">LLM Provider</h2>
              {llmStatus === 'active' && (
                <span className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-neon-green/15 text-neon-green text-xs font-medium">
                  <span className="w-1.5 h-1.5 rounded-full bg-neon-green animate-pulse" />
                  Active
                </span>
              )}
              {llmStatus === 'failed' && (
                <span className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-neon-red/15 text-neon-red text-xs font-medium">
                  <span className="w-1.5 h-1.5 rounded-full bg-neon-red" />
                  Failed
                </span>
              )}
              {llmSaved && (
                <span className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-neon-green/15 text-neon-green text-xs font-medium">
                  Saved
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleTestLLM}
                disabled={llmStatus === 'testing' || !llm.base_url || !llm.api_key || !llm.model}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-dark-700 text-dark-300 border border-dark-600 hover:bg-dark-600 hover:text-white transition-colors text-sm disabled:opacity-50"
              >
                {llmStatus === 'testing' ? (
                  <div className="w-4 h-4 border-2 border-neon-blue border-t-transparent rounded-full animate-spin" />
                ) : (
                  <TestTube className="w-4 h-4" />
                )}
                Test Connection
              </button>
              <button
                onClick={handleSaveLLM}
                disabled={saving || !llm.base_url || !llm.api_key || !llm.model}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-neon-blue/10 text-neon-blue border border-neon-blue/20 hover:bg-neon-blue/20 transition-colors text-sm disabled:opacity-50"
              >
                {saving ? (
                  <div className="w-4 h-4 border-2 border-neon-blue border-t-transparent rounded-full animate-spin" />
                ) : (
                  <Save className="w-4 h-4" />
                )}
                Save
              </button>
            </div>
          </div>

          {llmTestError && (
            <div className="mb-4 px-4 py-3 rounded-lg bg-neon-red/10 border border-neon-red/20 text-neon-red text-sm">
              {llmTestError}
            </div>
          )}

          <div className="space-y-4">
            <div>
              <label className="text-xs text-dark-400 mb-1.5 block">Provider</label>
              <select
                value={provider}
                onChange={(e) => handleProviderChange(e.target.value)}
                className="w-full px-4 py-2.5 rounded-lg bg-dark-900 border border-dark-700 text-white text-sm focus:border-neon-blue outline-none transition-all"
              >
                {Object.keys(LLM_PROVIDERS).map((name) => (
                  <option key={name} value={name}>{name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs text-dark-400 mb-1.5 block">API Base URL</label>
              <input
                type="text"
                value={llm.base_url}
                onChange={(e) => setLlm({ ...llm, base_url: e.target.value })}
                placeholder="https://openrouter.ai/api/v1"
                className="w-full px-4 py-2.5 rounded-lg bg-dark-900 border border-dark-700 text-white font-mono text-sm focus:border-neon-blue outline-none transition-all"
              />
            </div>
            <div>
              <label className="text-xs text-dark-400 mb-1.5 block">API Key</label>
              <input
                type="password"
                value={llm.api_key}
                onChange={(e) => setLlm({ ...llm, api_key: e.target.value })}
                placeholder="sk-..."
                className="w-full px-4 py-2.5 rounded-lg bg-dark-900 border border-dark-700 text-white font-mono text-sm focus:border-neon-blue outline-none transition-all"
              />
            </div>
            <div>
              <label className="text-xs text-dark-400 mb-1.5 block">Model</label>
              <input
                type="text"
                value={llm.model}
                onChange={(e) => setLlm({ ...llm, model: e.target.value })}
                placeholder="gpt-4"
                className="w-full px-4 py-2.5 rounded-lg bg-dark-900 border border-dark-700 text-white font-mono text-sm focus:border-neon-blue outline-none transition-all"
              />
            </div>
          </div>
        </motion.div>

        {/* ATLAS External API */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className="glass-card rounded-xl p-6"
        >
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-2">
              <KeyRound className="w-5 h-5 text-neon-green" />
              <h2 className="text-lg font-semibold text-white">ATLAS External API</h2>
              {atlasConfigured ? (
                <span className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-neon-green/15 text-neon-green text-xs font-medium">
                  <span className="w-1.5 h-1.5 rounded-full bg-neon-green" />
                  Key active
                </span>
              ) : (
                <span className="px-2.5 py-0.5 rounded-full bg-dark-700 text-dark-300 text-xs font-medium">
                  Not configured
                </span>
              )}
            </div>
            {atlasConfigured && (
              <div className="flex items-center gap-2">
                <button
                  onClick={handleGenerateKey}
                  disabled={atlasBusy}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg bg-dark-700 text-dark-300 border border-dark-600 hover:bg-dark-600 hover:text-white transition-colors text-sm disabled:opacity-50"
                >
                  <RefreshCw className="w-4 h-4" />
                  Rotate
                </button>
                <button
                  onClick={handleRevokeKey}
                  disabled={atlasBusy}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg bg-neon-red/10 text-neon-red border border-neon-red/20 hover:bg-neon-red/20 transition-colors text-sm disabled:opacity-50"
                >
                  <Trash2 className="w-4 h-4" />
                  Revoke
                </button>
              </div>
            )}
          </div>

          <p className="text-sm text-dark-400 mb-4">
            Lets the ATLAS app launch scans and fetch per-target CVE reports from this
            NetActor instance. Requests authenticate with the{' '}
            <code className="text-dark-300">X-API-Key</code> header.
          </p>

          {!atlasConfigured ? (
            <button
              onClick={handleGenerateKey}
              disabled={atlasBusy}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-neon-green/10 text-neon-green border border-neon-green/20 hover:bg-neon-green/20 transition-colors text-sm disabled:opacity-50"
            >
              <KeyRound className="w-4 h-4" />
              Generate API Key
            </button>
          ) : (
            <div className="flex items-center gap-2">
              <input
                readOnly
                value={atlasKey}
                className="flex-1 px-4 py-2.5 rounded-lg bg-dark-900 border border-dark-700 text-white font-mono text-xs focus:border-neon-green outline-none"
              />
              <button
                onClick={handleCopyKey}
                className="p-2.5 rounded-lg text-dark-400 hover:text-neon-green hover:bg-neon-green/10 transition-colors"
                title="Copy key"
              >
                <Copy className="w-4 h-4" />
              </button>
            </div>
          )}

          {keyCopied && <p className="mt-2 text-xs text-neon-green">Copied to clipboard</p>}

          {atlasConfigured && (
            <div className="mt-4 px-4 py-3 rounded-lg bg-dark-800/50 border border-dark-700">
              <p className="text-xs text-dark-400 mb-1">Example</p>
              <code className="block text-xs text-dark-300 font-mono break-all">
                {`curl -X POST http://localhost/api/atlas/scan -H "X-API-Key: <key>" -H "Content-Type: application/json" -d '{"host":"192.168.1.10"}'`}
              </code>
            </div>
          )}

          <div className="mt-6 pt-6 border-t border-dark-700">
            <label className="text-xs text-dark-400 mb-1.5 block">
              NVD API key (optional - raises the NVD rate limit for CVE enrichment)
            </label>
            <div className="flex items-center gap-2">
              <input
                type="password"
                value={nvdKey}
                placeholder={nvdConfigured ? 'Saved - type a new key to replace' : 'nvd_api_...'}
                onChange={(e) => setNvdKey(e.target.value)}
                className="flex-1 px-4 py-2.5 rounded-lg bg-dark-900 border border-dark-700 text-white font-mono text-sm focus:border-neon-green outline-none"
              />
              <button
                onClick={handleSaveNvdKey}
                disabled={atlasBusy || !nvdKey}
                className="px-4 py-2 rounded-lg bg-neon-blue/10 text-neon-blue border border-neon-blue/20 hover:bg-neon-blue/20 transition-colors text-sm disabled:opacity-50"
              >
                Save
              </button>
              {nvdConfigured && (
                <button
                  onClick={handleRevokeNvdKey}
                  disabled={atlasBusy}
                  className="p-2.5 rounded-lg text-dark-400 hover:text-neon-red hover:bg-neon-red/10 transition-colors"
                  title="Clear NVD key"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              )}
            </div>
          </div>
        </motion.div>

        {/* Toolboxes */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="glass-card rounded-xl p-6"
        >
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-2">
              <Server className="w-5 h-5 text-neon-purple" />
              <h2 className="text-lg font-semibold text-white">Toolboxes</h2>
            </div>
            <button
              onClick={() => setShowAddToolbox(!showAddToolbox)}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-neon-purple/10 text-neon-purple border border-neon-purple/20 hover:bg-neon-purple/20 transition-colors text-sm"
            >
              <Plus className="w-4 h-4" />
              Add Toolbox
            </button>
          </div>

          {/* Add toolbox form */}
          {showAddToolbox && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              className="mb-4 p-4 rounded-xl bg-dark-800/50 border border-dark-700 space-y-3"
            >
              <div className="grid grid-cols-2 gap-3">
                <input
                  type="text"
                  placeholder="Name"
                  value={newToolbox.name}
                  onChange={(e) => setNewToolbox({ ...newToolbox, name: e.target.value })}
                  className="px-3 py-2 rounded-lg bg-dark-900 border border-dark-700 text-white text-sm focus:border-neon-blue outline-none"
                />
                <select
                  value={newToolbox.executor_type}
                  onChange={(e) => setNewToolbox({ ...newToolbox, executor_type: e.target.value })}
                  className="px-3 py-2 rounded-lg bg-dark-900 border border-dark-700 text-white text-sm focus:border-neon-blue outline-none"
                >
                  <option value="docker">Docker</option>
                  <option value="ssh">SSH</option>
                  <option value="local">Local</option>
                </select>
                <input
                  type="text"
                  placeholder="Container name"
                  value={newToolbox.container_name}
                  onChange={(e) => setNewToolbox({ ...newToolbox, container_name: e.target.value })}
                  className="px-3 py-2 rounded-lg bg-dark-900 border border-dark-700 text-white text-sm focus:border-neon-blue outline-none"
                />
                <input
                  type="text"
                  placeholder="MCP URL (http://host:3001/mcp)"
                  value={newToolbox.mcp_url}
                  onChange={(e) => setNewToolbox({ ...newToolbox, mcp_url: e.target.value })}
                  className="px-3 py-2 rounded-lg bg-dark-900 border border-dark-700 text-white text-sm focus:border-neon-blue outline-none"
                />
              </div>
              <div className="flex justify-end gap-2">
                <button
                  onClick={() => setShowAddToolbox(false)}
                  className="px-3 py-1.5 rounded-lg text-sm text-dark-400 hover:text-white transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleAddToolbox}
                  disabled={!newToolbox.name}
                  className="px-4 py-1.5 rounded-lg bg-neon-purple/20 text-neon-purple text-sm hover:bg-neon-purple/30 transition-colors disabled:opacity-50"
                >
                  Add
                </button>
              </div>
            </motion.div>
          )}

          {/* Toolbox list */}
          <div className="space-y-2">
            {toolboxes.map(tb => (
              <div
                key={tb.name}
                className="flex items-center justify-between p-4 rounded-xl bg-dark-800/30 border border-dark-700/50 hover:border-dark-600 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-neon-purple/10 flex items-center justify-center">
                    <Link className="w-5 h-5 text-neon-purple" />
                  </div>
                  <div>
                    <h3 className="font-medium text-white">{tb.name}</h3>
                    <div className="flex items-center gap-2 text-xs text-dark-400">
                      <span className="capitalize">{tb.executor_type}</span>
                      {tb.container_name && <span>• {tb.container_name}</span>}
                      {tb.mcp_url && <span>• MCP</span>}
                      <span>• {tb.tool_count} tools</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {testResult?.name === tb.name && (
                    <span className={`text-xs ${testResult.ok ? 'text-neon-green' : 'text-neon-red'}`}>
                      {testResult.ok ? 'Connected' : 'Failed'}
                    </span>
                  )}
                  <button
                    onClick={() => handleTestToolbox(tb.name)}
                    disabled={testing === tb.name}
                    className="p-2 rounded-lg text-dark-400 hover:text-neon-blue hover:bg-neon-blue/10 transition-colors"
                    title="Test connection"
                  >
                    {testing === tb.name ? (
                      <div className="w-4 h-4 border-2 border-neon-blue border-t-transparent rounded-full animate-spin" />
                    ) : (
                      <TestTube className="w-4 h-4" />
                    )}
                  </button>
                  <button
                    onClick={() => handleDeleteToolbox(tb.name)}
                    className="p-2 rounded-lg text-dark-500 hover:text-neon-red hover:bg-neon-red/10 transition-colors"
                    title="Delete"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}

            {toolboxes.length === 0 && (
              <div className="text-center py-8 text-dark-400">
                <Server className="w-8 h-8 mx-auto mb-3 opacity-50" />
                <p>No toolboxes configured</p>
              </div>
            )}
          </div>
        </motion.div>
      </div>
    </div>
  );
}
