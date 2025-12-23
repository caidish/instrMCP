import React from 'react';
import { GearIcon } from './icons';
import { MCPMode, MCPOptionInfo } from './types';

interface Props {
  options: MCPOptionInfo[];
  enabledOptions: string[];
  disabled?: boolean;
  currentMode: MCPMode;
  onToggle: (option: string, enabled: boolean) => void;
}

const OptionsPanel: React.FC<Props> = ({
  options,
  enabledOptions,
  disabled = false,
  currentMode,
  onToggle
}) => {
  const [open, setOpen] = React.useState(false);

  React.useEffect(() => {
    if (disabled) {
      setOpen(false);
    }
  }, [disabled]);

  // Check if an option should be disabled based on mode requirements
  const isOptionDisabled = (option: MCPOptionInfo): boolean => {
    if (disabled) return true;
    if (option.requires_mode && option.requires_mode !== currentMode) {
      return true;
    }
    return false;
  };

  // Build tooltip with mode requirement info
  const getOptionTitle = (option: MCPOptionInfo): string => {
    let title = option.description || option.name;
    if (option.requires_mode && option.requires_mode !== currentMode) {
      title += ` (requires ${option.requires_mode} mode)`;
    }
    return title;
  };

  return (
    <div className="mcp-options">
      <button
        className="mcp-btn mcp-gear"
        disabled={disabled}
        onClick={() => setOpen(prev => !prev)}
        title="Toggle MCP options"
      >
        <GearIcon />
        <span>Options</span>
      </button>
      {open && (
        <div className="mcp-options-dropdown" onMouseLeave={() => setOpen(false)}>
          {options.length === 0 && (
            <div className="mcp-option-item empty">No options available</div>
          )}
          {options.map(option => (
            <label
              key={option.name}
              className={`mcp-option-item${isOptionDisabled(option) ? ' disabled' : ''}`}
              title={getOptionTitle(option)}
            >
              <input
                type="checkbox"
                checked={enabledOptions.includes(option.name)}
                disabled={isOptionDisabled(option)}
                onChange={evt => onToggle(option.name, evt.target.checked)}
              />
              <span>{option.name}</span>
            </label>
          ))}
        </div>
      )}
    </div>
  );
};

export default OptionsPanel;
