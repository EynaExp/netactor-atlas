import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Search, Server, Globe, Shield, ChevronDown, ChevronRight, Clock,
  Edit3, Save, X, RefreshCw
} from 'lucide-react';
import { listAssets, getAsset, updateAsset } from '../services/api';

interface Asset {
  id: string;
  host: string;
  asset_type: string;
  first_seen: string;
  last_seen: string;
  owner: string | null;
  notes: string | null;
  snapshots: Snapshot[];
}

interface Snapshot {
  id: string;
  asset_id: string;
  engagement_id: string;
  port: number | null;
  protocol: string | null;
  service: string | null;
  version: string | null;
  product: string | null;
  extra_info: string | null;
  state: string;
  created_at: string;
}

export default function Assets() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState<string>('');
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editNotes, setEditNotes] = useState('');
  const [editOwner, setEditOwner] = useState('');
  const [saving, setSaving] = useState(false);

  const loadAssets = async () => {
    setLoading(true);
    try {
      const data = await listAssets(search || undefined, typeFilter || undefined);
      setAssets(data);
    } catch (e) {
      console.error('Failed to load assets:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAssets();
  }, [search, typeFilter]);

  const handleExpand = async (id: string) => {
    if (expandedId === id) {
      setExpandedId(null);
      return;
    }
    try {
      const data = await getAsset(id);
      setAssets(prev => prev.map(a => a.id === id ? { ...a, ...data } : a));
      setExpandedId(id);
    } catch (e) {
      console.error('Failed to load asset:', e);
    }
  };

  const handleEdit = (asset: Asset) => {
    setEditingId(asset.id);
    setEditNotes(asset.notes || '');
    setEditOwner(asset.owner || '');
  };

  const handleSave = async (id: string) => {
    setSaving(true);
    try {
      await updateAsset(id, { notes: editNotes, owner: editOwner });
      setAssets(prev => prev.map(a => a.id === id ? { ...a, notes: editNotes, owner: editOwner } : a));
      setEditingId(null);
    } catch (e) {
      console.error('Failed to save asset:', e);
    } finally {
      setSaving(false);
    }
  };

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'host': return <Server className="w-4 h-4" />;
      case 'service': return <Globe className="w-4 h-4" />;
      case 'web': return <Globe className="w-4 h-4" />;
      default: return <Shield className="w-4 h-4" />;
    }
  };

  const getStateColor = (state: string) => {
    switch (state) {
      case 'open': return 'text-neon-green';
      case 'filtered': return 'text-yellow-400';
      case 'closed': return 'text-neon-red';
      default: return 'text-dark-400';
    }
  };

  const getServiceCount = (asset: Asset) => {
    return asset.snapshots?.length || 0;
  };

  return (
    <div className="h-full overflow-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Asset Inventory</h1>
          <p className="text-sm text-dark-400 mt-1">
            {assets.length} assets discovered across all scans
          </p>
        </div>
        <button
          onClick={loadAssets}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-dark-800 border border-dark-700 text-dark-300 hover:text-white hover:border-dark-600 transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Filters */}
      <div className="flex gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-500" />
          <input
            type="text"
            placeholder="Search by host..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 rounded-lg bg-dark-900 border border-dark-700 text-white placeholder-dark-500 focus:border-neon-blue outline-none text-sm"
          />
        </div>
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="px-4 py-2.5 rounded-lg bg-dark-900 border border-dark-700 text-white text-sm focus:border-neon-blue outline-none"
        >
          <option value="">All Types</option>
          <option value="host">Hosts</option>
          <option value="service">Services</option>
        </select>
      </div>

      {/* Assets List */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <div className="w-8 h-8 border-2 border-neon-blue border-t-transparent rounded-full animate-spin" />
        </div>
      ) : assets.length === 0 ? (
        <div className="text-center py-12">
          <Server className="w-12 h-12 text-dark-600 mx-auto mb-4" />
          <p className="text-dark-400">No assets discovered yet</p>
          <p className="text-dark-500 text-sm mt-2">Run a scan to discover assets</p>
        </div>
      ) : (
        <div className="space-y-3">
          {assets.map((asset) => (
            <motion.div
              key={asset.id}
              layout
              className="glass-card rounded-xl overflow-hidden"
            >
              {/* Asset Header */}
              <div
                className="flex items-center gap-4 p-4 cursor-pointer hover:bg-dark-800/30 transition-colors"
                onClick={() => handleExpand(asset.id)}
              >
                <div className={`p-2 rounded-lg ${
                  asset.asset_type === 'host' ? 'bg-neon-blue/10 text-neon-blue' : 'bg-purple-500/10 text-purple-400'
                }`}>
                  {getTypeIcon(asset.asset_type)}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="font-mono text-white font-medium truncate">{asset.host}</h3>
                    <span className="text-xs px-2 py-0.5 rounded bg-dark-700 text-dark-300">
                      {asset.asset_type}
                    </span>
                  </div>
                  <div className="flex items-center gap-4 mt-1 text-xs text-dark-400">
                    <span>{getServiceCount(asset)} services</span>
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {new Date(asset.last_seen).toLocaleDateString()}
                    </span>
                    {asset.owner && (
                      <span className="text-neon-blue">Owner: {asset.owner}</span>
                    )}
                  </div>
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); handleEdit(asset); }}
                  className="p-2 rounded-lg text-dark-400 hover:text-neon-blue hover:bg-neon-blue/10 transition-colors"
                >
                  <Edit3 className="w-4 h-4" />
                </button>
                {expandedId === asset.id ? (
                  <ChevronDown className="w-5 h-5 text-dark-400" />
                ) : (
                  <ChevronRight className="w-5 h-5 text-dark-400" />
                )}
              </div>

              {/* Expanded Content */}
              <AnimatePresence>
                {expandedId === asset.id && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className="border-t border-dark-700/50"
                  >
                    <div className="p-4 space-y-4">
                      {/* Notes */}
                      {asset.notes && (
                        <div className="p-3 rounded-lg bg-dark-800/50 text-sm text-dark-300">
                          <span className="text-dark-500 font-medium">Notes:</span> {asset.notes}
                        </div>
                      )}

                      {/* Services Table */}
                      {asset.snapshots && asset.snapshots.length > 0 ? (
                        <div className="overflow-x-auto">
                          <table className="w-full text-sm">
                            <thead>
                              <tr className="text-left text-dark-400 border-b border-dark-700/50">
                                <th className="pb-2 font-medium">Port</th>
                                <th className="pb-2 font-medium">Protocol</th>
                                <th className="pb-2 font-medium">Service</th>
                                <th className="pb-2 font-medium">Version</th>
                                <th className="pb-2 font-medium">State</th>
                                <th className="pb-2 font-medium">Discovered</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-dark-700/30">
                              {asset.snapshots.map((snap) => (
                                <tr key={snap.id} className="text-dark-200">
                                  <td className="py-2 font-mono">{snap.port}</td>
                                  <td className="py-2">{snap.protocol}</td>
                                  <td className="py-2">{snap.service}</td>
                                  <td className="py-2 text-dark-400">{snap.product || snap.version || '-'}</td>
                                  <td className={`py-2 ${getStateColor(snap.state)}`}>{snap.state}</td>
                                  <td className="py-2 text-dark-400 text-xs">
                                    {new Date(snap.created_at).toLocaleString()}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      ) : (
                        <p className="text-dark-500 text-sm">No services discovered</p>
                      )}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Edit Modal */}
              <AnimatePresence>
                {editingId === asset.id && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className="border-t border-neon-blue/30 bg-neon-blue/5"
                  >
                    <div className="p-4 space-y-3">
                      <div className="flex items-center justify-between mb-2">
                        <h4 className="text-sm font-medium text-white">Edit Asset</h4>
                        <button onClick={() => setEditingId(null)} className="text-dark-400 hover:text-white">
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                      <div>
                        <label className="block text-xs text-dark-400 mb-1">Notes</label>
                        <textarea
                          value={editNotes}
                          onChange={(e) => setEditNotes(e.target.value)}
                          placeholder="Add notes about this asset..."
                          className="w-full px-3 py-2 rounded-lg bg-dark-900 border border-dark-700 text-white placeholder-dark-500 focus:border-neon-blue outline-none text-sm resize-none h-20"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-dark-400 mb-1">Owner</label>
                        <input
                          type="text"
                          value={editOwner}
                          onChange={(e) => setEditOwner(e.target.value)}
                          placeholder="Assign owner..."
                          className="w-full px-3 py-2 rounded-lg bg-dark-900 border border-dark-700 text-white placeholder-dark-500 focus:border-neon-blue outline-none text-sm"
                        />
                      </div>
                      <div className="flex justify-end gap-2">
                        <button
                          onClick={() => setEditingId(null)}
                          className="px-3 py-1.5 rounded-lg text-dark-400 hover:text-white text-sm"
                        >
                          Cancel
                        </button>
                        <button
                          onClick={() => handleSave(asset.id)}
                          disabled={saving}
                          className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-neon-blue/10 text-neon-blue border border-neon-blue/20 hover:bg-neon-blue/20 text-sm disabled:opacity-50"
                        >
                          <Save className="w-3.5 h-3.5" />
                          {saving ? 'Saving...' : 'Save'}
                        </button>
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}
