import React, { useState } from 'react';
import {
  Paper,
  Typography,
  TextField,
  Button,
  Slider,
  Switch,
  FormControlLabel,
  Grid,
  Box,
  Alert,
} from '@mui/material';
import { PlayArrow } from '@mui/icons-material';
import { ExplorationConfig } from '../types';

interface ControlPanelProps {
  onStart: (config: ExplorationConfig) => void;
  disabled?: boolean;
}

export const ControlPanel: React.FC<ControlPanelProps> = ({ onStart, disabled }) => {
  const [config, setConfig] = useState<ExplorationConfig>({
    start_url: 'https://example.com',
    depth: 5,
    max_time: 300,
    browser_type: 'chromium',
    explore_visual: true,
    explore_console: true,
    explore_network: true,
  });

  const handleChange = (field: keyof ExplorationConfig, value: any) => {
    setConfig(prev => ({ ...prev, [field]: value }));
  };

  return (
    <Paper sx={{ p: 3 }}>
      <Typography variant="h6" gutterBottom>
        Exploration Configuration
      </Typography>
      
      <Grid container spacing={3}>
        <Grid item xs={12}>
          <TextField
            fullWidth
            label="Start URL"
            value={config.start_url}
            onChange={(e) => handleChange('start_url', e.target.value)}
            placeholder="https://example.com"
          />
        </Grid>
        
        <Grid item xs={12}>
          <Typography gutterBottom>
            Exploration Depth: {config.depth}
          </Typography>
          <Slider
            value={config.depth}
            onChange={(_, value) => handleChange('depth', value)}
            min={1}
            max={10}
            marks
            valueLabelDisplay="auto"
          />
        </Grid>
        
        <Grid item xs={12}>
          <Typography gutterBottom>
            Max Time: {config.max_time} seconds
          </Typography>
          <Slider
            value={config.max_time}
            onChange={(_, value) => handleChange('max_time', value)}
            min={60}
            max={600}
            step={30}
            marks
            valueLabelDisplay="auto"
          />
        </Grid>
        
        <Grid item xs={12}>
          <FormControlLabel
            control={
              <Switch
                checked={config.explore_visual}
                onChange={(e) => handleChange('explore_visual', e.target.checked)}
              />
            }
            label="Explore Visual Issues"
          />
        </Grid>
        
        <Grid item xs={12}>
          <FormControlLabel
            control={
              <Switch
                checked={config.explore_console}
                onChange={(e) => handleChange('explore_console', e.target.checked)}
              />
            }
            label="Monitor Console Errors"
          />
        </Grid>
        
        <Grid item xs={12}>
          <FormControlLabel
            control={
              <Switch
                checked={config.explore_network}
                onChange={(e) => handleChange('explore_network', e.target.checked)}
              />
            }
            label="Monitor Network Requests"
          />
        </Grid>
        
        <Grid item xs={12}>
          <Button
            fullWidth
            variant="contained"
            color="primary"
            startIcon={<PlayArrow />}
            onClick={() => onStart(config)}
            disabled={disabled}
          >
            Start Exploration
          </Button>
        </Grid>
      </Grid>
    </Paper>
  );
};