import { ISignal } from '@lumino/signaling';
import { Kernel } from '@jupyterlab/services';

export type MCPMode = 'safe' | 'unsafe' | 'dangerous';

export interface MCPOptionInfo {
  name: string;
  description?: string;
  requires_mode?: MCPMode;  // null/undefined = no mode requirement
}

export interface MCPState {
  serverRunning: boolean;
  mode: MCPMode;
  enabledOptions: string[];
  availableOptions: MCPOptionInfo[];
  host: string | null;
  port: number | null;
  dangerous: boolean;
}

export interface MCPStatusUpdate {
  kernel: Kernel.IKernelConnection;
  status: string;
  details: any;
}

export interface ToolbarSharedState {
  getServerReady: (kernel?: Kernel.IKernelConnection | null) => boolean;
  getComm?: (kernel?: Kernel.IKernelConnection | null) => any;
  statusUpdateSignal: ISignal<object, MCPStatusUpdate>;
}
