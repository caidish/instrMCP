import React from 'react';
import { MCPState } from './types';

interface Props {
  state: MCPState;
}

const StatusIndicator: React.FC<Props> = ({ state }) => {
  const { serverRunning, host, port, mode } = state;
  const label = serverRunning
    ? `Server running (${host || 'localhost'}:${port ?? '–'})`
    : 'Server stopped';

  return (
    <div className={`mcp-status ${serverRunning ? 'running' : 'stopped'} mode-${mode}`} title={label}>
      <span className="mcp-status-dot" aria-hidden="true" />
      <span className="mcp-status-text">{serverRunning ? 'Running' : 'Stopped'}</span>
      {serverRunning && port != null && <span className="mcp-status-port">:{port}</span>}
    </div>
  );
};

export default StatusIndicator;
