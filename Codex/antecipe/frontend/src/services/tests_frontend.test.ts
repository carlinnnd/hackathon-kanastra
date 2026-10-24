/**
 * Testes Unitários dos Serviços do Frontend Antecipe
 * - Formatação exata de Moeda BRL (BigInt, sem perda de centavos em limites altos)
 * - Mapeamento e explicabilidade de recusas (preservação de mensagem original do backend)
 * - Tratamento de limites técnicos e capacidade numérica (VALOR_EXCEDE_CAPACIDADE / TOTAL_EXCEDE_CAPACIDADE)
 * - Pure helper de visualização em memória para modo público efêmero (preservação de totais globais e integridade de restauração)
 * - Testes reais de resiliência e ciclo de vida do BulkUploadSession com FakeWebSocket e mock de File
 */

import { formatarMoedaBRL } from './currency';
import { obterExplicacaoRecusa } from './rejections';
import {
  aplicarFiltroPaginacaoLocal,
  verificarSnapshotCompleto,
} from './publicDemoResults';
import { BulkUploadSession } from './bulkUpload';
import { SimulationEnvelope } from '../types';

function assertEqual(actual: unknown, expected: unknown, desc?: string): void {
  if (actual !== expected) {
    throw new Error(`Falha no teste ${desc || ''}: esperado ${JSON.stringify(expected)}, obtido ${JSON.stringify(actual)}`);
  }
}

function assertTrue(condition: boolean, desc?: string): void {
  if (!condition) {
    throw new Error(`Falha no teste de condição verdadeira: ${desc || ''}`);
  }
}

console.log('--- Iniciando testes unitários do Frontend Antecipe ---');

// 1. Testes de Moeda BRL (valores comuns e limites altos Numeric(18,2))
console.log('Testando formatarMoedaBRL...');

// 1.1 Valores comuns
assertEqual(formatarMoedaBRL('5000.00'), 'R$ 5.000,00', '5000.00');
assertEqual(formatarMoedaBRL('4700.00'), 'R$ 4.700,00', '4700.00');
assertEqual(formatarMoedaBRL('50.00'), 'R$ 50,00', '50.00');
assertEqual(formatarMoedaBRL('0.00'), 'R$ 0,00', '0.00');
assertEqual(formatarMoedaBRL('0'), 'R$ 0,00', '0');
assertEqual(formatarMoedaBRL(null), 'R$ 0,00', 'null');
assertEqual(formatarMoedaBRL(undefined), 'R$ 0,00', 'undefined');

// 1.2 Formato brasileiro com vírgula de entrada
assertEqual(formatarMoedaBRL('5000,00'), 'R$ 5.000,00', '5000,00');
assertEqual(formatarMoedaBRL('1.234.567,89'), 'R$ 1.234.567,89', '1.234.567,89');

// 1.3 Limite extremo Numeric(18,2) - 9999999999999999.99
// Em Number normal, 9999999999999999.99 sofre perda de precisão float
const valorExtremo = '9999999999999999.99';
const formatadoExtremo = formatarMoedaBRL(valorExtremo);
assertEqual(formatadoExtremo, 'R$ 9.999.999.999.999.999,99', '9999999999999999.99');
console.log('✓ Formatação BRL exata para 5000, 4700 e 9999999999999999.99 passou!');

// 2. Testes de Explicabilidade de Recusas (obterExplicacaoRecusa)
console.log('Testando obterExplicacaoRecusa...');

// 2.1 Preserva mensagemOriginal rica do backend para códigos conhecidos
const msgBackendValor = 'Valor nominal de R$ 50.00 é inferior ao mínimo permitido de R$ 100.00.';
const expValor = obterExplicacaoRecusa('VALOR_MINIMO', msgBackendValor);
assertEqual(expValor.titulo, 'Valor Nominal Inferior ao Mínimo');
assertEqual(expValor.descricao, msgBackendValor);
assertTrue(expValor.acaoRecomendada.includes('Confira o valor de face com o documento fiscal original'));
assertEqual(expValor.acaoRecomendada.includes('agrupe'), false, 'Não deve sugerir agrupar títulos');

// 2.2 Preserva dias e limites em PRAZO_MAXIMO
const msgBackendPrazo = 'Prazo de 231 dias excede o limite máximo de 180 dias.';
const expPrazo = obterExplicacaoRecusa('PRAZO_MAXIMO', msgBackendPrazo);
assertEqual(expPrazo.titulo, 'Prazo de Vencimento Superior ao Limite');
assertEqual(expPrazo.descricao, msgBackendPrazo);

