/**
 * QDevBot Desktop uses a dedicated kernelspec for offline/historical analysis.
 * That kernel must never receive the InstrMCP IPython extension, comm targets,
 * or active-cell snapshots because it does not own instrument control.
 *
 * All other kernels retain InstrMCP's existing behaviour. This keeps the
 * integration opt-in to QDevBot's explicitly named analysis kernelspec and
 * avoids changing ordinary JupyterLab notebooks.
 */
export const QDEVBOT_ANALYSIS_KERNEL_NAME = 'qdevbot-analysis';

export interface KernelIdentity {
  readonly name?: string | null;
}

export function isQdevbotAnalysisKernel(
  kernel?: KernelIdentity | null
): boolean {
  return kernel?.name === QDEVBOT_ANALYSIS_KERNEL_NAME;
}
