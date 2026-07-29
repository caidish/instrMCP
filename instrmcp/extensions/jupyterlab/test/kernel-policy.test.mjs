import test from 'node:test';
import assert from 'node:assert/strict';
import {
  QDEVBOT_ANALYSIS_KERNEL_NAME,
  isQdevbotAnalysisKernel
} from '../lib/kernel-policy.js';

test('isolates only the exact QDevBot analysis kernelspec', () => {
  assert.equal(QDEVBOT_ANALYSIS_KERNEL_NAME, 'qdevbot-analysis');
  assert.equal(isQdevbotAnalysisKernel({ name: 'qdevbot-analysis' }), true);
  assert.equal(isQdevbotAnalysisKernel({ name: 'qdevbot-control-snapshot' }), false);
  assert.equal(isQdevbotAnalysisKernel({ name: 'python3' }), false);
  assert.equal(isQdevbotAnalysisKernel({ name: 'qdevbot-analysis-copy' }), false);
  assert.equal(isQdevbotAnalysisKernel(null), false);
});
