import React from 'react';
import { ReactWidget } from '@jupyterlab/apputils';
import { NotebookPanel } from '@jupyterlab/notebook';
import { Kernel } from '@jupyterlab/services';
import MCPToolbarComponent from './MCPToolbarComponent';
import { MCPMode, MCPState, MCPStatusUpdate, ToolbarSharedState } from './types';

const DEFAULT_STATE: MCPState = {
  serverRunning: false,
  mode: 'safe',
  enabledOptions: [],
  availableOptions: [],
  host: null,
  port: null,
  dangerous: false
};

export class MCPToolbarWidget extends ReactWidget {
  private _panel: NotebookPanel;
  private _shared: ToolbarSharedState;
  private _state: MCPState = { ...DEFAULT_STATE };
  private _controlComm: Kernel.IComm | null = null;
  private _kernelRestarting: boolean = false;

  constructor(panel: NotebookPanel, sharedState: ToolbarSharedState) {
    super();
    this._panel = panel;
    this._shared = sharedState;
    this.addClass('mcp-toolbar-widget');

    this._shared.statusUpdateSignal.connect(this._onStatusUpdate, this);
    this._panel.sessionContext.kernelChanged.connect(this._onKernelChanged, this);

    // Listen to kernel status changes to detect restarts
    const kernel = this._panel.sessionContext.session?.kernel;
    if (kernel) {
      kernel.statusChanged.connect(this._onKernelStatusChanged, this);
    }

    void this._initialize();
  }

  dispose(): void {
    this._shared.statusUpdateSignal.disconnect(this._onStatusUpdate, this);
    this._panel.sessionContext.kernelChanged.disconnect(this._onKernelChanged, this);
    const kernel = this._panel.sessionContext.session?.kernel;
    if (kernel) {
      kernel.statusChanged.disconnect(this._onKernelStatusChanged, this);
    }
    this._closeControlComm();
    super.dispose();
  }

  render(): React.ReactElement {
    return (
      <MCPToolbarComponent
        state={this._state}
        onStart={this._handleStart}
        onStop={this._handleStop}
        onRestart={this._handleRestart}
        onReset={this._handleReset}
        onSetMode={this._handleModeChange}
        onToggleOption={this._handleOptionToggle}
      />
    );
  }

  private async _initialize(): Promise<void> {
    await this._panel.sessionContext.ready;
    await this._openControlComm();
  }

  private async _openControlComm(): Promise<void> {
    // Always close existing comm first
    this._closeControlComm();

    const kernel = this._panel.sessionContext.session?.kernel;
    if (!kernel || kernel.status === 'dead' || kernel.status === 'restarting') {
      return;
    }

    try {
      const comm = kernel.createComm('mcp:toolbar_control');
      comm.onMsg = (msg: any) => {
        // Guard against disposed widget
        if (this.isDisposed) return;
        this._handleControlMessage(msg);
      };
      comm.onClose = () => {
        // Comm was closed (kernel shutdown, etc.) - clear our reference
        this._controlComm = null;
      };
      this._controlComm = comm;
      await comm.open();  // Wait for open to complete
      this._requestStatus();
    } catch (error) {
      console.warn('MCP Toolbar: failed to open control comm', error);
      this._controlComm = null;
    }
  }

  private _requestStatus(): void {
    this._sendControlMessage({ type: 'get_status' });
  }

  private _handleControlMessage(msg: any): void {
    const data = msg?.content?.data || {};
    const msgType = data.type;

    if (msgType === 'status') {
      this._applyDetails(data);
    } else if (msgType === 'result' && data.details) {
      this._applyDetails(data.details);
    } else if (msgType === 'status_broadcast' && data.details) {
      // Handle broadcasts sent through the control comm (instead of separate status comm)
      this._applyDetails(data.details);
    }
  }

  private _onStatusUpdate = (sender: object, update: MCPStatusUpdate): void => {
    const kernel = this._panel.sessionContext.session?.kernel;
    if (!kernel || update.kernel !== kernel) {
      return;
    }

    this._applyDetails(update.details);

    if (update.status === 'server_stopped') {
      this._state = { ...this._state, serverRunning: false };
      this.update();
    }

    // When kernel comes back and server not started, refresh comm and status
    if (update.status === 'server_not_started') {
      void this._openControlComm();
    }
  };

