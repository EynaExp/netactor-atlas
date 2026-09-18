import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  Plus, Trash2, Globe, Server, Network, ArrowLeft,
  Zap, Shield, FileText, AlertTriangle
} from 'lucide-react';
import { createEngagement, runEngagement } from '../services/api';
import { useLang } from '../i18n';

const targetTypes = [
  { value: 'ip', label: 'IP Address', icon: Server, placeholder: '192.168.1.1' },
  { value: 'cidr', label: 'CIDR Range', icon: Network, placeholder: '192.168.1.0/24' },
  { value: 'domain', label: 'Domain', icon: Globe, placeholder: 'example.com' },
];

const scanModes = [
  { value: 'quick', label: 'Quick Scan', desc: 'Fast scan of common ports', time: '~2 min' },
  { value: 'full', label: 'Full Scan', desc: 'Comprehensive port scan', time: '~10 min' },
  { value: 'stealth', label: 'Stealth Scan', desc: 'Slow, evasive scan', time: '~30 min' },
];

const reportLevels = [
  { value: 'minimal', label: 'Minimal', desc: 'Quick overview with key findings', icon: FileText },
  { value: 'medium', label: 'Medium', desc: 'Detailed findings with evidence', icon: FileText },
  { value: 'detailed', label: 'Detailed', desc: 'Complete analysis with all data', icon: FileText },
];

