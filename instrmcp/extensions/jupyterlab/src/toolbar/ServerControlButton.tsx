import React from 'react';
import { PlayIcon, StopIcon } from './icons';

interface Props {
  running: boolean;
  onStart: () => void;
  onStop: () => void;
}

const ServerControlButton: React.FC<Props> = ({ running, onStart, onStop }) => {
  const handleClick = () => {
    if (running) {
      onStop();
    } else {
      onStart();
    }
  };

  return (
    <button
      className={`mcp-btn mcp-server-btn ${running ? 'running' : 'stopped'}`}
      onClick={handleClick}
      title={running ? 'Stop MCP server' : 'Start MCP server'}
    >
      {running ? <StopIcon /> : <PlayIcon />}
      <span>{running ? 'Stop' : 'Start'}</span>
    </button>
  );
};

export default ServerControlButton;
