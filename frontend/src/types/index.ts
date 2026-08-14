export interface ExplorationConfig {
  start_url: string;
  depth: number;
  max_time: number;
  browser_type: string;
  explore_visual: boolean;
  explore_console: boolean;
  explore_network: boolean;
  custom_instructions?: string;
}

export interface Finding {
  id: string;
  type: 'visual' | 'functional' | 'console' | 'network' | 'accessibility';
  severity: 'low' | 'medium' | 'high' | 'critical';
  title?: string;
  description: string;
  url: string;
  reproduction_steps: string[];
  screenshot?: string;
  timestamp?: string;
  created_at?: string;
}

export interface PathNode {
  id: string;
  step: number;
  action: string;
  url: string;
  timestamp: string;
  children: PathNode[];
}

export interface Metrics {
  statesExplored: number;
  bugsFound: number;
  coverage: number;
  anomaliesDetected: number;
  averageResponseTime: number;
}

export interface ExplorationSession {
  id: string;
  status: 'idle' | 'running' | 'paused' | 'completed' | 'error';
  startUrl: string;
  currentUrl: string;
  exploredPaths: PathNode[];
  findings: Finding[];
  metrics: Metrics;
  startTime?: string;
  endTime?: string;
}

export interface WebSocketMessage {
  type: string;
  data?: any;
  message?: string;
  timestamp: string;
}
