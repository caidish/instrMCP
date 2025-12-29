import { DocumentRegistry } from '@jupyterlab/docregistry';
import { NotebookPanel, INotebookModel } from '@jupyterlab/notebook';
import { MCPToolbarWidget } from './MCPToolbarWidget';
import { ToolbarSharedState } from './types';

export class MCPToolbarExtension
  implements DocumentRegistry.IWidgetExtension<NotebookPanel, INotebookModel>
{
  private _shared: ToolbarSharedState;

  constructor(shared: ToolbarSharedState) {
    this._shared = shared;
  }

  createNew(panel: NotebookPanel): MCPToolbarWidget {
    const widget = new MCPToolbarWidget(panel, this._shared);
    panel.toolbar.insertItem(0, 'mcpToolbar', widget);
    panel.disposed.connect(() => {
      widget.dispose();
    });
    return widget;
  }
}
