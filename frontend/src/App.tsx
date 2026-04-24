import React, { useState, useEffect, useRef } from 'react';
import { client } from './api/client';
import type { Run, RunSummary, Plan, Artifact } from './api/client';
import { subscribeToEvents } from './api/events';
import type { RuntimeEvent } from './api/events';
import { 
  Play, Pause, Square, Search, Plus, 
  Activity, FileText, 
  AlertCircle, ChevronDown,
  Cpu, Database, Clock, Zap, Shield,
  Layers, MessageSquare, Target, Settings, Eye
} from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { CognitiveGraph } from './CognitiveGraph';
import { TerminalOverride } from './TerminalOverride';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const App: React.FC = () => {
  const [runs, setRuns] = useState<Run[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [summary, setSummary] = useState<RunSummary | null>(null);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [state, setState] = useState<any>(null);
  const [events, setEvents] = useState<RuntimeEvent[]>([]);
  const [approvals, setApprovals] = useState<any[]>([]);
  const [search, setSearch] = useState('');
  const [connected, setConnected] = useState(false);
  const [showComposer, setShowComposer] = useState(false);
  const [selectedArtifact, setSelectedArtifact] = useState<Artifact | null>(null);
  const [activeTab, setActiveTab] = useState<'timeline' | 'graph' | 'terminal'>('timeline');
  
  const timelineRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    refreshGlobal();
    const interval = setInterval(refreshGlobal, 8000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (selectedRunId) {
      refreshRun(selectedRunId);
      setEvents([]);
      const unsubscribe = subscribeToEvents(
        selectedRunId,
        (event) => {
          setEvents(prev => [...prev, event]);
          refreshRun(selectedRunId);
          refreshGlobal();
        },
        setConnected
      );
      return unsubscribe;
    } else {
      setConnected(false);
      setSummary(null);
      setPlan(null);
      setArtifacts([]);
      setState(null);
      setEvents([]);
    }
  }, [selectedRunId]);

  useEffect(() => {
    if (timelineRef.current) {
      timelineRef.current.scrollTop = timelineRef.current.scrollHeight;
    }
  }, [events]);

  const refreshGlobal = async () => {
    try {
      const [runsData, approvalsData] = await Promise.all([
        client.getRuns(),
        client.getApprovals()
      ]);
      setRuns(runsData.runs || []);
      setApprovals(approvalsData.pending || []);
    } catch (e) {
      console.error(e);
    }
  };

  const refreshRun = async (id: string) => {
    try {
      const [summaryData, planData, artifactsData, stateData] = await Promise.all([
        client.getSummary(id),
        client.getPlan(id),
        client.getArtifacts(id),
        client.getState(id)
      ]);
      setSummary(summaryData);
      setPlan(planData.plan);
      setArtifacts(artifactsData.artifacts || []);
      setState(stateData);
    } catch (e) {
      console.error(e);
    }
  };

  const handleCreateRun = async (payload: any) => {
    try {
      const res = await client.createRun(payload);
      setShowComposer(false);
      await refreshGlobal();
      setSelectedRunId(res.run_id);
    } catch (e) {
      alert("Failed to create run: " + e);
    }
  };

  const filteredRuns = runs.filter(r => 
    r.run_id.toLowerCase().includes(search.toLowerCase()) ||
    r.goal?.description.toLowerCase().includes(search.toLowerCase())
  ).sort((a, b) => b.updated_at - a.updated_at);

  return (
    <div className="flex h-screen bg-[#0a0d14] text-[#f8fafc] overflow-hidden font-sans selection:bg-blue-500/30">
      {/* Sidebar */}
      <aside className="w-72 flex-shrink-0 bg-[#121620] border-r border-white/5 flex flex-col z-10 shadow-2xl">
        <div className="p-6 border-b border-white/5">
          <h1 className="text-[0.9rem] font-black text-white uppercase tracking-[0.2em] flex items-center gap-3">
            <div className="w-2.5 h-2.5 bg-blue-500 rounded-full shadow-[0_0_15px_#3b82f6] animate-pulse" />
            Human
          </h1>
          <p className="text-[0.65rem] text-[#64748b] mt-1 font-bold uppercase tracking-widest">Cognitive Runtime</p>
        </div>
        
        <div className="p-4 border-b border-white/5">
          <div className="relative group">
            <Search className="absolute left-3 top-2.5 w-4 h-4 text-[#64748b] group-focus-within:text-blue-400 transition-colors" />
            <input 
              type="text" 
              placeholder="Filter active runs..."
              className="w-full bg-[#1a202c] border border-white/5 rounded-xl py-2.5 pl-10 pr-3 text-sm focus:outline-none focus:border-blue-500/50 transition-all placeholder:text-[#475569]"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto py-3 px-2 space-y-1">
          {filteredRuns.map(r => (
            <div 
              key={r.run_id}
              onClick={() => setSelectedRunId(r.run_id)}
              className={cn(
                "p-4 rounded-xl cursor-pointer transition-all border border-transparent",
                selectedRunId === r.run_id 
                  ? "bg-blue-600/10 border-blue-500/30 shadow-inner shadow-blue-500/5" 
                  : "hover:bg-white/[0.03] text-[#94a3b8] hover:text-white"
              )}
            >
              <div className="flex justify-between items-start mb-1">
                <div className="text-[0.7rem] font-mono font-bold truncate opacity-80">{r.run_id}</div>
                <div className={cn(
                  "w-1.5 h-1.5 rounded-full",
                  r.status === 'running' ? "bg-emerald-400 shadow-[0_0_5px_#10b981]" :
                  r.status === 'paused' ? "bg-amber-400" : "bg-[#64748b]"
                )} />
              </div>
              <div className="text-[0.75rem] font-medium line-clamp-2 leading-snug">{r.goal?.description || 'No goal defined'}</div>
              <div className="flex justify-between items-center mt-3 pt-3 border-t border-white/[0.03]">
                <span className={cn(
                  "text-[0.6rem] font-black uppercase tracking-widest",
                  r.status === 'running' ? "text-emerald-400" :
                  r.status === 'paused' ? "text-amber-400" : "text-[#64748b]"
                )}>{r.status}</span>
                <span className="text-[0.6rem] text-[#475569] font-mono">
                  {new Date(r.updated_at * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
            </div>
          ))}
          {filteredRuns.length === 0 && (
             <div className="text-center py-10 text-[#475569] text-xs font-medium italic">No matches found</div>
          )}
        </div>

        <div className="p-5 border-t border-white/5 bg-[#0a0d14]/50">
          <button 
            onClick={() => setShowComposer(true)}
            className="w-full py-3 bg-blue-600 hover:bg-blue-500 text-white rounded-xl font-bold text-sm transition-all shadow-lg shadow-blue-600/20 active:scale-95 flex items-center justify-center gap-2"
          >
            <Plus className="w-4 h-4" /> New Cognitive Run
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col overflow-hidden relative">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(59,130,246,0.03),transparent_60%)] pointer-events-none" />
        
        {/* Header */}
        <header className="px-8 py-5 bg-[#121620]/60 backdrop-blur-3xl border-b border-white/5 flex items-center justify-between z-10 shadow-sm">
          <div className="flex items-center gap-6 overflow-hidden">
            <div className="flex-shrink-0 w-10 h-10 bg-blue-600/10 border border-blue-500/20 rounded-xl flex items-center justify-center text-blue-400">
               <Cpu className="w-5 h-5" />
            </div>
            <div className="min-w-0">
              <h2 className="text-xl font-black font-mono tracking-tight truncate">{selectedRunId || 'System Standby'}</h2>
              <div className="flex items-center gap-3 mt-0.5">
                <p className="text-sm font-medium text-[#94a3b8] truncate max-w-[500px]">
                  {summary?.goal?.description || 'Initialize a run to begin monitoring execution state'}
                </p>
                {selectedRunId && (
                  <div className="flex items-center gap-2 bg-white/[0.03] px-2.5 py-0.5 rounded-full border border-white/5">
                    <div className={cn("w-1 h-1 rounded-full", connected ? "bg-emerald-400 shadow-[0_0_5px_#10b981] animate-pulse" : "bg-[#64748b]")} />
                    <span className="text-[0.6rem] font-black text-[#64748b] uppercase tracking-tighter">{connected ? 'Live Sync' : 'Offline'}</span>
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="flex gap-2 ml-4">
            {summary?.status === 'running' && (
              <HeaderAction onClick={() => client.pause(selectedRunId!)} icon={<Pause className="w-4 h-4" />} label="Pause" variant="warning" />
            )}
            {summary?.status === 'paused' && (
              <HeaderAction onClick={() => client.resume(selectedRunId!)} icon={<Play className="w-4 h-4" />} label="Resume" variant="success" />
            )}
            {selectedRunId && ['running', 'paused'].includes(summary?.status || '') && (
              <HeaderAction onClick={() => confirm('Terminate cognitive run?') && client.stop(selectedRunId!)} icon={<Square className="w-4 h-4" />} label="Stop" variant="danger" />
            )}
          </div>
        </header>

        {selectedRunId ? (
          <div className="flex-1 grid grid-cols-[340px_1fr_360px] h-full overflow-hidden">
            {/* Left Column: Health & Planning */}
            <div className="border-r border-white/5 flex flex-col overflow-hidden bg-black/5">
              <PanelHeader title="Runtime Health & Plan" />
              <div className="p-6 space-y-6 overflow-y-auto">
                {/* Metric Grid */}
                <div className="grid grid-cols-2 gap-4">
                  <MetricCard label="System Cycles" value={summary?.cycle_id || 0} icon={<Clock className="w-3 h-3" />} />
                  <MetricCard label="Total Actions" value={summary?.total_actions || 0} icon={<Zap className="w-3 h-3" />} />
                </div>

                {/* Regulation Card */}
                <Card title="Regulation Health" icon={<Shield className="w-3.5 h-3.5" />}>
                   <div className="space-y-3">
                      <HealthMetric label="Uncertainty Load" value={state?.uncertainty_load} color="blue" />
                      <HealthMetric label="Continuity Health" value={state?.continuity_health} color="emerald" />
                      <HealthMetric label="Goal Drift" value={state?.goal_drift} color="orange" />
                      <HealthMetric label="Overload Pressure" value={state?.overload_pressure} color="red" />
                   </div>
                </Card>

                {/* Plan View */}
                <Card title="Active Execution Plan" icon={<Layers className="w-3.5 h-3.5" />}>
                    {plan ? (
                      <div className="space-y-4">
                        <div className="flex justify-between items-center">
                          <span className={cn("px-2 py-0.5 rounded text-[0.6rem] font-black uppercase tracking-wider", 
                            plan.status === 'active' ? "bg-blue-500/20 text-blue-400" : 
                            plan.status === 'failed' ? "bg-red-500/20 text-red-400" : "bg-white/5 text-[#64748b]")}>
                            {plan.status}
                          </span>
                          <span className="text-[0.65rem] font-bold text-[#64748b] font-mono">{plan.current_step} / {plan.steps.length}</span>
                        </div>
                        <div className="space-y-3 relative">
                           <div className="absolute left-[7px] top-2 bottom-2 w-px bg-white/[0.05]" />
                           {plan.steps.map((s, i) => (
                             <div key={i} className="flex gap-4 relative">
                                <div className={cn("w-4 h-4 rounded-full flex-shrink-0 mt-0.5 flex items-center justify-center text-[0.5rem] font-black z-10",
                                  s.status === 'completed' ? "bg-emerald-500 text-white" :
                                  s.status === 'running' ? "bg-blue-500 text-white animate-pulse" :
                                  s.status === 'failed' ? "bg-red-500 text-white" : "bg-[#1a202c] border border-white/10 text-[#475569]"
                                )}>
                                  {s.status === 'completed' ? '✓' : i + 1}
                                </div>
                                <div className="min-w-0">
                                  <div className={cn("text-[0.75rem] font-semibold leading-tight mb-0.5", 
                                    s.status === 'pending' ? "text-[#64748b]" : "text-white")}>{s.description}</div>
                                  <div className="text-[0.65rem] font-mono text-blue-400/80 uppercase tracking-tighter">{s.tool_name}</div>
                                </div>
                             </div>
                           ))}
                        </div>
                      </div>
                    ) : (
                      <div className="text-center py-6 text-[#475569] text-xs font-medium italic">Runtime generator currently idle</div>
                    )}
                </Card>
              </div>
            </div>

            {/* Center Column: Views */}
            <div className="flex flex-col overflow-hidden">
              <div className="px-6 py-4 bg-white/[0.02] border-b border-white/5 flex items-center justify-between">
                <div className="text-[0.65rem] font-black text-[#475569] uppercase tracking-[0.25em]">
                  {activeTab === 'timeline' ? 'Live Event Sourcing' : activeTab === 'graph' ? 'Cognitive Graph' : 'Operator Terminal'}
                </div>
                <div className="flex bg-[#1a202c] rounded-lg border border-white/5 p-1">
                  <button onClick={() => setActiveTab('timeline')} className={cn("px-3 py-1 text-xs font-bold rounded transition-colors", activeTab === 'timeline' ? "bg-white/[0.05] text-white" : "text-[#475569] hover:text-[#94a3b8]")}>Timeline</button>
                  <button onClick={() => setActiveTab('graph')} className={cn("px-3 py-1 text-xs font-bold rounded transition-colors", activeTab === 'graph' ? "bg-white/[0.05] text-white" : "text-[#475569] hover:text-[#94a3b8]")}>Graph</button>
                  <button onClick={() => setActiveTab('terminal')} className={cn("px-3 py-1 text-xs font-bold rounded transition-colors", activeTab === 'terminal' ? "bg-white/[0.05] text-white" : "text-[#475569] hover:text-[#94a3b8]")}>Terminal</button>
                </div>
              </div>
              <div className="flex-1 overflow-hidden relative bg-[#0a0d14]">
                <div 
                  ref={timelineRef} 
                  className={cn("absolute inset-0 overflow-y-auto scroll-smooth", activeTab !== 'timeline' && 'hidden')}
                >
                  {events.length > 0 ? (
                    <div className="divide-y divide-white/[0.03]">
                      {events.map((e, i) => (
                        <EventRow key={i} event={e} />
                      ))}
                    </div>
                  ) : (
                    <div className="h-full flex flex-col items-center justify-center text-[#475569] gap-4">
                      <div className="w-16 h-16 rounded-full border-2 border-dashed border-white/[0.05] flex items-center justify-center">
                         <Clock className="w-6 h-6 opacity-20" />
                      </div>
                      <div className="text-xs font-bold uppercase tracking-[0.2em] opacity-40">Awaiting Cycle Transition</div>
                    </div>
                  )}
                </div>
                {activeTab === 'graph' && <CognitiveGraph state={state} />}
                {activeTab === 'terminal' && <TerminalOverride />}
              </div>
            </div>

            {/* Right Column: Cognitive State & Queue */}
            <div className="border-l border-white/5 flex flex-col overflow-hidden bg-black/5">
              <PanelHeader title="Introspection & Control" />
              <div className="p-6 space-y-6 overflow-y-auto">
                {/* Approvals */}
                {approvals.length > 0 && (
                  <Card title="Operator Approval Queue" icon={<Eye className="w-3.5 h-3.5" />} color="orange">
                    <div className="space-y-3">
                      {approvals.map((ap, i) => (
                        <div key={i} className="bg-orange-500/[0.03] border border-orange-500/20 rounded-xl p-4 space-y-3">
                           <div className="flex justify-between items-start">
                              <div className="text-[0.65rem] font-black text-orange-400 uppercase tracking-wider">{ap.tool_name}</div>
                              <div className="text-[0.55rem] font-mono text-orange-400/40">ID: {ap.action_id}</div>
                           </div>
                           <div className="text-[0.75rem] leading-snug font-medium">{ap.reason}</div>
                           <div className="text-[0.65rem] p-2 bg-black/20 rounded font-mono text-[#94a3b8] break-all">
                              {JSON.stringify(ap.arguments || ap.affected_resource)}
                           </div>
                           <div className="grid grid-cols-2 gap-2">
                              <button onClick={() => client.approve(ap.run_id, ap.action_id)} className="bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-400 border border-emerald-500/30 text-[0.65rem] font-black py-2 rounded-lg transition-all uppercase tracking-widest">Approve</button>
                              <button onClick={() => client.deny(ap.run_id, ap.action_id)} className="bg-red-500/20 hover:bg-red-500/30 text-red-400 border border-red-500/30 text-[0.65rem] font-black py-2 rounded-lg transition-all uppercase tracking-widest">Deny</button>
                           </div>
                        </div>
                      ))}
                    </div>
                  </Card>
                )}

                {/* State Inspector */}
                <Card title="Cognitive State Inspector" icon={<Activity className="w-3.5 h-3.5" />}>
                   <StateInspector state={state} />
                </Card>

                {/* Artifacts */}
                <Card title="Artifact Browser" icon={<FileText className="w-3.5 h-3.5" />}>
                   <div className="space-y-2">
                     {artifacts.map((a, i) => (
                       <div 
                        key={i} 
                        onClick={() => setSelectedArtifact(a)}
                        className="bg-white/[0.03] hover:bg-white/[0.06] border border-white/5 rounded-xl p-3 cursor-pointer transition-all flex items-center gap-3 group"
                       >
                          <div className="w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center text-blue-400 group-hover:bg-blue-500/20 transition-all">
                             <FileText className="w-4 h-4" />
                          </div>
                          <div className="min-w-0">
                            <div className="text-[0.7rem] font-bold truncate group-hover:text-blue-400 transition-colors">{a.title}</div>
                            <div className="text-[0.6rem] text-[#475569] font-mono mt-0.5">{a.type} • {new Date(a.created_at * 1000).toLocaleTimeString()}</div>
                          </div>
                       </div>
                     ))}
                     {artifacts.length === 0 && <div className="text-center py-6 text-[#475569] text-xs font-medium italic">No output objects generated</div>}
                   </div>
                </Card>
              </div>
            </div>
          </div>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-[#475569] gap-6 animate-in fade-in duration-700">
            <div className="w-24 h-24 rounded-[2rem] bg-blue-600/[0.03] border border-blue-500/[0.05] flex items-center justify-center text-blue-500/20">
               <Zap className="w-10 h-10" />
            </div>
            <div className="text-center space-y-2">
              <h3 className="text-xl font-black text-[#94a3b8] tracking-tight uppercase">Runtime Idle</h3>
              <p className="max-w-xs text-sm font-medium leading-relaxed opacity-60">Select an existing temporal thread or initiate a new cognitive objective to begin monitoring.</p>
            </div>
          </div>
        )}

        {/* Modals */}
        {showComposer && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#0a0d14]/90 backdrop-blur-md p-4 animate-in fade-in zoom-in-95 duration-200">
            <GoalComposer onSubmit={handleCreateRun} onCancel={() => setShowComposer(false)} />
          </div>
        )}

        {selectedArtifact && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#0a0d14]/95 backdrop-blur-md p-8 animate-in fade-in zoom-in-95 duration-200">
             <div className="bg-[#121620] border border-white/10 rounded-3xl w-full max-w-4xl h-full flex flex-col overflow-hidden shadow-2xl">
                <div className="p-6 border-b border-white/5 flex justify-between items-center bg-white/[0.01]">
                   <div className="flex items-center gap-4">
                      <div className="w-10 h-10 bg-blue-600/10 rounded-xl flex items-center justify-center text-blue-400">
                         <FileText className="w-5 h-5" />
                      </div>
                      <div>
                        <h3 className="text-lg font-bold">{selectedArtifact.title}</h3>
                        <p className="text-xs text-[#64748b] font-mono">{selectedArtifact.type} • {new Date(selectedArtifact.created_at * 1000).toLocaleString()}</p>
                      </div>
                   </div>
                   <button onClick={() => setSelectedArtifact(null)} className="p-2 hover:bg-white/5 rounded-full transition-colors text-[#64748b] hover:text-white">
                      <Plus className="w-6 h-6 rotate-45" />
                   </button>
                </div>
                <div className="flex-1 overflow-auto p-8 font-mono text-[0.8rem] leading-relaxed text-[#cbd5e0] selection:bg-blue-500/40">
                   <pre className="whitespace-pre-wrap">{typeof selectedArtifact.content === 'string' ? selectedArtifact.content : JSON.stringify(selectedArtifact.content, null, 2)}</pre>
                </div>
             </div>
          </div>
        )}
      </main>
    </div>
  );
};

// --- Sub-components ---

const PanelHeader = ({ title }: { title: string }) => (
  <div className="px-6 py-4 bg-white/[0.02] border-b border-white/5 text-[0.65rem] font-black text-[#475569] uppercase tracking-[0.25em]">
    {title}
  </div>
);

const Card = ({ title, icon, children, color = "blue" }: { title: string, icon: React.ReactNode, children: React.ReactNode, color?: string }) => (
  <div className="bg-[#121620]/40 border border-white/5 rounded-2xl overflow-hidden shadow-sm">
    <div className="px-4 py-3 bg-white/[0.01] border-b border-white/5 flex items-center gap-2">
       <span className={cn(color === "orange" ? "text-orange-400" : "text-blue-400")}>{icon}</span>
       <span className="text-[0.7rem] font-bold text-[#94a3b8] uppercase tracking-wider">{title}</span>
    </div>
    <div className="p-4">{children}</div>
  </div>
);

const MetricCard = ({ label, value, icon, className }: { label: string, value: string | number, icon: React.ReactNode, className?: string }) => (
  <div className={cn("bg-[#1a202c]/50 border border-white/5 rounded-2xl p-4 flex flex-col gap-1 shadow-sm group hover:border-blue-500/20 transition-all", className)}>
    <div className="flex items-center gap-1.5 opacity-40 group-hover:opacity-100 transition-all">
       <span className="text-blue-400">{icon}</span>
       <span className="text-[0.6rem] font-black text-[#64748b] uppercase tracking-widest">{label}</span>
    </div>
    <span className="text-xl font-black font-mono text-white mt-1">{value}</span>
  </div>
);

const HealthMetric = ({ label, value, color }: { label: string, value: number | undefined, color: string }) => {
  const v = value ?? 0;
  const pct = Math.min(100, Math.max(0, v * 100));
  const colors = {
    blue: "bg-blue-500",
    emerald: "bg-emerald-500",
    orange: "bg-orange-500",
    red: "bg-red-500"
  };
  return (
    <div className="space-y-1.5">
       <div className="flex justify-between items-center text-[0.65rem] font-bold">
          <span className="text-[#64748b]">{label}</span>
          <span className="text-[#94a3b8] font-mono">{(v * 100).toFixed(0)}%</span>
       </div>
       <div className="h-1 w-full bg-white/5 rounded-full overflow-hidden">
          <div className={cn("h-full transition-all duration-500", colors[color as keyof typeof colors])} style={{ width: `${pct}%` }} />
       </div>
    </div>
  );
};

const HeaderAction = ({ onClick, icon, label, variant }: { onClick: () => void, icon: React.ReactNode, label: string, variant: 'warning' | 'success' | 'danger' }) => {
  const styles = {
    warning: "border-orange-500/20 text-orange-400 hover:bg-orange-500/10",
    success: "border-emerald-500/20 text-emerald-400 hover:bg-emerald-500/10",
    danger: "border-red-500/20 text-red-400 hover:bg-red-500/10"
  };
  return (
    <button onClick={onClick} className={cn("px-4 py-2 bg-[#1a202c] border rounded-xl flex items-center gap-2 text-xs font-bold transition-all active:scale-95", styles[variant])}>
      {icon} {label}
    </button>
  );
};

const EventRow = ({ event }: { event: RuntimeEvent }) => {
  const [expanded, setExpanded] = useState(false);
  const typeStyles = {
    plan: "text-purple-400 bg-purple-400/5",
    approval: "text-orange-400 bg-orange-400/5",
    goal: "text-emerald-400 bg-emerald-400/5",
    error: "text-red-400 bg-red-400/5",
    tool: "text-blue-400 bg-blue-400/5"
  };
  const typeKey = event.type.split('_')[0] as keyof typeof typeStyles;
  
  return (
    <div 
      className={cn("px-8 py-5 hover:bg-white/[0.01] cursor-pointer transition-all border-l-2 border-transparent", expanded && "bg-white/[0.02] border-blue-500/50")}
      onClick={() => setExpanded(!expanded)}
    >
      <div className="flex gap-6 items-start">
        <div className="text-[0.65rem] font-mono text-[#475569] font-bold pt-1 w-8">{event.seq}</div>
        <div className="flex-1 min-w-0">
          <div className="flex justify-between items-center mb-1.5">
            <span className={cn("text-[0.65rem] font-black font-mono px-2 py-0.5 rounded tracking-tighter uppercase", typeStyles[typeKey] || "text-[#94a3b8] bg-white/5")}>
              {event.type}
            </span>
            <span className="text-[0.6rem] font-bold text-[#475569] font-mono">
              {new Date(event.created_at * 1000).toLocaleTimeString()}
            </span>
          </div>
          <div className={cn("text-[0.8rem] text-[#94a3b8] font-mono line-clamp-1 opacity-80", expanded && "hidden")}>
            {JSON.stringify(event.payload)}
          </div>
          {expanded && (
            <div className="mt-3 bg-black/40 border border-white/5 rounded-2xl p-5 text-[0.7rem] font-mono text-blue-200/60 whitespace-pre-wrap break-all shadow-inner leading-relaxed">
              {JSON.stringify(event.payload, null, 2)}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

const StateInspector = ({ state }: { state: any }) => {
  if (!state) return <div className="text-[0.7rem] text-[#475569] py-8 text-center font-medium italic">Introspection layer offline</div>;

  const fields = [
    { key: 'active_focus', label: 'Active Focus', icon: <Activity className="w-3 h-3" /> },
    { key: 'working_memory', label: 'Working Memory', icon: <Database className="w-3 h-3" /> },
    { key: 'hypotheses', label: 'Hypotheses', icon: <Layers className="w-3 h-3" /> },
    { key: 'tensions', label: 'Internal Tensions', icon: <AlertCircle className="w-3 h-3" /> },
    { key: 'pre_narrative', label: 'Pre-Narrative', icon: <MessageSquare className="w-3 h-3" /> },
    { key: 'post_narrative', label: 'Post-Narrative', icon: <MessageSquare className="w-3 h-3" /> },
    { key: 'interpretive_bias', label: 'Interpretive Bias', icon: <Target className="w-3 h-3" /> },
    { key: 'pending_options', label: 'Pending Options', icon: <Settings className="w-3 h-3" /> }
  ];

  return (
    <div className="space-y-2">
      {fields.map(f => {
        const val = state[f.key];
        if (val === undefined || val === null || (Array.isArray(val) && val.length === 0) || (typeof val === 'string' && val === '')) return null;
        return <AccordionItem key={f.key} label={f.label} icon={f.icon} value={val} />;
      })}
    </div>
  );
};

const AccordionItem = ({ label, icon, value }: { label: string, icon: React.ReactNode, value: any }) => {
  const [open, setOpen] = useState(false);
  return (
    <div className={cn("bg-[#1a202c]/30 border border-white/5 rounded-xl overflow-hidden transition-all", open && "border-blue-500/20 bg-[#1a202c]/60 shadow-lg")}>
      <div 
        onClick={() => setOpen(!open)}
        className="px-4 py-3 cursor-pointer hover:bg-white/[0.02] flex items-center justify-between transition-all"
      >
        <div className="flex items-center gap-3">
          <span className={cn("transition-colors", open ? "text-blue-400" : "text-[#475569]")}>{icon}</span>
          <span className={cn("text-[0.75rem] font-bold tracking-tight transition-colors", open ? "text-white" : "text-[#94a3b8]")}>{label}</span>
        </div>
        <ChevronDown className={cn("w-3 h-3 text-[#475569] transition-transform duration-300", open && "rotate-180 text-blue-400")} />
      </div>
      {open && (
        <div className="px-4 pb-4 pt-0 border-t border-white/[0.03] text-[0.65rem] font-mono text-[#94a3b8] whitespace-pre-wrap leading-relaxed overflow-x-auto selection:bg-blue-500/30">
          <div className="py-3">
            {typeof value === 'object' ? JSON.stringify(value, null, 2) : value}
          </div>
        </div>
      )}
    </div>
  );
};

const GoalComposer = ({ onSubmit, onCancel }: { onSubmit: (payload: any) => void, onCancel: () => void }) => {
  const [type, setType] = useState('operator_request');
  const [description, setDescription] = useState('');
  const [maxActions, setMaxActions] = useState(10);

  return (
    <div className="bg-[#121620] border border-white/10 rounded-[2rem] w-[540px] shadow-2xl overflow-hidden shadow-blue-500/10">
      <div className="p-8 border-b border-white/5 bg-white/[0.01]">
        <h2 className="text-2xl font-black tracking-tight">Initialize Objective</h2>
        <p className="text-sm font-medium text-[#64748b] mt-1">Configure the bounded goal and constraints for the cognitive runtime.</p>
      </div>
      <div className="p-8 space-y-6">
        <div className="space-y-2">
          <label className="text-[0.65rem] font-black text-[#475569] uppercase tracking-[0.2em] px-1">Tactical Mode</label>
          <select 
            value={type} 
            onChange={(e) => setType(e.target.value)}
            className="w-full bg-[#0a0d14] border border-white/10 rounded-2xl p-4 text-sm font-semibold focus:outline-none focus:border-blue-500/50 transition-all appearance-none cursor-pointer"
          >
            <option value="operator_request">Operator Request</option>
            <option value="inspect_workspace">Inspect Workspace</option>
            <option value="summarize_files">Summarize Files</option>
            <option value="extract_facts">Extract Facts</option>
            <option value="draft_note">Draft Note</option>
            <option value="propose_write">Propose Write</option>
          </select>
        </div>
        <div className="space-y-2">
          <label className="text-[0.65rem] font-black text-[#475569] uppercase tracking-[0.2em] px-1">Goal Description</label>
          <textarea 
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Define the specific achievement criteria..."
            className="w-full bg-[#0a0d14] border border-white/10 rounded-2xl p-4 text-sm font-medium focus:outline-none focus:border-blue-500/50 transition-all min-h-[120px] resize-none placeholder:text-[#475569]"
          />
        </div>
        <div className="grid grid-cols-1 gap-6">
          <div className="space-y-2">
            <label className="text-[0.65rem] font-black text-[#475569] uppercase tracking-[0.2em] px-1">Safety Constraint: Max Actions</label>
            <div className="relative">
               <input 
                type="number" 
                value={maxActions}
                onChange={(e) => setMaxActions(parseInt(e.target.value) || 0)}
                className="w-full bg-[#0a0d14] border border-white/10 rounded-2xl p-4 text-sm font-mono font-bold focus:outline-none focus:border-blue-500/50 transition-all"
              />
              <div className="absolute right-4 top-4 text-[0.6rem] font-black text-[#475569] uppercase">Actions</div>
            </div>
          </div>
        </div>
      </div>
      <div className="p-8 bg-white/[0.02] flex justify-end gap-4 border-t border-white/5">
        <button onClick={onCancel} className="px-6 py-3 text-sm font-black text-[#475569] hover:text-white transition-colors uppercase tracking-widest">Abort</button>
        <button 
          onClick={() => onSubmit({ goal: { type, description }, config: { max_actions: maxActions } })}
          className="bg-blue-600 hover:bg-blue-500 text-white px-8 py-3 rounded-2xl font-black text-sm transition-all shadow-xl shadow-blue-600/30 active:scale-95 uppercase tracking-widest"
        >
          Initialize Thread
        </button>
      </div>
    </div>
  );
};

export default App;
