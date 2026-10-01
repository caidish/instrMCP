import { DocumentRegistry } from '@jupyterlab/docregistry';
import { NotebookPanel, INotebookModel } from '@jupyterlab/notebook';
import { MCPToolbarWidget } from './MCPToolbarWidget';
import { ToolbarSharedState } from './types';
import { Kernel } from '@jupyterlab/services';

export class MCPToolbarExtension
  implements DocumentRegistry.IWidgetExtension<NotebookPanel, INotebookModel>
{
  private _shared: ToolbarSharedState;
  private _kernelAllowed: (
    kernel?: Kernel.IKernelConnection | null
  ) => boolean;

  constructor(
    shared: ToolbarSharedState,
    kernelAllowed: (kernel?: Kernel.IKernelConnection | null) => boolean = () => true
  ) {
    this._shared = shared;
    this._kernelAllowed = kernelAllowed;
  }

  createNew(panel: NotebookPanel): MCPToolbarWidget {
    const widget = new MCPToolbarWidget(
      panel,
      this._shared,
      this._kernelAllowed
    );
    panel.toolbar.insertItem(0, 'mcpToolbar', widget);
    panel.disposed.connect(() => {
      widget.dispose();
    });
    return widget;
  }
}
