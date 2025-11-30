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
    this._closeControlComm();

    const kernel = this._panel.sessionContext.session?.kernel;
    if (!kernel || kernel.status === 'dead') {
      return;
    }

    try {
      const comm = kernel.createComm('mcp:toolbar_control');
      comm.onMsg = (msg: any) => {
        this._handleControlMessage(msg);
      };
      this._controlComm = comm;
      comm.open();
      this._requestStatus();
    } catch (error) {
      console.warn('MCP Toolbar: failed to open control comm', error);
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
    this._kernelRestarting = false;
    this._closeControlComm();
    this._state = { ...DEFAULT_STATE };
    this.update();
    void this._openControlComm();
  };

  private _handleModeChange = (mode: MCPMode): void => {
    if (mode === this._state.mode) {
      return;
    }

    this._sendControlMessage({ type: 'set_mode', mode });

    if (this._state.serverRunning) {
      const restart = window.confirm('Restart MCP server now to apply mode change?');
      if (restart) {
        this._handleRestart();
      }
    }
  };

  private _handleOptionToggle = (option: string, enabled: boolean): void => {
    this._sendControlMessage({ type: 'set_option', option, enabled });

    if (this._state.serverRunning) {
      const restart = window.confirm('Restart MCP server to apply option changes?');
      if (restart) {
        this._handleRestart();
      }
    }
  };

  private _sendControlMessage(payload: any): void {
    const kernel = this._panel.sessionContext.session?.kernel;
    if (!kernel || kernel.status === 'dead' || kernel.status === 'restarting') {
      return;
    }

    // Don't send if kernel is in restart transition
    if (this._kernelRestarting) {
      console.log('MCP Toolbar: Skipping send during kernel restart');
      return;
    }

    if (!this._controlComm || this._controlComm.isDisposed) {
      void this._openControlComm().then(() => {
        if (this._controlComm && !this._controlComm.isDisposed) {
          try {
            this._controlComm.send(payload);
          } catch (error) {
            console.warn('MCP Toolbar: failed to send control message after reconnect', error);
            // Clear comm on failure so next action reopens it
            this._controlComm = null;
          }
        }
      });
      return;
    }

    try {
      this._controlComm.send(payload);
    } catch (error) {
      console.warn('MCP Toolbar: failed to send control message', error);
      // Clear comm on failure so next action reopens it
      this._controlComm = null;
    }
  }

  private _closeControlComm(): void {
    if (this._controlComm && !this._controlComm.isDisposed) {
      try {
        this._controlComm.close();
      } catch (error) {
        // ignore
      }
    }
    this._controlComm = null;
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
      // Kernel came back - reconnect
      console.log('MCP Toolbar: Kernel back from restart, reconnecting');
      this._kernelRestarting = false;
      void this._openControlComm();
    }
  };
}
