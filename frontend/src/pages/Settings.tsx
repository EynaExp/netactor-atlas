import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import {
  Settings as SettingsIcon, Save, TestTube, Plus, Trash2,
  Server, Link, Wifi
} from 'lucide-react';
import {
  getLLMSettings, updateLLMSettings, listToolboxes, addToolbox,
  deleteToolbox, testToolbox
} from '../services/api';
import { LLMSettings, ToolboxConfig } from '../types';

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

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [llmData, tbData] = await Promise.all([getLLMSettings(), listToolboxes()]);
      setLlm(llmData);
      setToolboxes(tbData);
    } catch (e) {
      console.error('Failed to load settings:', e);
    }
  };

  const handleSaveLLM = async () => {
    setSaving(true);
    try {
      await updateLLMSettings(llm);
    } catch (e) {
      console.error('Failed to save LLM settings:', e);
    } finally {
      setSaving(false);
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
            </div>
            <button
              onClick={handleSaveLLM}
              disabled={saving}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-neon-blue/10 text-neon-blue border border-neon-blue/20 hover:bg-neon-blue/20 transition-colors text-sm"
            >
              {saving ? (
                <div className="w-4 h-4 border-2 border-neon-blue border-t-transparent rounded-full animate-spin" />
              ) : (
                <Save className="w-4 h-4" />
              )}
              Save
            </button>
          </div>

          <div className="space-y-4">
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
