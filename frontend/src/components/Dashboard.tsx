import React, { useState } from 'react';
import {
  Container,
  Grid,
  Box,
  AppBar,
  Toolbar,
  Typography,
  Chip,
  Alert,
  Button,
} from '@mui/material';
import { ControlPanel } from './ControlPanel';
import { FindingsPanel } from './FindingsPanel';
import { useWebSocket } from '../hooks/useWebSocket';
import { explorationAPI } from '../services/api';
import { ExplorationConfig, ExplorationSession, Finding } from '../types';

export const Dashboard: React.FC = () => {
  const [session, setSession] = useState<ExplorationSession>({
    id: '',
    status: 'idle',
    startUrl: '',
    currentUrl: '',
    exploredPaths: [],
    findings: [],
    metrics: {
      statesExplored: 0,
      bugsFound: 0,
      coverage: 0,
      anomaliesDetected: 0,
      averageResponseTime: 0,
    },
  });

  // Derived from the same base URL api.ts uses, so both point at one backend.
  const wsBase = (process.env.REACT_APP_API_URL || 'http://localhost:8000')
    .replace(/^http/, 'ws');

  const { connected, sendMessage } = useWebSocket(
    `${wsBase}/ws/${session.id || 'default'}`,
    {
      onMessage: (data) => {
        handleWebSocketMessage(data);
      },
    }
  );

  const handleWebSocketMessage = (data: any) => {
    console.log('Received:', data);

    switch (data.type) {
      case 'status':
        setSession(prev => ({ ...prev, status: 'running' }));
        break;
        
      case 'state_update':
        setSession(prev => ({
          ...prev,
          currentUrl: data.path?.url || prev.currentUrl,
          metrics: {
            ...prev.metrics,
            statesExplored: prev.metrics.statesExplored + 1,
          },
        }));
        break;
        
      case 'finding':
        setSession(prev => ({
          ...prev,
          findings: [...prev.findings, data.finding],
          metrics: {
            ...prev.metrics,
            bugsFound: prev.metrics.bugsFound + 1,
          },
        }));
        break;
        
      case 'complete':
        setSession(prev => ({ ...prev, status: 'completed' }));
        break;
        
      case 'error':
        setSession(prev => ({ ...prev, status: 'error' }));
        break;
    }
  };

  const handleStart = async (config: ExplorationConfig) => {
    try {
      const result = await explorationAPI.startExploration(config);
      setSession(prev => ({
        ...prev,
        id: result.session_id,
        status: 'running',
        startUrl: config.start_url,
      }));
    } catch (error) {
      console.error('Failed to start:', error);
    }
  };

  return (
    <Box sx={{ flexGrow: 1 }}>
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            Vanguard-X Explorer
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            <Chip
              label={connected ? 'Connected' : 'Disconnected'}
              color={connected ? 'success' : 'error'}
              size="small"
            />
            <Button
              variant="outlined"
              size="small"
              onClick={() => {
                console.log('Debug - session:', session.id, 'connected:', connected);
                try { sendMessage?.({ type: 'ping' }); } catch (e) { console.warn('sendMessage failed', e); }
              }}
            >
              Debug
            </Button>
          </Box>
        </Toolbar>
      </AppBar>

      <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
        <Grid container spacing={3}>
          <Grid item xs={12} md={4}>
            <ControlPanel onStart={handleStart} disabled={session.status === 'running'} />
          </Grid>
          
          <Grid item xs={12} md={8}>
            {session.status === 'running' && (
              <Alert severity="info" sx={{ mb: 2 }}>
                Exploring: {session.currentUrl || session.startUrl}
              </Alert>
            )}
            <FindingsPanel findings={session.findings} />
          </Grid>
        </Grid>
      </Container>
    </Box>
  );
};
