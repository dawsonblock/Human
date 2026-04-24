export type EventType = 
  | 'cycle_completed' | 'tool_call_executed' | 'tool_call_failed'
  | 'plan_created' | 'plan_step_completed' | 'plan_step_failed' | 'plan_step_started'
  | 'goal_completed' | 'approval_requested' | 'approval_granted' | 'approval_denied'
  | 'run_finished' | 'run_paused' | 'run_resumed';

export interface RuntimeEvent {
  run_id: string;
  seq: number;
  type: EventType;
  payload: unknown;
  created_at: number;
}

export function subscribeToEvents(runId: string, onEvent: (event: RuntimeEvent) => void, onConnectionChange: (connected: boolean) => void) {
  const sse = new EventSource(`/api/runs/${runId}/events`);

  const handleEvent = (data: string) => {
    try {
      const event = JSON.parse(data);
      onEvent(event);
    } catch (e) {
      console.error('Failed to parse event', e);
    }
  };

  sse.onopen = () => onConnectionChange(true);
  sse.onerror = () => onConnectionChange(false);

  const eventTypes: EventType[] = [
    'cycle_completed', 'tool_call_executed', 'tool_call_failed',
    'plan_created', 'plan_step_completed', 'plan_step_failed', 'plan_step_started',
    'goal_completed', 'approval_requested', 'approval_granted', 'approval_denied',
    'run_finished', 'run_paused', 'run_resumed'
  ];

  eventTypes.forEach(type => {
    sse.addEventListener(type, (e: MessageEvent) => handleEvent(e.data));
  });

  return () => sse.close();
}