// 2.3 Situação cadastral não verificada
const msgBackendCadastral = 'Situação cadastral do sacado não foi verificada na base de dados oficial.';
const expCadastral = obterExplicacaoRecusa('SITUACAO_CADASTRAL_SACADO', msgBackendCadastral);
assertEqual(expCadastral.titulo, 'Situação Cadastral Incompatível do Sacado');
assertEqual(expCadastral.descricao, msgBackendCadastral);
assertEqual(expCadastral.descricao.includes('Receita Federal'), false);

// 2.4 NAO_VENCIDA contempla vencimento igual à data-base
const expNaoVencida = obterExplicacaoRecusa('NAO_VENCIDA', undefined);
assertTrue(expNaoVencida.acaoRecomendada.includes('igual ou posterior'));

// 2.5 Limite de capacidade técnica individual (VALOR_EXCEDE_CAPACIDADE)
const expCapacidadeIndiv = obterExplicacaoRecusa('VALOR_EXCEDE_CAPACIDADE', undefined);
assertEqual(expCapacidadeIndiv.titulo, 'Valor Excede Capacidade Técnica do Sistema');
assertTrue(expCapacidadeIndiv.descricao.includes('9.999.999.999.999,99'));
assertTrue(expCapacidadeIndiv.acaoRecomendada.includes('capacidade técnica'));

// 2.6 Limite de capacidade técnica da simulação (TOTAL_EXCEDE_CAPACIDADE)
const expCapacidadeTotal = obterExplicacaoRecusa('TOTAL_EXCEDE_CAPACIDADE', undefined);
assertEqual(expCapacidadeTotal.titulo, 'Total excede a capacidade técnica do sistema');
assertEqual(expCapacidadeTotal.descricao, 'O total nominal do lote ou o total líquido aprovado ultrapassa o limite de representação suportado.');
assertTrue(expCapacidadeTotal.acaoRecomendada.includes('fracionado'));

// 2.7 Código desconhecido - fallback seguro
const expDesconhecido = obterExplicacaoRecusa('REGRA_CUSTOM_NOVA', 'Regra customizada não foi satisfeita.');
assertEqual(expDesconhecido.titulo, 'Recusa: REGRA_CUSTOM_NOVA');
assertEqual(expDesconhecido.descricao, 'Regra customizada não foi satisfeita.');
assertTrue(expDesconhecido.acaoRecomendada.includes('política do fundo'));

console.log('✓ Preservação de mensagem original, limites de capacidade técnica e fallback seguro passaram!');

// 3. Testes do Helper de Visualização em Memória (Modo Público Efêmero)
console.log('Testando publicDemoResults...');

const mockDemoCompleto: SimulationEnvelope = {
  simulation_id: 'demo-efemera-uuid',
  rule_version: 1,
  rule_version_id: 1,
  data_base: '2026-10-22',
  status: 'concluida',
  total_itens: 3,
  aprovados: 1,
  recusados: 2,
  total_nominal: '15000.00',
  total_liquido: '4700.00',
  resultados: [
    { linha: 1, documento: 'NF-1', sacado: 'S1', aprovado: true, valor_nominal: '5000.00', valor_liquido: '4700.00', motivos: [] },
    { linha: 2, documento: 'NF-2', sacado: 'S2', aprovado: false, valor_nominal: '50.00', valor_liquido: null, motivos: [{ codigo: 'VALOR_MINIMO', mensagem: 'Abaixo piso' }] },
    { linha: 3, documento: 'NF-3', sacado: 'S3', aprovado: false, valor_nominal: '10000.00', valor_liquido: null, motivos: [{ codigo: 'PRAZO_MAXIMO', mensagem: 'Acima prazo' }] },
  ],
  pagination: { page: 1, page_size: 50, total: 3, total_pages: 1 },
  auditoria: { cadastro_fonte: 'SIMULADO_DEMO', carteira_referencia: 'REF_TEST', configuration_hash: 'abc' },
  avisos: [],
};

// 3.1 Verificação de snapshot completo
assertTrue(verificarSnapshotCompleto(mockDemoCompleto), 'Snapshot de 3 itens com 3 resultados deve ser completo');

const mockParcial: SimulationEnvelope = {
  ...mockDemoCompleto,
  total_itens: 100, // 100 itens no lote mas apenas 3 carregados na página
};
assertEqual(verificarSnapshotCompleto(mockParcial), false, 'Snapshot com total_itens > length é parcial');