  private _applyDetails(details: any): void {
    if (!details) {
      return;
    }

    const next: MCPState = { ...this._state };

    const enabledOptions = details.enabled_options ?? details.enabledOptions;
    if (Array.isArray(enabledOptions)) {
      next.enabledOptions = [...enabledOptions];
    }

    const availableOptions = details.available_options ?? details.availableOptions;
    if (Array.isArray(availableOptions)) {
      next.availableOptions = [...availableOptions];
    }

    if (typeof details.host !== 'undefined') {
      next.host = details.host;
    }

    if (typeof details.port !== 'undefined') {
      next.port = details.port;
    }

    if (typeof details.server_running === 'boolean') {
      next.serverRunning = details.server_running;
    }

    if (typeof details.dangerous === 'boolean') {
      next.dangerous = details.dangerous;
    }

    if (typeof details.mode === 'string') {
      next.mode = details.mode as MCPMode;
    }

    if (next.dangerous) {
      next.mode = 'dangerous';
    }

    this._state = next;
    this.update();
  }

  private _handleStart = (): void => {
    this._sendControlMessage({ type: 'start_server' });
  };

  private _handleStop = (): void => {
    this._sendControlMessage({ type: 'stop_server' });
  };

  private _handleRestart = (): void => {
    this._sendControlMessage({ type: 'restart_server' });
  };

  private _handleReset = (): void => {
    console.log('MCP Toolbar: Manual reset triggered');

    // 1. Clear kernel restart flag
    this._kernelRestarting = false;

    // 2. Close comm completely
    this._closeControlComm();

    // 3. Reset state to defaults
    this._state = { ...DEFAULT_STATE };
    this.update();

    // 4. Delay then reconnect (give kernel time to stabilize)
    setTimeout(() => {
      if (!this.isDisposed) {
        void this._openControlComm();
      }
    }, 200);
  };

  private _handleModeChange = (mode: MCPMode): void => {
    if (mode === this._state.mode) {
      return;
    }
    // Guard: should be disabled in UI already, but double-check
    if (this._state.serverRunning) {
      return;
    }
    this._sendControlMessage({ type: 'set_mode', mode });
  };

  private _handleOptionToggle = (option: string, enabled: boolean): void => {
    // Guard: should be disabled in UI already, but double-check
    if (this._state.serverRunning) {
      return;
    }
    this._sendControlMessage({ type: 'set_option', option, enabled });
  };

  private _sendControlMessage(payload: any): void {
    // Don't send if widget is disposed
    if (this.isDisposed) return;

    const kernel = this._panel.sessionContext.session?.kernel;
    if (!kernel || kernel.status === 'dead' || kernel.status === 'restarting') {
      return;
    }

    // Don't send if kernel is in restart transition
    if (this._kernelRestarting) {
      console.log('MCP Toolbar: Skipping send during kernel restart');
      return;
    }

    // Check if comm is valid
    if (!this._controlComm || this._controlComm.isDisposed) {
      // Reconnect and retry
      void this._openControlComm().then(() => {
        if (this._controlComm && !this._controlComm.isDisposed && !this.isDisposed) {
          try {
            this._controlComm.send(payload);
          } catch (error) {
            console.warn('MCP Toolbar: failed to send after reconnect', error);
            this._closeControlComm();  // Close properly on failure
          }
        }
      });
      return;
    }

    try {
      this._controlComm.send(payload);
    } catch (error) {
      console.warn('MCP Toolbar: failed to send control message', error);
      this._closeControlComm();  // Close properly on failure so next action reopens
    }
  }

  private _closeControlComm(): void {
    // Clear reference FIRST to prevent race conditions
    const comm = this._controlComm;
    this._controlComm = null;

    if (comm && !comm.isDisposed) {
      try {
        comm.close();
      } catch (error) {
        // Ignore - comm may already be closed
      }
    }
  }

  private _onKernelChanged = (): void => {
    console.log('MCP Toolbar: Kernel changed');
    this._kernelRestarting = false;
    this._closeControlComm();
    this._state = { ...DEFAULT_STATE };
    this.update();

    // Reconnect status listener to new kernel
    const kernel = this._panel.sessionContext.session?.kernel;
    if (kernel) {
      kernel.statusChanged.connect(this._onKernelStatusChanged, this);
      void this._openControlComm();
    }
  };

  private _onKernelStatusChanged = (
    sender: Kernel.IKernelConnection,
    status: Kernel.Status
  ): void => {
    console.log(`MCP Toolbar: Kernel status changed to ${status}`);

    if (status === 'restarting' || status === 'dead' || status === 'terminating') {
      // Kernel is going away - immediately close comm and prevent sends
      this._kernelRestarting = true;
      this._closeControlComm();
      this._state = { ...DEFAULT_STATE };
      this.update();
    } else if (status === 'idle' && this._kernelRestarting) {
      // Kernel came back - wait a bit then reconnect
      console.log('MCP Toolbar: Kernel back from restart, reconnecting');
      this._kernelRestarting = false;
      setTimeout(() => {
        if (!this.isDisposed && !this._kernelRestarting) {
          void this._openControlComm();
        }
      }, 100);
    }
  };
}
