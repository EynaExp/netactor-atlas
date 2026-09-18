import { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ArrowLeft, Play, CheckCircle2, Clock, Shield,
  ChevronDown, ChevronRight, Activity, Wifi, WifiOff,
  Search, Zap, FileText, Loader2, Square, RotateCcw, Download
} from 'lucide-react';
import {
  getEngagement, getEngagementSessions, getEngagementActions, getActionDetail,
  getEngagementFindings, getEngagementReports, approvePhase, createWS, stopEngagement, retryEngagement,
  getToken
} from '../services/api';
import { Engagement, AgentSession, AgentAction, Finding, WSMessage, PhaseType, PHASE_CONFIG } from '../types';
import { useLang } from '../i18n';

const phases: PhaseType[] = ['recon', 'scanner', 'vuln_analyzer', 'report'];
const phasesWithExploit: PhaseType[] = ['recon', 'scanner', 'vuln_analyzer', 'exploit', 'report'];

const phaseIcons: Record<string, any> = {
  recon: Search,
  scanner: Shield,
  vuln_analyzer: Activity,
  exploit: Zap,
  report: FileText,
};

export default function ScanDetail() {
  const { t } = useLang();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [engagement, setEngagement] = useState<Engagement | null>(null);
  const [sessions, setSessions] = useState<AgentSession[]>([]);
  const [actions, setActions] = useState<AgentAction[]>([]);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [reports, setReports] = useState<any[]>([]);
  const [wsConnected, setWsConnected] = useState(false);
  const [liveLogs, setLiveLogs] = useState<WSMessage[]>([]);
  const [expandedAction, setExpandedAction] = useState<string | null>(null);
  const [selectedPhase, setSelectedPhase] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const dirtyRef = useRef(false);
  const logsEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!id) return;
    loadData(true);  // force initial load — dirty flag is for WS-driven refresh only
    connectWebSocket();
    const interval = setInterval(() => loadData(), 3000);
    return () => {
      clearInterval(interval);
      wsRef.current?.close();
    };
  }, [id]);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [liveLogs]);

  const loadData = async (force = false) => {
    if (!id) return;
    if (!force && !dirtyRef.current) return;
    dirtyRef.current = false;
    try {
      const [eng, sess, act, find, rep] = await Promise.all([
        getEngagement(id),
        getEngagementSessions(id),
        getEngagementActions(id),
        getEngagementFindings(id),
        getEngagementReports(id).catch(() => []),
      ]);
      setEngagement(eng);
      setSessions(sess);
      setActions(act);
      setFindings(find);
      setReports(rep);
    } catch (e) {
      console.error('Failed to load data:', e);
    }
  };

  const handleExpandAction = async (action: AgentAction) => {
    if (expandedAction === action.id) {
      setExpandedAction(null);
      return;
    }
    setExpandedAction(action.id);
    // Fetch full output (list view returns truncated previews)
    if (!id) return;
    try {
      const full = await getActionDetail(id, action.id);
      setActions(prev => prev.map(a => a.id === action.id ? full : a));
    } catch (e) {
      console.error('Failed to load action detail:', e);
    }
  };

  const connectWebSocket = () => {
    if (!id) return;
    const ws = createWS(id, (msg: WSMessage) => {
      setWsConnected(true);
      setLiveLogs(prev => [...prev.slice(-200), msg]);
      // Don't reload data on every event — mark dirty; the interval picks it up
      dirtyRef.current = true;
    });
    ws.onopen = () => setWsConnected(true);
    ws.onclose = () => {
      setWsConnected(false);
      setTimeout(connectWebSocket, 3000);
    };
    wsRef.current = ws;
  };

  const [stopping, setStopping] = useState(false);
  const [retrying, setRetrying] = useState(false);

  const handleStop = async () => {
    if (!id || stopping) return;
    setStopping(true);
    try {
      await stopEngagement(id);
      dirtyRef.current = true;
    } catch (e) { console.error(e); }
    finally { setStopping(false); }
  };

  const handleRetry = async () => {
    if (!id || retrying) return;
    setRetrying(true);
    try {
      await retryEngagement(id);
      dirtyRef.current = true;
    } catch (e) { console.error(e); }
    finally { setRetrying(false); }
  };

  const handleApprove = async (phase: string) => {
    if (!id) return;
    await approvePhase(id, phase);
    loadData();
  };

  const handleDownload = async (reportId: string, format: string) => {
    if (!id) return;
    const token = getToken();
    if (!token) return;
    try {
      const res = await fetch(`/api/engagements/${id}/reports/${reportId}/export?format=${format}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (!res.ok) throw new Error('Download failed');
      const blob = await res.blob();
      const ext = format === 'markdown' ? 'md' : format;
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `netactor-report.${ext}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error('Download error:', e);
    }
  };

  if (!engagement) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-neon-blue border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const activePhases = engagement.enable_exploit ? phasesWithExploit : phases;
  const currentPhaseIndex = activePhases.indexOf(engagement.current_phase as PhaseType);

  const getSessionForPhase = (phase: string) =>
    sessions.find(s => s.agent_type === phase);

  const getActionsForSession = (sessionId: string) =>
    actions.filter(a => a.session_id === sessionId);

  const getPhaseStatus = (phase: string, index: number) => {
    const session = getSessionForPhase(phase);
    if (session?.status === 'completed') return 'completed';
    if (session?.status === 'running') return 'running';
    if (engagement.current_phase === phase && engagement.phase_status === 'running') return 'running';
    if (index < currentPhaseIndex) return 'completed';
    if (index === currentPhaseIndex && engagement.phase_status === 'running') return 'running';
    if (index === currentPhaseIndex) return 'current';
    return 'pending';
  };

  const phaseLabel = (phase: string) => {
    const map: Record<string, string> = {
      recon: t('phaseRecon'), scanner: t('phaseScanner'), vuln_analyzer: t('phaseAnalysis'),
      exploit: t('phaseExploit'), report: t('phaseReport'),
    };
    return map[phase] || PHASE_CONFIG[phase as PhaseType]?.label || phase;
  };

  const selectedSession = selectedPhase ? getSessionForPhase(selectedPhase) : null;
  const selectedActions = selectedSession ? getActionsForSession(selectedSession.id) : [];

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-dark-800/50 bg-dark-950/80 backdrop-blur-sm shrink-0">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate('/')}
            className="p-2 rounded-lg hover:bg-dark-800 text-dark-400 hover:text-white transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-xl font-bold text-white">{engagement.name}</h1>
            <div className="flex items-center gap-3 mt-1 text-sm text-dark-400">
              <span className="font-mono">{engagement.target_scope.map(t => t.value).join(', ')}</span>
              <span>•</span>
              <span className={`font-medium ${engagement.status === 'completed' ? 'text-neon-green' : engagement.status === 'failed' ? 'text-neon-red' : engagement.status === 'stopping' ? 'text-neon-yellow' : 'text-neon-blue'}`}>
                {engagement.status}
              </span>
              <span>•</span>
              {engagement.created_at && (
                <>
                  <span className="text-dark-500">{new Date(engagement.created_at).toLocaleString()}</span>
                  {engagement.completed_at && (
                    <>
                      <span>→</span>
                      <span>{new Date(engagement.completed_at).toLocaleString()}</span>
                      <span className="text-neon-blue font-mono">
                        ({Math.round((new Date(engagement.completed_at).getTime() - new Date(engagement.created_at).getTime()) / 60000)}m)
                      </span>
                    </>
                  )}
                  {!engagement.completed_at && engagement.status === 'running' && (
                    <span className="text-neon-blue animate-pulse">running...</span>
                  )}
                  <span>•</span>
                </>
              )}
              <div className="flex items-center gap-1">
                {wsConnected ? (
                  <Wifi className="w-3 h-3 text-neon-green" />
                ) : (
                  <WifiOff className="w-3 h-3 text-neon-red" />
                )}
                <span className={wsConnected ? 'text-neon-green' : 'text-neon-red'}>
                  {wsConnected ? 'Live' : 'Offline'}
                </span>
              </div>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {(engagement.status === 'running' || engagement.status === 'stopping') && (
            <button
              onClick={handleStop}
              disabled={stopping || engagement.status === 'stopping'}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-neon-red/10 text-neon-red border border-neon-red/20 hover:bg-neon-red/20 transition-colors disabled:opacity-50"
            >
              {stopping ? (
                <div className="w-4 h-4 border-2 border-neon-red border-t-transparent rounded-full animate-spin" />
              ) : (
                <Square className="w-4 h-4" />
              )}
              {engagement.status === 'stopping' ? 'Stopping...' : 'Stop Scan'}
            </button>
          )}
          {['failed', 'stopped', 'completed'].includes(engagement.status) && (
            <button
              onClick={handleRetry}
              disabled={retrying}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-neon-blue/10 text-neon-blue border border-neon-blue/20 hover:bg-neon-blue/20 transition-colors disabled:opacity-50"
            >
              {retrying ? (
                <div className="w-4 h-4 border-2 border-neon-blue border-t-transparent rounded-full animate-spin" />
              ) : (
                <RotateCcw className="w-4 h-4" />
              )}
              Re-run Scan
            </button>
          )}
          {engagement.status === 'running' && engagement.phase_status === 'pending' && (
            <button
              onClick={() => handleApprove(engagement.current_phase)}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-neon-green/10 text-neon-green border border-neon-green/20 hover:bg-neon-green/20 transition-colors"
            >
              <Play className="w-4 h-4" />
              Continue to {engagement.current_phase}
            </button>
          )}
          {reports.length > 0 && (
            <>
              <button
                onClick={() => handleDownload(reports[0].id, 'markdown')}
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs bg-neon-blue/10 text-neon-blue border border-neon-blue/20 hover:bg-neon-blue/20 transition-colors"
              >
                <Download className="w-3.5 h-3.5" />
                .md
              </button>
              <button
                onClick={() => handleDownload(reports[0].id, 'docx')}
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs bg-green-500/10 text-green-400 border border-green-500/20 hover:bg-green-500/20 transition-colors"
              >
                <Download className="w-3.5 h-3.5" />
                .docx
              </button>
              <button
                onClick={() => handleDownload(reports[0].id, 'pdf')}
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20 transition-colors"
              >
                <Download className="w-3.5 h-3.5" />
                .pdf
              </button>
            </>
          )}
        </div>
      </div>

      {/* Main content: flow + detail panel */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Flow Graph */}
        <div className={`shrink-0 transition-all duration-300 ${selectedPhase ? 'h-[180px]' : 'flex-1'} flex items-center justify-center p-6`}>
          <div className="flex items-center gap-0 w-full max-w-5xl">
            {activePhases.map((phase, i) => {
              const Icon = phaseIcons[phase] || Activity;
              const status = getPhaseStatus(phase, i);
              const isSelected = selectedPhase === phase;
              const session = getSessionForPhase(phase);

              return (
                <div key={phase} className="flex items-center flex-1 last:flex-initial">
                  {/* Phase Card */}
                  <motion.button
                    onClick={() => setSelectedPhase(selectedPhase === phase ? null : phase)}
                    whileHover={{ scale: 1.03 }}
                    whileTap={{ scale: 0.98 }}
                    className={`relative flex flex-col items-center justify-center gap-2 p-5 rounded-2xl border-2 transition-all cursor-pointer min-w-[140px] ${
                      isSelected
                        ? status === 'completed'
                          ? 'border-neon-green bg-neon-green/10 shadow-lg shadow-neon-green/20'
                          : status === 'running'
                          ? 'border-neon-blue bg-neon-blue/10 shadow-lg shadow-neon-blue/20'
                          : 'border-neon-yellow bg-neon-yellow/10 shadow-lg shadow-neon-yellow/20'
                        : status === 'completed'
                        ? 'border-neon-green/30 bg-neon-green/5 hover:bg-neon-green/10'
                        : status === 'running'
                        ? 'border-neon-blue/30 bg-neon-blue/5 animate-pulse-glow hover:bg-neon-blue/10'
                        : status === 'current'
                        ? 'border-neon-yellow/30 bg-neon-yellow/5 hover:bg-neon-yellow/10'
                        : 'border-dark-700 bg-dark-800/50 hover:bg-dark-800 opacity-60 hover:opacity-80'
                    }`}
                  >
                    {/* Status indicator */}
                    <div className={`absolute -top-2 -right-2 w-6 h-6 rounded-full flex items-center justify-center ${
                      status === 'completed' ? 'bg-neon-green text-dark-900' :
                      status === 'running' ? 'bg-neon-blue text-dark-900' :
                      'bg-dark-600 text-dark-400'
                    }`}>
                      {status === 'completed' ? <CheckCircle2 className="w-4 h-4" /> :
                       status === 'running' ? <Loader2 className="w-4 h-4 animate-spin" /> :
                       <span className="text-xs font-bold">{i + 1}</span>}
                    </div>

                    {/* Icon */}
                    <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${
                      status === 'completed' ? 'bg-neon-green/20 text-neon-green' :
                      status === 'running' || status === 'current' ? 'bg-neon-blue/20 text-neon-blue' :
                      'bg-dark-700 text-dark-500'
                    }`}>
                      <Icon className="w-6 h-6" />
                    </div>

                    {/* Label */}
                    <span className={`text-sm font-semibold ${
                      status === 'completed' ? 'text-neon-green' :
                      status === 'running' || status === 'current' ? 'text-neon-blue' :
                      'text-dark-500'
                    }`}>
                      {phaseLabel(phase)}
                    </span>

                    {/* Stats */}
                    {session && (
                      <div className="flex flex-col items-center gap-0.5">
                        <span className="text-[10px] text-dark-500 font-mono">
                          {session.tokens_used > 0 ? `${(session.tokens_used / 1000).toFixed(1)}k tokens` : 'starting...'}
                        </span>
                        {session.started_at && session.completed_at && (
                          <span className="text-[10px] text-dark-600 font-mono">
                            {Math.round((new Date(session.completed_at).getTime() - new Date(session.started_at).getTime()) / 1000)}s
                          </span>
                        )}
                        {session.started_at && !session.completed_at && (
                          <span className="text-[10px] text-neon-blue font-mono animate-pulse">running</span>
                        )}
                      </div>
                    )}

                    {/* Selection indicator */}
                    {isSelected && (
                      <motion.div
                        layoutId="phase-indicator"
                        className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-8 h-1 rounded-full bg-neon-blue"
                      />
                    )}
                  </motion.button>

                  {/* Arrow connector */}
                  {i < activePhases.length - 1 && (
                    <div className="flex items-center mx-1 shrink-0">
                      <div className={`w-8 sm:w-12 lg:w-16 h-0.5 ${
                        status === 'completed' ? 'bg-neon-blue/70' : 'bg-dark-800'
                      }`}>
                        {status === 'completed' && (
                          <motion.div
                            initial={{ scaleX: 0 }}
                            animate={{ scaleX: 1 }}
                            className="h-full bg-neon-blue origin-left"
                          />
                        )}
                      </div>
                      <ChevronRight className={`w-4 h-4 ${
                        status === 'completed' ? 'text-neon-blue' : 'text-dark-800'
                      }`} />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Detail Panel (bottom) */}
        <AnimatePresence>
          {selectedPhase && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.3, ease: 'easeInOut' }}
              className="border-t border-dark-800/50 bg-dark-950/80 backdrop-blur-sm overflow-hidden flex-1 min-h-0"
            >
              <div className="flex flex-col h-full max-h-[500px]">
                {/* Detail header */}
                <div className="flex items-center justify-between px-6 py-3 border-b border-dark-800/50 shrink-0">
                  <div className="flex items-center gap-3">
                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                      getPhaseStatus(selectedPhase, activePhases.indexOf(selectedPhase as PhaseType)) === 'completed'
                        ? 'bg-neon-green/20 text-neon-green'
                        : 'bg-neon-blue/20 text-neon-blue'
                    }`}>
                      {(() => {
                        const Icon = phaseIcons[selectedPhase] || Activity;
                        return <Icon className="w-4 h-4" />;
                      })()}
                    </div>
                    <div>
                      <h3 className="font-semibold text-white">{selectedPhase ? phaseLabel(selectedPhase) : ''}</h3>
                      <p className="text-xs text-dark-400">
                        {selectedSession
                          ? `${selectedActions.length} actions • ${selectedSession.tokens_used} tokens`
                          : 'Waiting to start...'}
                      </p>
                      {selectedSession?.started_at && (
                        <p className="text-[10px] text-dark-600 font-mono mt-0.5">
                          {new Date(selectedSession.started_at).toLocaleTimeString()}
                          {selectedSession.completed_at && ` → ${new Date(selectedSession.completed_at).toLocaleTimeString()} (${Math.round((new Date(selectedSession.completed_at).getTime() - new Date(selectedSession.started_at).getTime()) / 1000)}s)`}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {selectedSession?.status === 'completed' && (
                      <span className="px-2 py-1 text-xs rounded-full bg-neon-green/10 text-neon-green border border-neon-green/20">
                        Completed
                      </span>
                    )}
                    {selectedSession?.status === 'running' && (
                      <span className="px-2 py-1 text-xs rounded-full bg-neon-blue/10 text-neon-blue border border-neon-blue/20 animate-pulse">
                        Running
                      </span>
                    )}
                    <button
                      onClick={() => setSelectedPhase(null)}
                      className="p-1.5 rounded-lg hover:bg-dark-800 text-dark-400 hover:text-white transition-colors"
                    >
                      <ChevronDown className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {/* Detail content */}
                <div className="flex-1 overflow-auto p-4">
                  {selectedActions.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-dark-500">
                      <Clock className="w-8 h-8 mb-2 opacity-50" />
                      <p className="text-sm">No actions recorded yet</p>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {selectedActions.map((action) => (
                        <div
                          key={action.id}
                          className="glass-card rounded-xl overflow-hidden"
                        >
                          <button
                            onClick={() => handleExpandAction(action)}
                            className="w-full flex items-center justify-between px-4 py-3 hover:bg-dark-800/20 transition-colors"
                          >
                            <div className="flex items-center gap-3">
                              <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${
                                action.success ? 'bg-neon-green' : 'bg-neon-red'
                              }`} />
                              <span className="text-sm font-mono text-white">
                                {action.tool_name || action.action_type}
                              </span>
                              {action.action_type === 'mcp_call' && (
                                <span className="px-1.5 py-0.5 text-[10px] rounded bg-neon-purple/20 text-neon-purple font-medium">
                                  TOOL
                                </span>
                              )}
                              {action.action_type === 'llm_call' && (
                                <span className="px-1.5 py-0.5 text-[10px] rounded bg-neon-blue/20 text-neon-blue font-medium">
                                  LLM
                                </span>
                              )}
                            </div>
                            <div className="flex items-center gap-3">
                              <span className="text-xs text-dark-500 font-mono">
                                {action.duration_ms ? `${(action.duration_ms / 1000).toFixed(1)}s` : '-'}
                              </span>
                              {expandedAction === action.id ? (
                                <ChevronDown className="w-4 h-4 text-dark-500" />
                              ) : (
                                <ChevronRight className="w-4 h-4 text-dark-500" />
                              )}
                            </div>
                          </button>

                          <AnimatePresence>
                            {expandedAction === action.id && (
                              <motion.div
                                initial={{ height: 0, opacity: 0 }}
                                animate={{ height: 'auto', opacity: 1 }}
                                exit={{ height: 0, opacity: 0 }}
                                className="border-t border-dark-800/50 overflow-hidden"
                              >
                                <div className="p-4 space-y-3">
                                  <div>
                                    <p className="text-xs text-dark-500 mb-1 font-medium">Input</p>
                                    <pre className="text-xs font-mono text-dark-300 bg-dark-900 rounded-lg p-3 overflow-x-auto max-h-32 overflow-y-auto">
                                      {JSON.stringify(action.input_data, null, 2)}
                                    </pre>
                                  </div>
                                  <div>
                                    <p className="text-xs text-dark-500 mb-1 font-medium">Output</p>
                                    <pre className="text-xs font-mono text-dark-300 bg-dark-900 rounded-lg p-3 overflow-x-auto max-h-60 overflow-y-auto whitespace-pre-wrap">
                                      {typeof action.output_data === 'object'
                                        ? JSON.stringify(action.output_data, null, 2)
                                        : String(action.output_data)}
                                    </pre>
                                  </div>
                                </div>
                              </motion.div>
                            )}
                          </AnimatePresence>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Findings (always visible at bottom when no phase selected) */}
        {!selectedPhase && findings.length > 0 && (
          <div className="border-t border-dark-800/50 bg-dark-950/80 p-4 shrink-0 max-h-[200px] overflow-auto">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Shield className="w-4 h-4 text-neon-blue" />
                <span className="text-sm font-medium text-white">Findings ({findings.length})</span>
              </div>
            </div>
            <div className="flex gap-2 flex-wrap">
              {findings.slice(0, 6).map(f => (
                <div key={f.id} className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-dark-800/50 border border-dark-700/50">
                  <span className={`w-2 h-2 rounded-full ${
                    f.severity === 'critical' ? 'bg-red-500' :
                    f.severity === 'high' ? 'bg-orange-500' :
                    f.severity === 'medium' ? 'bg-yellow-500' :
                    f.severity === 'low' ? 'bg-blue-500' :
                    'bg-gray-500'
                  }`} />
                  <span className="text-xs text-dark-300 truncate max-w-[200px]">{f.title}</span>
                </div>
              ))}
              {findings.length > 6 && (
                <span className="text-xs text-dark-500 self-center">+{findings.length - 6} more</span>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
