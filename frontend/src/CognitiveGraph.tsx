import React, { useMemo } from 'react';
import { ReactFlow, Background, Controls, MarkerType } from '@xyflow/react';
import type { Node, Edge } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import type { AgentState } from './api/client';

export const CognitiveGraph: React.FC<{ state: AgentState | null }> = ({ state }) => {
  const { nodes, edges } = useMemo(() => {
    if (!state) return { nodes: [], edges: [] };
    
    const nodes: Node[] = [];
    const edges: Edge[] = [];
    
    // Core runtime node
    nodes.push({
      id: 'core',
      position: { x: 400, y: 50 },
      data: { label: 'Cognitive Core' },
      style: { background: '#1e293b', color: '#fff', border: '1px solid #3b82f6', borderRadius: '8px' }
    });

    // Active Goal
    if (state.active_goal) {
      nodes.push({
        id: 'goal',
        position: { x: 200, y: 150 },
        data: { label: `Goal: ${state.active_goal.type}` },
        style: { background: '#0f766e', color: '#fff', border: '1px solid #14b8a6', borderRadius: '8px' }
      });
      edges.push({ id: 'core-goal', source: 'core', target: 'goal', animated: true, markerEnd: { type: MarkerType.ArrowClosed } });
    }

    // Active Plan
    if (state.active_plan) {
      nodes.push({
        id: 'plan',
        position: { x: 200, y: 250 },
        data: { label: `Plan (${state.active_plan.status})` },
        style: { background: '#4338ca', color: '#fff', border: '1px solid #6366f1', borderRadius: '8px' }
      });
      if (state.active_goal) {
        edges.push({ id: 'goal-plan', source: 'goal', target: 'plan', animated: true, markerEnd: { type: MarkerType.ArrowClosed } });
      } else {
        edges.push({ id: 'core-plan', source: 'core', target: 'plan', animated: true, markerEnd: { type: MarkerType.ArrowClosed } });
      }
    }

    // Active Focus
    if (state.active_focus && state.active_focus.length > 0) {
      nodes.push({
        id: 'focus',
        position: { x: 600, y: 150 },
        data: { label: `Focus: ${state.active_focus.length} cands` },
        style: { background: '#b45309', color: '#fff', border: '1px solid #f59e0b', borderRadius: '8px' }
      });
      edges.push({ id: 'core-focus', source: 'core', target: 'focus', animated: true, markerEnd: { type: MarkerType.ArrowClosed } });
    }
    
    // Tensions
    if (state.tensions && state.tensions.length > 0) {
      nodes.push({
        id: 'tensions',
        position: { x: 800, y: 150 },
        data: { label: `Tensions: ${state.tensions.length}` },
        style: { background: '#b91c1c', color: '#fff', border: '1px solid #ef4444', borderRadius: '8px' }
      });
      edges.push({ id: 'core-tensions', source: 'core', target: 'tensions', animated: true, markerEnd: { type: MarkerType.ArrowClosed } });
    }

    return { nodes, edges };
  }, [state]);

  return (
    <div className="w-full h-full bg-[#0a0d14]">
      <ReactFlow nodes={nodes} edges={edges} fitView>
        <Background color="#334155" gap={16} />
        <Controls />
      </ReactFlow>
    </div>
  );
};
