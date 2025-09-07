import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';

import { INotebookTracker } from '@jupyterlab/notebook';

import { Cell } from '@jupyterlab/cells';

import { Kernel } from '@jupyterlab/services';

import { NotebookPanel } from '@jupyterlab/notebook';
import { ICellModel } from '@jupyterlab/cells';
import { NotebookActions } from '@jupyterlab/notebook';

/**
 * MCP Active Cell Bridge Extension
 * 
 * Tracks the currently editing cell in JupyterLab and sends updates
 * to the kernel via comm protocol for consumption by the MCP server.
 */
const plugin: JupyterFrontEndPlugin<void> = {
  id: 'mcp-active-cell-bridge:plugin',
  description: 'Bridge active cell content to MCP server via kernel comm',
  autoStart: true,
  requires: [INotebookTracker],
  activate: (app: JupyterFrontEnd, notebooks: INotebookTracker) => {
    console.log('MCP Active Cell Bridge extension activated');

    // Keep track of comm connections per kernel
    const comms = new WeakMap<Kernel.IKernelConnection, any>();
    
    // Track which comms have been successfully opened
    const openedComms = new WeakMap<Kernel.IKernelConnection, boolean>();
    
    // Track pending comm initialization to prevent race conditions
    const commInitializing = new WeakMap<Kernel.IKernelConnection, Promise<any>>();
    
    // Debounce utility function
    const debounce = (fn: () => void, delay: number) => {
      let timeoutId: number | null = null;
      return () => {
        if (timeoutId) {
          window.clearTimeout(timeoutId);
        }
        timeoutId = window.setTimeout(fn, delay);
      };
    };

    // Check if comm is ready to send messages
    const isCommReady = (kernel: Kernel.IKernelConnection, comm: any): boolean => {
      return comm && !comm.isDisposed && openedComms.get(kernel) === true;
    };

    // Handle cell update requests from kernel
    const handleCellUpdate = async (kernel: Kernel.IKernelConnection, comm: any, data: any) => {
      const requestId = data.request_id;
      const newContent = data.content;
      
      try {
        const panel = notebooks.currentWidget;
        const cell = notebooks.activeCell;
        
        if (!panel || !cell) {
          // Send error response
          comm.send({
            type: 'update_response',
            request_id: requestId,
            success: false,
            message: 'No active cell available for update'
          });
          return;
        }
        
        // Update cell content
        cell.model.sharedModel.setSource(newContent);
        
        // Send success response
        comm.send({
          type: 'update_response',
          request_id: requestId,
          success: true,
          cell_id: cell.model.id,
          message: 'Cell updated successfully'
        });
        
        console.log(`MCP Active Cell Bridge: Updated cell content (${newContent.length} chars)`);
        
      } catch (error) {
        console.error('MCP Active Cell Bridge: Failed to update cell:', error);
        
        // Send error response
        comm.send({
          type: 'update_response',
          request_id: requestId,
          success: false,
          message: `Failed to update cell: ${error}`
        });
      }
    };

    // Handle cell execution requests from kernel
    const handleCellExecution = async (kernel: Kernel.IKernelConnection, comm: any, data: any) => {
      const requestId = data.request_id;
      
      try {
        const panel = notebooks.currentWidget;
        const cell = notebooks.activeCell;
        
        if (!panel || !cell) {
          // Send error response
          comm.send({
            type: 'execute_response',
            request_id: requestId,
            success: false,
            message: 'No active cell available for execution'
          });
          return;
        }
        
        // Execute the active cell using NotebookActions
        await NotebookActions.run(panel.content, panel.sessionContext);
        
        // Send success response
        comm.send({
          type: 'execute_response',
          request_id: requestId,
          success: true,
          cell_id: cell.model.id,
          message: 'Cell executed successfully'
        });
        
        console.log('MCP Active Cell Bridge: Executed active cell');
        
      } catch (error) {
        console.error('MCP Active Cell Bridge: Failed to execute cell:', error);
        
        // Send error response
        comm.send({
          type: 'execute_response',
          request_id: requestId,
          success: false,
          message: `Failed to execute cell: ${error}`
        });
      }
    };

    // Ensure comm connection exists for a kernel
    const ensureComm = async (kernel?: Kernel.IKernelConnection | null) => {
      if (!kernel || !kernel.status || kernel.status === 'dead') {
        console.warn('MCP Active Cell Bridge: Kernel not available or dead');
        return null;
      }
      
      if (kernel.status !== 'idle' && kernel.status !== 'busy') {
        console.warn(`MCP Active Cell Bridge: Kernel not ready (status: ${kernel.status})`);
        return null;
      }
      
      let comm = comms.get(kernel);
      if (!comm || !isCommReady(kernel, comm)) {
        // Check if already initializing
        let initPromise = commInitializing.get(kernel);
        if (initPromise) {
          try {
            await initPromise;
            return comms.get(kernel) || null;
          } catch {
            return null;
          }
        }
        
        // Start initialization
        initPromise = (async () => {
          try {
            comm = kernel.createComm('mcp:active_cell');
            
            // Handle incoming messages from kernel
            comm.onMsg = (msg: any) => {
              const data = msg?.content?.data || {};
              if (data.type === 'request_current') {
                // Kernel is requesting fresh snapshot
                sendSnapshot(kernel);
              } else if (data.type === 'update_cell') {
                // Kernel is requesting to update the active cell content
                handleCellUpdate(kernel, comm, data);
              } else if (data.type === 'execute_cell') {
                // Kernel is requesting to execute the active cell
                handleCellExecution(kernel, comm, data);
              }
            };
            
            // Handle comm close
            comm.onClose = (msg: any) => {
              console.log('MCP Active Cell Bridge: Comm closed');
              openedComms.delete(kernel);
              comms.delete(kernel);
              commInitializing.delete(kernel);
            };
            
            // Open comm and wait for it to be ready
            await comm.open({}).done;
            
            // Mark comm as successfully opened
            openedComms.set(kernel, true);
            comms.set(kernel, comm);
            console.log('MCP Active Cell Bridge: Comm opened and ready');
            return comm;
          } catch (error) {
            console.error('MCP Active Cell Bridge: Failed to create comm:', error);
            
            // Check if error is due to missing comm target
            const errorMsg = error?.toString() || '';
            if (errorMsg.includes('No such comm target') || errorMsg.includes('comm target')) {
              console.error('MCP Active Cell Bridge: Kernel comm target not registered!');
              console.error('Run this command in a notebook cell: %load_ext servers.jupyter_qcodes.jupyter_mcp_extension');
            }
            
            openedComms.delete(kernel);
            comms.delete(kernel);
            throw error;
          } finally {
            commInitializing.delete(kernel);
          }
        })();
        
        commInitializing.set(kernel, initPromise);
        return await initPromise;
      }
      return comm;
    };

    // Send cell snapshot to kernel
    const sendSnapshot = async (kernel?: Kernel.IKernelConnection | null) => {
      const panel = notebooks.currentWidget;
      const cell = notebooks.activeCell;
      
      if (!panel || !cell) {
        return;
      }
      
      const targetKernel = kernel ?? panel.sessionContext.session?.kernel;
      if (!targetKernel) {
        return;
      }

      // Ensure comm is ready
      const comm = await ensureComm(targetKernel);
      if (!comm || !isCommReady(targetKernel, comm)) {
        console.warn('MCP Active Cell Bridge: Comm not ready for sending');
        return;
      }

      try {
        // Get cell editor and content
        const editor = (cell as any).editor;
        const text = cell.model.sharedModel.getSource();
        
        // Get cursor position if available
        let cursor = null;
        try {
          cursor = editor?.getCursorPosition?.() ?? null;
        } catch (e) {
          // Cursor position might not be available
        }
        
        // Get selection if available
        let selection = null;
        try {
          const selectionObj = editor?.getSelection?.() ?? null;
          if (selectionObj && selectionObj.start !== selectionObj.end) {
            selection = {
              start: selectionObj.start,
              end: selectionObj.end
            };
          }
        } catch (e) {
          // Selection might not be available
        }

        // Truncate text if too large (safety limit)
        const maxLength = 50000;
        let truncatedText = text;
        let truncated = false;
        if (text.length > maxLength) {
          truncatedText = text.slice(0, maxLength);
          truncated = true;
        }

        const payload = {
          type: 'snapshot',
          path: panel.context.path,
          index: panel.content.activeCellIndex,
          id: cell.model.id,
          cell_type: cell.model.type, // 'code' | 'markdown' | 'raw'
          text: truncatedText,
          cursor,
          selection,
          truncated,
          original_length: text.length,
          ts_ms: Date.now(),
          client_id: (app as any).info?.workspace ?? 'unknown'
        };

        comm.send(payload);
        console.log(`MCP Active Cell Bridge: Sent snapshot (${truncatedText.length} chars)`);
        
      } catch (error) {
        console.error('MCP Active Cell Bridge: Failed to send snapshot:', error);
        // Try to recreate comm on failure
        comms.delete(targetKernel);
        openedComms.delete(targetKernel);
        commInitializing.delete(targetKernel);
      }
    };

    // Track active cell changes
    notebooks.activeCellChanged.connect(async (sender: any, args: any) => {
      const kernel = notebooks.currentWidget?.sessionContext.session?.kernel ?? null;
      await ensureComm(kernel);
      
      // Send snapshot immediately when cell changes
      await sendSnapshot(kernel);
      
      // Set up debounced content change tracking for the new cell
      const cell = notebooks.activeCell;
      if (cell) {
        // Create debounced function with 2000ms delay as requested
        const debouncedSendSnapshot = debounce(() => sendSnapshot(kernel), 2000);
        
        // Listen to content changes
        cell.model.sharedModel.changed.connect(() => {
          debouncedSendSnapshot();
        });
        
        console.log('MCP Active Cell Bridge: Tracking new active cell');
      }
    });

    // Track notebook changes
    notebooks.currentChanged.connect(async (sender: any, args: any) => {
      const kernel = notebooks.currentWidget?.sessionContext.session?.kernel ?? null;
      await ensureComm(kernel);
      await sendSnapshot(kernel);
      console.log('MCP Active Cell Bridge: Notebook changed, sent snapshot');
    });

    // Handle kernel ready/restart
    notebooks.widgetAdded.connect((sender: any, panel: any) => {
      panel.sessionContext.ready.then(() => {
        const kernel = panel.sessionContext.session?.kernel ?? null;
        ensureComm(kernel);
        console.log('MCP Active Cell Bridge: Kernel ready, setting up comm');
      });
    });

    console.log('MCP Active Cell Bridge: Event listeners registered');
  }
};

export default plugin;