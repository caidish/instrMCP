import React from 'react';
import ServerControlButton from './ServerControlButton';
import ModeSelector from './ModeSelector';
import OptionsPanel from './OptionsPanel';
import StatusIndicator from './StatusIndicator';
import { MCPMode, MCPState } from './types';

interface Props {
  state: MCPState;
  onStart: () => void;
  onStop: () => void;
  onRestart: () => void;
  onReset: () => void;
  onSetMode: (mode: MCPMode) => void;
  onToggleOption: (option: string, enabled: boolean) => void;
}

const MCPToolbarComponent: React.FC<Props> = ({
  state,
  onStart,
  onStop,
  onRestart,
  onReset,
  onSetMode,
  onToggleOption
}) => {
  return (
    <div className="mcp-toolbar-container">
      <ServerControlButton running={state.serverRunning} onStart={onStart} onStop={onStop} />
      <ModeSelector
        mode={state.mode}
        disabled={state.serverRunning}
        onChange={mode => onSetMode(mode)}
      />
      <OptionsPanel
        options={state.availableOptions}
        enabledOptions={state.enabledOptions}
        disabled={state.serverRunning}
        currentMode={state.mode}
        onToggle={onToggleOption}
      />
      <button
        className="mcp-btn mcp-restart"
        onClick={onRestart}
        disabled={!state.serverRunning}
        title="Restart MCP server"
      >
        ⟳
        <span>Restart</span>
      </button>
      <button
        className="mcp-btn mcp-reset"
        onClick={onReset}
        title="Reset toolbar connection (use after kernel restart)"
      >
        ↺
        <span>Reset</span>
      </button>
      <StatusIndicator state={state} />
    </div>
  );
};

export default MCPToolbarComponent;
