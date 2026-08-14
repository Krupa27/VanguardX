import React from 'react';
import {
  Paper,
  Typography,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Chip,
  Box,
  IconButton,
  Collapse,
  Alert,
} from '@mui/material';
import {
  BugReport,
  Warning,
  Error,
  Info,
  ExpandMore,
  ExpandLess,
} from '@mui/icons-material';
import { Finding } from '../types';

interface FindingsPanelProps {
  findings: Finding[];
}

export const FindingsPanel: React.FC<FindingsPanelProps> = ({ findings }) => {
  const [expanded, setExpanded] = React.useState<string | null>(null);

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'critical':
        return <Error color="error" />;
      case 'high':
        return <Warning color="warning" />;
      case 'medium':
        return <Info color="info" />;
      default:
        return <BugReport color="success" />;
    }
  };

  const formatTimestamp = (finding: Finding) => {
    const raw = finding.timestamp || finding.created_at;
    if (!raw) return '';
    const date = new Date(raw);
    return Number.isNaN(date.getTime()) ? '' : date.toLocaleString();
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical':
        return 'error';
      case 'high':
        return 'warning';
      case 'medium':
        return 'info';
      default:
        return 'success';
    }
  };

  return (
    <Paper sx={{ p: 2, maxHeight: '600px', overflow: 'auto' }}>
      <Typography variant="h6" gutterBottom>
        Findings ({findings.length})
      </Typography>
      
      {findings.length === 0 ? (
        <Alert severity="info">
          No findings yet. Start exploration to discover issues.
        </Alert>
      ) : (
        <List>
          {findings.map((finding) => (
            <ListItem
              key={finding.id}
              alignItems="flex-start"
              sx={{ flexDirection: 'column', mb: 2 }}
            >
              <Box sx={{ display: 'flex', width: '100%', alignItems: 'center' }}>
                <ListItemIcon>
                  {getSeverityIcon(finding.severity)}
                </ListItemIcon>
                <ListItemText
                  primary={
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Typography variant="subtitle1">
                        {finding.title || finding.description}
                      </Typography>
                      <Chip
                        label={finding.severity}
                        size="small"
                        color={getSeverityColor(finding.severity) as any}
                      />
                      <Chip
                        label={finding.type}
                        size="small"
                        variant="outlined"
                      />
                    </Box>
                  }
                  secondary={
                    <>
                      <Typography variant="body2" color="textSecondary">
                        URL: {finding.url}
                      </Typography>
                      <Typography variant="caption" color="textSecondary">
                        {formatTimestamp(finding)}
                      </Typography>
                    </>
                  }
                />
                <IconButton
                  onClick={() => setExpanded(expanded === finding.id ? null : finding.id)}
                >
                  {expanded === finding.id ? <ExpandLess /> : <ExpandMore />}
                </IconButton>
              </Box>
              
              <Collapse in={expanded === finding.id} timeout="auto" unmountOnExit>
                <Box sx={{ pl: 4, pr: 2, pb: 2 }}>
                  <Typography variant="subtitle2" gutterBottom>
                    Reproduction Steps:
                  </Typography>
                  <ol>
                    {finding.reproduction_steps?.map((step, index) => (
                      <li key={index}>
                        <Typography variant="body2">{step}</Typography>
                      </li>
                    ))}
                  </ol>
                </Box>
              </Collapse>
            </ListItem>
          ))}
        </List>
      )}
    </Paper>
  );
};