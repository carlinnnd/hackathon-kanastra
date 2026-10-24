const fs = require('fs');
const path = require('path');
const ts = require('../node_modules/typescript');

const rootDir = path.resolve(__dirname, '..');
const currPath = path.join(rootDir, 'src/services/currency.ts');
const rejPath = path.join(rootDir, 'src/services/rejections.ts');
const pubDemoPath = path.join(rootDir, 'src/services/publicDemoResults.ts');
const bulkUploadPath = path.join(rootDir, 'src/services/bulkUpload.ts');
const testPath = path.join(rootDir, 'src/services/tests_frontend.test.ts');

const currCode = fs.readFileSync(currPath, 'utf8');
const rejCode = fs.readFileSync(rejPath, 'utf8');
const pubDemoCode = fs.readFileSync(pubDemoPath, 'utf8');
const bulkUploadCode = fs.readFileSync(bulkUploadPath, 'utf8');
const testCode = fs.readFileSync(testPath, 'utf8');

const transpiledCurr = ts.transpileModule(currCode, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
const transpiledRej = ts.transpileModule(rejCode, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
const transpiledPubDemo = ts.transpileModule(pubDemoCode, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
const transpiledBulkUpload = ts.transpileModule(bulkUploadCode, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
const transpiledTest = ts.transpileModule(testCode, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;

const mCurr = { exports: {} };
new Function('exports', 'module', 'require', transpiledCurr)(mCurr.exports, mCurr, require);

const mRej = { exports: {} };
new Function('exports', 'module', 'require', transpiledRej)(mRej.exports, mRej, require);

const mPubDemo = { exports: {} };
new Function('exports', 'module', 'require', transpiledPubDemo)(mPubDemo.exports, mPubDemo, require);

const mBulkUpload = { exports: {} };
new Function('exports', 'module', 'require', transpiledBulkUpload)(mBulkUpload.exports, mBulkUpload, require);

const reqMock = (modulePath) => {
  if (modulePath.includes('currency')) return mCurr.exports;
  if (modulePath.includes('rejections')) return mRej.exports;
  if (modulePath.includes('publicDemoResults')) return mPubDemo.exports;
  if (modulePath.includes('bulkUpload')) return mBulkUpload.exports;
  return require(modulePath);
};

const mTest = { exports: {} };

async function run() {
  try {
    new Function('exports', 'module', 'require', 'console', transpiledTest)(mTest.exports, mTest, reqMock, console);

    if (typeof mTest.exports.runBulkTransportTests === 'function') {
      const deadline = new Promise((_, reject) => {
        setTimeout(() => reject(new Error('Deadline de 5s excedido nos testes assíncronos de transporte.')), 5000);
      });

      await Promise.race([mTest.exports.runBulkTransportTests(), deadline]);
      console.log('--- Suíte assíncrona de resiliência BulkTransport finalizada com sucesso! ---');
    }

    process.exit(0);
  } catch (err) {
    console.error('Erro na execução dos testes frontend:', err);
    process.exit(1);
  }
}

run();