export default function NewScan() {
  const { t } = useLang();
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [targets, setTargets] = useState<{ type: string; value: string }[]>([
    { type: 'ip', value: '' }
  ]);
  const [scanMode, setScanMode] = useState('quick');
  const [reportLevel, setReportLevel] = useState('minimal');
  const [enableExploit, setEnableExploit] = useState(false);
  const [creating, setCreating] = useState(false);

  const addTarget = () => {
    setTargets([...targets, { type: 'ip', value: '' }]);
  };

  const removeTarget = (index: number) => {
    if (targets.length > 1) {
      setTargets(targets.filter((_, i) => i !== index));
    }
  };

  const updateTarget = (index: number, field: 'type' | 'value', value: string) => {
    const updated = [...targets];
    updated[index] = { ...updated[index], [field]: value };
    setTargets(updated);
  };

  const handleSubmit = async () => {
    if (!name || targets.some(t => !t.value)) return;
    setCreating(true);
    try {
      const engagement = await createEngagement({
        name,
        target_scope: targets.filter(t => t.value),
        scan_mode: scanMode,
        enable_exploit: enableExploit,
        report_level: reportLevel,
      });
      await runEngagement(engagement.id, enableExploit, true);
      navigate(`/scan/${engagement.id}`);
    } catch (e) {
      console.error('Failed to create engagement:', e);
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="h-full overflow-auto p-6">
      {/* Header */}
      <div className="flex items-center gap-4 mb-8">
        <button
          onClick={() => navigate('/')}
          className="p-2 rounded-lg hover:bg-dark-800 text-dark-400 hover:text-white transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div>
          <h1 className="text-2xl font-bold text-white">{t('newScan')}</h1>
          <p className="text-dark-400 mt-1">Configure your penetration test</p>
        </div>
      </div>

      <div className="max-w-4xl space-y-6">
        {/* Scan Name */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-card rounded-xl p-6"
        >
          <h2 className="text-lg font-semibold text-white mb-4">{t('scanName')}</h2>
          <input
            type="text"
            placeholder={t('scanNamePlaceholder')}
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full px-4 py-3 rounded-lg bg-dark-900 border border-dark-700 text-white placeholder-dark-500 focus:border-neon-blue focus:ring-1 focus:ring-neon-blue/30 outline-none transition-all"
          />
        </motion.div>

        {/* Targets */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="glass-card rounded-xl p-6"
        >
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white">{t('targetScope')}</h2>
            <button
              onClick={addTarget}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm text-neon-blue hover:bg-neon-blue/10 transition-colors"
            >
              <Plus className="w-4 h-4" />
              {t('addTarget')}
            </button>
          </div>

          <div className="space-y-3">
            {targets.map((target, i) => (
              <div key={i} className="flex items-center gap-3">
                <select
                  value={target.type}
                  onChange={(e) => updateTarget(i, 'type', e.target.value)}
                  className="px-3 py-2.5 rounded-lg bg-dark-900 border border-dark-700 text-white focus:border-neon-blue outline-none transition-all text-sm"
                >
                  {targetTypes.map(tt => (
                    <option key={tt.value} value={tt.value}>{tt.label}</option>
                  ))}
                </select>
                <input
                  type="text"
                  placeholder={targetTypes.find(t => t.value === target.type)?.placeholder}
                  value={target.value}
                  onChange={(e) => updateTarget(i, 'value', e.target.value)}
                  className="flex-1 px-4 py-2.5 rounded-lg bg-dark-900 border border-dark-700 text-white placeholder-dark-500 focus:border-neon-blue focus:ring-1 focus:ring-neon-blue/30 outline-none transition-all font-mono text-sm"
                />
                <button
                  onClick={() => removeTarget(i)}
                  disabled={targets.length === 1}
                  className="p-2 rounded-lg text-dark-500 hover:text-neon-red hover:bg-neon-red/10 transition-colors disabled:opacity-30"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        </motion.div>

        {/* Scan Mode */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="glass-card rounded-xl p-6"
        >
          <h2 className="text-lg font-semibold text-white mb-4">{t('scanMode')}</h2>
          <div className="grid grid-cols-3 gap-3">
            {scanModes.map(mode => (
              <button
                key={mode.value}
                onClick={() => setScanMode(mode.value)}
                className={`p-4 rounded-xl border text-left transition-all ${
                  scanMode === mode.value
                    ? 'border-neon-blue bg-neon-blue/10 glow-blue'
                    : 'border-dark-700 hover:border-dark-600 bg-dark-800/50'
                }`}
              >
                <div className="flex items-center gap-2 mb-2">
                  <Shield className={`w-4 h-4 ${scanMode === mode.value ? 'text-neon-blue' : 'text-dark-400'}`} />
                  <span className={`font-medium ${scanMode === mode.value ? 'text-neon-blue' : 'text-white'}`}>
                    {mode.label}
                  </span>
                </div>
                <p className="text-xs text-dark-400">{mode.desc}</p>
                <p className="text-xs text-dark-500 mt-1">{mode.time}</p>
              </button>
            ))}
          </div>
        </motion.div>

        {/* Report Level */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25 }}
          className="glass-card rounded-xl p-6"
        >
          <h2 className="text-lg font-semibold text-white mb-4">{t('reportLevel')}</h2>
          <div className="grid grid-cols-3 gap-3">
            {reportLevels.map(level => (
              <button
                key={level.value}
                onClick={() => setReportLevel(level.value)}
                className={`p-4 rounded-xl border text-left transition-all ${
                  reportLevel === level.value
                    ? 'border-neon-blue bg-neon-blue/10 glow-blue'
                    : 'border-dark-700 hover:border-dark-600 bg-dark-800/50'
                }`}
              >
                <div className="flex items-center gap-2 mb-2">
                  <level.icon className={`w-4 h-4 ${reportLevel === level.value ? 'text-neon-blue' : 'text-dark-400'}`} />
                  <span className={`font-medium ${reportLevel === level.value ? 'text-neon-blue' : 'text-white'}`}>
                    {level.label}
                  </span>
                </div>
                <p className="text-xs text-dark-400">{level.desc}</p>
              </button>
            ))}
          </div>
        </motion.div>

        {/* Exploit Toggle */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="glass-card rounded-xl p-6"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Zap className="w-5 h-5 text-neon-yellow" />
              <div>
                <h3 className="font-medium text-white">{t('enableExploitation')}</h3>
                <p className="text-sm text-dark-400">
                  Attempt to exploit discovered vulnerabilities (optional)
                </p>
              </div>
            </div>
            <button
              onClick={() => setEnableExploit(!enableExploit)}
              className={`relative w-12 h-6 rounded-full transition-colors ${
                enableExploit ? 'bg-neon-green' : 'bg-dark-700'
              }`}
            >
              <div
                className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${
                  enableExploit ? 'translate-x-7' : 'translate-x-1'
                }`}
              />
            </button>
          </div>
          {enableExploit && (
            <div className="mt-3 p-3 rounded-lg bg-neon-yellow/10 border border-neon-yellow/20 flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 text-neon-yellow mt-0.5" />
              <p className="text-sm text-neon-yellow/80">
                {t('exploitWarning')}
              </p>
            </div>
          )}
        </motion.div>

        {/* Submit */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.35 }}
        >
          <button
            onClick={handleSubmit}
            disabled={!name || targets.some(t => !t.value) || creating}
            className="w-full py-3 rounded-xl bg-gradient-to-r from-neon-blue to-cyber-600 text-white font-semibold hover:shadow-lg hover:shadow-neon-blue/20 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {creating ? (
              <>
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                {t('starting')}
              </>
            ) : (
              <>
                <Zap className="w-4 h-4" />
                {t('startScan')}
              </>
            )}
          </button>
        </motion.div>
      </div>
    </div>
  );
}
