import React from 'react';
import { ChevronIcon, ShieldIcon, SkullIcon, WarningIcon } from './icons';
import { MCPMode } from './types';

interface Props {
  mode: MCPMode;
  disabled?: boolean;
  onChange: (mode: MCPMode) => void;
}

const ModeSelector: React.FC<Props> = ({ mode, disabled = false, onChange }) => {
  const icon =
    mode === 'safe' ? <ShieldIcon /> : mode === 'unsafe' ? <WarningIcon /> : <SkullIcon />;

  return (
    <div className={`mcp-mode-selector mode-${mode}`}>
      <div className="mcp-mode-pill">
        {icon}
        <span className="mcp-mode-label">{mode}</span>
        <ChevronIcon />
      </div>
      <select
        className="mcp-mode-select"
        value={mode}
        disabled={disabled}
        onChange={evt => onChange(evt.target.value as MCPMode)}
        aria-label="Select MCP mode"
      >
        <option value="safe">safe</option>
        <option value="unsafe">unsafe</option>
        <option value="dangerous">dangerous</option>
      </select>
    </div>
  );
};

export default ModeSelector;
