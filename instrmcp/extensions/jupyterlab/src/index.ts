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

    // Handle add cell requests from kernel
    const handleAddCell = async (kernel: Kernel.IKernelConnection, comm: any, data: any) => {
      const requestId = data.request_id;
      const cellType = data.cell_type || 'code';
      const position = data.position || 'below';
      const content = data.content || '';

      try {
        const panel = notebooks.currentWidget;

        if (!panel) {
          // Send error response
          comm.send({
            type: 'add_cell_response',
            request_id: requestId,
            success: false,
            message: 'No active notebook available'
          });
          return;
        }

        // Validate cell type
        const validTypes = ['code', 'markdown', 'raw'];
        if (!validTypes.includes(cellType)) {
          comm.send({
            type: 'add_cell_response',
            request_id: requestId,
            success: false,
            message: `Invalid cell_type '${cellType}'. Must be one of: ${validTypes.join(', ')}`
          });
          return;
        }

        // Validate position
        const validPositions = ['above', 'below'];
        if (!validPositions.includes(position)) {
          comm.send({
            type: 'add_cell_response',
            request_id: requestId,
            success: false,
            message: `Invalid position '${position}'. Must be one of: ${validPositions.join(', ')}`
          });
          return;
        }

        // Create new cell
        if (position === 'above') {
          await NotebookActions.insertAbove(panel.content);
        } else {
          await NotebookActions.insertBelow(panel.content);
        }

        // Get the newly created cell
        const newCell = notebooks.activeCell;
        if (newCell) {
          // Set cell type if needed
          if (newCell.model.type !== cellType) {
            await NotebookActions.changeCellType(panel.content, cellType as any);
          }

          // Set content if provided
          if (content) {
            newCell.model.sharedModel.setSource(content);
          }
        }

        // Send success response
        comm.send({
          type: 'add_cell_response',
          request_id: requestId,
          success: true,
          cell_type: cellType,
          position: position,
          content_length: content.length,
          cell_id: newCell?.model.id,
          message: 'Cell added successfully'
        });

        console.log(`MCP Active Cell Bridge: Added ${cellType} cell ${position} with ${content.length} chars`);

      } catch (error) {
        console.error('MCP Active Cell Bridge: Failed to add cell:', error);

        // Send error response
        comm.send({
          type: 'add_cell_response',
          request_id: requestId,
          success: false,
          message: `Failed to add cell: ${error}`
        });
      }
    };

    // Handle delete cell requests from kernel
    const handleDeleteCell = async (kernel: Kernel.IKernelConnection, comm: any, data: any) => {
      const requestId = data.request_id;

      try {
        const panel = notebooks.currentWidget;
        const cell = notebooks.activeCell;

        if (!panel || !cell) {
          // Send error response
          comm.send({
            type: 'delete_cell_response',
            request_id: requestId,
            success: false,
            message: 'No active cell available for deletion'
          });
          return;
        }

        const cellId = cell.model.id;
        const totalCells = panel.content.model?.cells.length || 0;

        // Check if this is the only cell
        if (totalCells <= 1) {
          // Clear the content instead of deleting
          cell.model.sharedModel.setSource('');

          // Send success response
          comm.send({
            type: 'delete_cell_response',
            request_id: requestId,
            success: true,
            cell_id: cellId,
            action: 'cleared',
            message: 'Last cell content cleared (cell preserved)'
          });

          console.log('MCP Active Cell Bridge: Cleared last cell content');
        } else {
          // Delete the cell
          await NotebookActions.deleteCells(panel.content);

          // Send success response
          comm.send({
            type: 'delete_cell_response',
            request_id: requestId,
            success: true,
            cell_id: cellId,
            action: 'deleted',
            message: 'Cell deleted successfully'
          });

          console.log('MCP Active Cell Bridge: Deleted cell');
        }

      } catch (error) {
        console.error('MCP Active Cell Bridge: Failed to delete cell:', error);

        // Send error response
        comm.send({
          type: 'delete_cell_response',
          request_id: requestId,
          success: false,
          message: `Failed to delete cell: ${error}`
        });
      }
    };

    // Handle apply patch requests from kernel
    const handleApplyPatch = async (kernel: Kernel.IKernelConnection, comm: any, data: any) => {
      const requestId = data.request_id;
      const oldText = data.old_text || '';
      const newText = data.new_text || '';

      try {
        const panel = notebooks.currentWidget;
        const cell = notebooks.activeCell;

        if (!panel || !cell) {
          // Send error response
          comm.send({
            type: 'apply_patch_response',
            request_id: requestId,
            success: false,
            message: 'No active cell available for patching'
          });
          return;
        }

        if (!oldText) {
          comm.send({
            type: 'apply_patch_response',
            request_id: requestId,
            success: false,
            message: 'old_text parameter cannot be empty'
          });
          return;
        }

        // Get current cell content
        const currentContent = cell.model.sharedModel.getSource();

        // Apply patch (replace first occurrence)
        const patchedContent = currentContent.replace(oldText, newText);

        // Check if replacement was made
        const wasReplaced = patchedContent !== currentContent;

        if (wasReplaced) {
          // Update cell content
          cell.model.sharedModel.setSource(patchedContent);

          // Send success response
          comm.send({
            type: 'apply_patch_response',
            request_id: requestId,
            success: true,
            cell_id: cell.model.id,
            replaced: true,
            old_text_length: oldText.length,
            new_text_length: newText.length,
            content_length_before: currentContent.length,
            content_length_after: patchedContent.length,
            message: 'Patch applied successfully'
          });

          console.log(`MCP Active Cell Bridge: Applied patch (${oldText.length} -> ${newText.length} chars)`);
        } else {
          // No replacement made
          comm.send({
            type: 'apply_patch_response',
            request_id: requestId,
            success: true,
            cell_id: cell.model.id,
            replaced: false,
            old_text_length: oldText.length,
            new_text_length: newText.length,
            message: 'Patch target not found - no changes made'
          });

          console.log('MCP Active Cell Bridge: Patch target not found');
        }

      } catch (error) {
        console.error('MCP Active Cell Bridge: Failed to apply patch:', error);

        // Send error response
        comm.send({
          type: 'apply_patch_response',
          request_id: requestId,
          success: false,
          message: `Failed to apply patch: ${error}`
        });
      }
    };

    // Handle delete cells by number requests from kernel
    const handleDeleteCellsByNumber = async (kernel: Kernel.IKernelConnection, comm: any, data: any) => {
      const requestId = data.request_id;
      const cellNumbers = data.cell_numbers || [];

      try {
        const panel = notebooks.currentWidget;

        if (!panel) {
          comm.send({
            type: 'delete_cells_by_number_response',
            request_id: requestId,
            success: false,
            message: 'No active notebook available'
          });
          return;
        }

        if (!Array.isArray(cellNumbers) || cellNumbers.length === 0) {
          comm.send({
            type: 'delete_cells_by_number_response',
            request_id: requestId,
            success: false,
            message: 'cell_numbers must be a non-empty array'
          });
          return;
        }

        const notebook = panel.content;
        const cells = notebook.model?.cells;

        if (!cells) {
          comm.send({
            type: 'delete_cells_by_number_response',
            request_id: requestId,
            success: false,
            message: 'Cannot access notebook cells'
          });
          return;
        }

        // Map execution counts to cell indices
        const executionCountToIndex = new Map<number, number>();
        for (let i = 0; i < cells.length; i++) {
          const cellModel = cells.get(i);
          const execCount = (cellModel as any).executionCount;
          if (execCount != null) {
            executionCountToIndex.set(execCount, i);
          }
        }

        const results: any[] = [];
        const indicesToDelete: number[] = [];

        // Validate all cell numbers and collect indices
        for (const cellNum of cellNumbers) {
          if (!executionCountToIndex.has(cellNum)) {
            results.push({
              cell_number: cellNum,
              success: false,
              message: `Cell with execution count ${cellNum} not found`
            });
          } else {
            const index = executionCountToIndex.get(cellNum)!;
            indicesToDelete.push(index);
            results.push({
              cell_number: cellNum,
              index: index,
              success: true
            });
          }
        }

        // Sort indices in descending order to delete from bottom to top
        // This prevents index shifting issues
        indicesToDelete.sort((a, b) => b - a);

        // Delete cells
        let deletedCount = 0;
        let clearedCount = 0;

        for (const index of indicesToDelete) {
          try {
            // Check if this is the last cell
            if (cells.length === 1) {
              // Clear content instead of deleting
              const cellModel = cells.get(index);
              if (cellModel) {
                cellModel.sharedModel.setSource('');
                const resultIndex = results.findIndex(r => r.index === index);
                if (resultIndex !== -1) {
                  results[resultIndex].message = 'Last cell - content cleared instead of deleted';
                  results[resultIndex].cleared = true;
                }
                clearedCount++;
              }
            } else {
              // Use the notebook model's method to remove cells
              notebook.model?.sharedModel.deleteCell(index);
              deletedCount++;
            }
          } catch (error) {
            const resultIndex = results.findIndex(r => r.index === index);
            if (resultIndex !== -1) {
              results[resultIndex].success = false;
              results[resultIndex].message = `Failed to delete: ${error}`;
            }
          }
        }

        // Send success response
        comm.send({
          type: 'delete_cells_by_number_response',
          request_id: requestId,
          success: true,
          deleted_count: deletedCount,
          total_requested: cellNumbers.length,
          results: results,
          message: `Deleted ${deletedCount} cell(s)`
        });

        console.log(`MCP Active Cell Bridge: Deleted ${deletedCount} cells by number`);

      } catch (error) {
        console.error('MCP Active Cell Bridge: Failed to delete cells by number:', error);

        comm.send({
          type: 'delete_cells_by_number_response',
          request_id: requestId,
          success: false,
          message: `Failed to delete cells: ${error}`
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
              const msgType = data.type;

              if (msgType === 'request_current') {
                sendSnapshot(kernel);
              } else if (msgType === 'update_cell') {
                handleCellUpdate(kernel, comm, data);
              } else if (msgType === 'execute_cell') {
                handleCellExecution(kernel, comm, data);
              } else if (msgType === 'add_cell') {
                handleAddCell(kernel, comm, data);
              } else if (msgType === 'delete_cell') {
                handleDeleteCell(kernel, comm, data);
              } else if (msgType === 'delete_cells_by_number') {
                handleDeleteCellsByNumber(kernel, comm, data);
              } else if (msgType === 'apply_patch') {
                handleApplyPatch(kernel, comm, data);
              } else {
                console.warn(`MCP Active Cell Bridge: Unknown message type: ${msgType}`);
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