import axios from 'axios';
import { ExplorationConfig } from '../types';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const explorationAPI = {
  startExploration: async (config: ExplorationConfig) => {
    const response = await api.post('/api/explore/start', config);
    return response.data;
  },

  stopExploration: async (sessionId: string) => {
    const response = await api.post(`/api/explore/stop/${sessionId}`);
    return response.data;
  },

  getSessionStatus: async (sessionId: string) => {
    const response = await api.get(`/api/explore/status/${sessionId}`);
    return response.data;
  },

  healthCheck: async () => {
    const response = await api.get('/health');
    return response.data;
  },
};
