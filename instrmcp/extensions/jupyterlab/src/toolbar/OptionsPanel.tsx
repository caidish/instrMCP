import React from 'react';
import { GearIcon } from './icons';
import { MCPOptionInfo } from './types';

interface Props {
  options: MCPOptionInfo[];
  enabledOptions: string[];
  disabled?: boolean;
  onToggle: (option: string, enabled: boolean) => void;
}

const OptionsPanel: React.FC<Props> = ({
  options,
  enabledOptions,
  disabled = false,
  onToggle
}) => {
  const [open, setOpen] = React.useState(false);

  React.useEffect(() => {
    if (disabled) {
      setOpen(false);
    }
  }, [disabled]);

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
              className="mcp-option-item"
              title={option.description || option.name}
            >
              <input
                type="checkbox"
                checked={enabledOptions.includes(option.name)}
                disabled={disabled}
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