// 3.2 Filtrar por aprovado preserva totais globais
const filtradoAprovado = aplicarFiltroPaginacaoLocal(mockDemoCompleto, 'aprovado', 'todos', 1, 50);
assertEqual(filtradoAprovado.resultados.length, 1, 'Deve retornar 1 aprovado');
assertEqual(filtradoAprovado.total_itens, 3, 'Total global de itens deve se manter 3');
assertEqual(filtradoAprovado.aprovados, 1, 'Total global de aprovados deve se manter 1');
assertEqual(filtradoAprovado.recusados, 2, 'Total global de recusados deve se manter 2');
assertEqual(filtradoAprovado.total_nominal, '15000.00', 'Total nominal deve se manter inalterado');
assertEqual(filtradoAprovado.total_liquido, '4700.00', 'Total líquido deve se manter inalterado');
assertEqual(filtradoAprovado.pagination.total, 1, 'Total de paginação filtrada deve ser 1');

// 3.3 Filtrar por motivo VALOR_MINIMO
const filtradoMotivo = aplicarFiltroPaginacaoLocal(mockDemoCompleto, 'todos', 'VALOR_MINIMO', 1, 50);
assertEqual(filtradoMotivo.resultados.length, 1, 'Deve retornar 1 item com VALOR_MINIMO');
assertEqual(filtradoMotivo.resultados[0].documento, 'NF-2');
assertEqual(filtradoMotivo.total_itens, 3, 'Total global de itens deve continuar 3');

// 3.4 Restaurar filtro para 'todos' recupera todos os 3 itens originais
const restaurado = aplicarFiltroPaginacaoLocal(mockDemoCompleto, 'todos', 'todos', 1, 50);
assertEqual(restaurado.resultados.length, 3, 'Restaurar deve exibir novamente todos os 3 resultados');
assertEqual(restaurado.pagination.total, 3);
console.log('✓ Pure helper de modo público efêmero validado com sucesso!');

// 4. Testes Reais com FakeWebSocket de Resiliência e Transporte WebSocket v1
console.log('Testando resiliência real de BulkUploadSession com FakeWebSocket...');

// Mock puro de File sem I/O
class FakeFile {
  name: string;
  size: number;
  private content: Uint8Array;

  constructor(name: string, sizeBytes: number) {
    this.name = name;
    this.size = sizeBytes;
    this.content = new Uint8Array(sizeBytes);
  }

  slice(start: number, end: number) {
    const sub = this.content.subarray(start, end);
    return {
      arrayBuffer: async () => sub.buffer,
    };
  }
}

// FakeWebSocket puro
class FakeWebSocket {
  url: string;
  readyState = 0; // CONNECTING
  binaryType = 'blob';
  sentMessages: unknown[] = [];

  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((ev: { data: string }) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    setTimeout(() => {
      if (this.readyState === 0) {
        this.readyState = 1; // OPEN
        this.onopen?.();
      }
    }, 5);
  }

  send(data: unknown) {
    this.sentMessages.push(data);
  }

  close() {
    this.readyState = 3; // CLOSED
    this.onclose?.();
  }

  serverEmitMessage(dataObj: Record<string, unknown>) {
    this.onmessage?.({ data: JSON.stringify(dataObj) });
  }

  serverEmitClose() {
    this.readyState = 3; // CLOSED
    this.onclose?.();
  }

  serverEmitError() {
    this.onerror?.();
  }
}

