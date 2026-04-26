import React, { useMemo } from 'react';
import { ReactFlow, Background, Controls, MarkerType, Handle, Position } from '@xyflow/react';
import type { Node, Edge } from '@xyflow/react';
import { Target, Layers, Eye, Activity, AlertCircle, Cpu } from 'lucide-react';
import '@xyflow/react/dist/style.css';
import type { AgentState } from './api/client';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const CustomNode = ({ data }: any) => {
  const Icon = data.icon || Activity;
  return (
    <div className={cn(
      "px-4 py-3 rounded-2xl border-2 shadow-sm min-w-[160px] bg-white transition-all",
      data.color === 'blue' && "border-blue-500/20 text-blue-700 shadow-blue-500/5",
      data.color === 'indigo' && "border-indigo-500/20 text-indigo-700 shadow-indigo-500/5",
      data.color === 'emerald' && "border-emerald-500/20 text-emerald-700 shadow-emerald-500/5",
      data.color === 'orange' && "border-orange-500/20 text-orange-700 shadow-orange-500/5",
      data.color === 'red' && "border-red-500/20 text-red-700 shadow-red-500/5",
      data.color === 'slate' && "border-slate-500/20 text-slate-700 shadow-slate-500/5",
    )}>
      <Handle type="target" position={Position.Top} className="!bg-slate-300" />
      <div className="flex items-center gap-3">
        <div className={cn(
          "w-8 h-8 rounded-lg flex items-center justify-center",
          data.color === 'blue' && "bg-blue-50",
          data.color === 'indigo' && "bg-indigo-50",
          data.color === 'emerald' && "bg-emerald-50",
          data.color === 'orange' && "bg-orange-50",
          data.color === 'red' && "bg-red-50",
          data.color === 'slate' && "bg-slate-50",
        )}>
          <Icon className="w-4 h-4" />
        </div>
        <div className="flex flex-col">
          <span className="text-[0.6rem] font-black uppercase tracking-widest opacity-50">{data.type}</span>
          <span className="text-xs font-bold leading-tight truncate max-w-[100px]">{data.label}</span>
        </div>
      </div>
      <Handle type="source" position={Position.Bottom} className="!bg-slate-300" />
    </div>
  );
};

const nodeTypes = {
  custom: CustomNode,
};

export const CognitiveGraph: React.FC<{ state: AgentState | null }> = ({ state }) => {
  const { nodes, edges } = useMemo(() => {
    if (!state) return { nodes: [], edges: [] };
    
    const nodes: Node[] = [];
    const edges: Edge[] = [];
    
    // Core runtime node
    nodes.push({
      id: 'core',
      type: 'custom',
      position: { x: 400, y: 50 },
      data: { label: 'Cognitive Core', type: 'Runtime', icon: Cpu, color: 'blue' },
    });

    // Active Goal
    if (state.active_goal) {
      nodes.push({
        id: 'goal',
        type: 'custom',
        position: { x: 200, y: 200 },
        data: { label: state.active_goal.type, type: 'Active Goal', icon: Target, color: 'emerald' },
      });
      edges.push({ 
        id: 'core-goal', 
        source: 'core', 
        target: 'goal', 
        animated: true, 
        style: { stroke: '#10b981', strokeWidth: 2 },
        markerEnd: { type: MarkerType.ArrowClosed, color: '#10b981' } 
      });
    }

    // Active Plan
    if (state.active_plan) {
      nodes.push({
        id: 'plan',
        type: 'custom',
        position: { x: 200, y: 350 },
        data: { label: state.active_plan.status, type: 'Current Plan', icon: Layers, color: 'indigo' },
      });
      const source = state.active_goal ? 'goal' : 'core';
      edges.push({ 
        id: `${source}-plan`, 
        source: source, 
        target: 'plan', 
        animated: true, 
        style: { stroke: '#6366f1', strokeWidth: 2 },
        markerEnd: { type: MarkerType.ArrowClosed, color: '#6366f1' } 
      });
    }

    // Active Focus
    if (state.active_focus && state.active_focus.length > 0) {
      nodes.push({
        id: 'focus',
        type: 'custom',
        position: { x: 600, y: 200 },
        data: { label: `${state.active_focus.length} Candidates`, type: 'Focus', icon: Eye, color: 'orange' },
      });
      edges.push({ 
        id: 'core-focus', 
        source: 'core', 
        target: 'focus', 
        animated: true, 
        style: { stroke: '#f59e0b', strokeWidth: 2 },
        markerEnd: { type: MarkerType.ArrowClosed, color: '#f59e0b' } 
      });
    }
    
    // Tensions
    if (state.tensions && state.tensions.length > 0) {
      nodes.push({
        id: 'tensions',
        type: 'custom',
        position: { x: 800, y: 200 },
        data: { label: `${state.tensions.length} Active`, type: 'Tensions', icon: AlertCircle, color: 'red' },
      });
      edges.push({ 
        id: 'core-tensions', 
        source: 'core', 
        target: 'tensions', 
        animated: true, 
        style: { stroke: '#ef4444', strokeWidth: 2 },
        markerEnd: { type: MarkerType.ArrowClosed, color: '#ef4444' } 
      });
    }

    return { nodes, edges };
  }, [state]);

  return (
    <div className="w-full h-full bg-white">
      <ReactFlow 
        nodes={nodes} 
        edges={edges} 
        nodeTypes={nodeTypes}
        fitView
        colorMode="light"
      >
        <Background color="#f1f5f9" gap={20} />
        <Controls showInteractive={false} className="bg-white border-slate-200 shadow-sm rounded-xl overflow-hidden" />
      </ReactFlow>
    </div>
  );
};