export async function runBulkTransportTests(): Promise<void> {
  // Salva global original se existir
  const originalWS = (globalThis as unknown as { WebSocket?: unknown }).WebSocket;
  let activeFakeWS: FakeWebSocket | null = null;

  (globalThis as unknown as { WebSocket: unknown }).WebSocket = class extends FakeWebSocket {
    constructor(url: string) {
      super(url);
      activeFakeWS = this;
    }
  };

  try {
    // Caso 1: Fechamento antes do ready -> rejeita start() e reporta wasCompleted = false
    {
      const fileMock = new FakeFile('lote_1.csv', 1024) as unknown as File;
      const closedEvents: boolean[] = [];

      const session = new BulkUploadSession(fileMock, {
        onProgress: () => {},
        onError: () => {},
        onComplete: () => {},
        onSessionClosed: (wasCompleted) => {
          closedEvents.push(wasCompleted);
        },
      });

      const startPromise = session.start();

      // Aguarda conectar e fecha antes de emitir ready
      await new Promise((r) => setTimeout(r, 10));
      assertTrue(activeFakeWS !== null, 'FakeWebSocket deve ser instanciado');
      activeFakeWS!.serverEmitClose();

      let startFailed = false;
      try {
        await startPromise;
      } catch {
        startFailed = true;
      }

      assertEqual(startFailed, true, 'start() deve ser rejeitado se fechar antes do ready');
      assertEqual(closedEvents.length > 0 ? closedEvents[0] : null, false, 'onSessionClosed deve receber wasCompleted=false');
      console.log('✓ Caso 1: Desconexão antes de ready rejeita start e reporta wasCompleted=false');
    }

    // Caso 2: Emissão de ready, avanço de streaming e desconexão durante espera de ACK
    {
      const fileMock = new FakeFile('lote_2.csv', 5000000) as unknown as File; // 5 MB > janela de 4 MiB
      const errorsReported: { codigo: string; mensagem: string }[] = [];
      const closedEvents: boolean[] = [];

      const session = new BulkUploadSession(fileMock, {
        onProgress: () => {},
        onError: (err) => {
          errorsReported.push(err);
        },
        onComplete: () => {},
        onSessionClosed: (wasCompleted) => {
          closedEvents.push(wasCompleted);
        },
      });

      const startPromise = session.start();
      await new Promise((r) => setTimeout(r, 10));

      // Servidor emite ready com janela de 4 MiB (4194304) e chunks de 256 KiB
      activeFakeWS!.serverEmitMessage({
        type: 'ready',
        chunk_bytes: 262144,
        window_bytes: 4194304,
      });

      await startPromise; // Handshake resolvido com sucesso!

      // Aguarda fatiar até encher a janela e ficar aguardando ACK
      await new Promise((r) => setTimeout(r, 20));

      // Servidor desconecta abruptamente enquanto cliente aguarda ACK
      activeFakeWS!.serverEmitClose();

      // Aguarda desfecho da promise cancelada
      await new Promise((r) => setTimeout(r, 15));

      assertEqual(closedEvents.length > 0 ? closedEvents[0] : null, false, 'onSessionClosed reporta wasCompleted=false em queda durante envio');
      assertTrue(errorsReported.length > 0, 'Erro de streaming deve ser emitido');
      assertEqual(errorsReported.length > 0 ? errorsReported[0].codigo : null, 'ERRO_STREAMING');
      console.log('✓ Caso 2: Queda aguardando ACK acorda awaiter, dispara onError e reporta wasCompleted=false');
    }

    // Caso 3: Conclusão completa seguida de encerramento de sessão -> onComplete recebe payload exato e onSessionClosed recebe wasCompleted=true
    {
      const fileMock = new FakeFile('lote_3.csv', 500) as unknown as File;
      const completedSimulations: SimulationEnvelope[] = [];
      const closedEvents: boolean[] = [];

      const session = new BulkUploadSession(fileMock, {
        onProgress: () => {},
        onError: () => {},
        onComplete: (sim) => {
          completedSimulations.push(sim);
        },
        onSessionClosed: (wasCompleted) => {
          closedEvents.push(wasCompleted);
        },
      });

      const startPromise = session.start();
      await new Promise((r) => setTimeout(r, 10));

      activeFakeWS!.serverEmitMessage({
        type: 'ready',
        chunk_bytes: 500,
        window_bytes: 1000,
      });
      await startPromise;

      // Confirma todos os 500 bytes via ack
      activeFakeWS!.serverEmitMessage({
        type: 'ack',
        received_bytes: 500,
      });

      // Servidor emite complete com envelope
      const mockResultPayload: SimulationEnvelope = {
        ...mockDemoCompleto,
        simulation_id: 'uuid-finalizado',
      };

      activeFakeWS!.serverEmitMessage({
        type: 'complete',
        simulation: mockResultPayload,
      });

      assertEqual(completedSimulations.length > 0 ? completedSimulations[0].simulation_id : null, 'uuid-finalizado', 'onComplete deve receber payload exato');
      assertEqual(session.getIsCompleted(), true, 'session.isCompleted deve ser true');

      // Agora servidor encerra a sessão
      activeFakeWS!.serverEmitClose();

      assertEqual(closedEvents.length > 0 ? closedEvents[0] : null, true, 'onSessionClosed deve receber wasCompleted=true após conclusão');
      console.log('✓ Caso 3: Conclusão completa preserva payload exato e reporta wasCompleted=true no close');
    }

    // Caso 4: Encerramento manual (close) não emite onError antigo
    {
      const fileMock = new FakeFile('lote_4.csv', 1000000) as unknown as File;
      let erroDisparado = false;

      const session = new BulkUploadSession(fileMock, {
        onProgress: () => {},
        onError: () => {
          erroDisparado = true;
        },
        onComplete: () => {},
        onSessionClosed: () => {},
      });

      const startPromise = session.start();
      await new Promise((r) => setTimeout(r, 10));
      activeFakeWS!.serverEmitMessage({ type: 'ready', chunk_bytes: 256, window_bytes: 512 });
      await startPromise;

      // Usuário troca de arquivo / fecha manualmente
      session.close();
      await new Promise((r) => setTimeout(r, 20));

      assertEqual(erroDisparado, false, 'close() manual não deve disparar onError de streaming residual');
      console.log('✓ Caso 4: Fechamento manual não polui com onError residual');
    }
  } finally {
    // Restaura global
    (globalThis as unknown as { WebSocket?: unknown }).WebSocket = originalWS;
  }
}
