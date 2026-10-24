/**
 * Cliente de Transporte WebSocket para Bulk Upload de Recebíveis
 * Conforme contrato especificado em antecipe-bulk-upload/index.md:
 * - Frames binários de até 256 KiB
 * - Leitura via File.slice().arrayBuffer() (nunca o arquivo inteiro em memória)
 * - Janela deslizante negociada (padr?o: 12 MiB) aguardando confirmação ACK
 * - Envio de {type: "finish"} após confirmação de todos os bytes
 * - Recebimento de eventos de progresso {type: "progress", rows_processed}
 * - Recebimento do envelope final {type: "complete", simulation}
 * - Sessão interativa para paginação e filtros via {type: "query", request_id, page, page_size, status, reason}
 *   na MESMA conexão WebSocket (evita 404 em instâncias efêmeras da Vercel).
 */

import { SimulationEnvelope, StreamProgressInfo } from '../types';

export interface BulkUploadCallbacks {
  onProgress: (info: StreamProgressInfo) => void;
  onError: (erro: { codigo: string; mensagem: string }) => void;
  onComplete: (simulation: SimulationEnvelope) => void;
  onSessionClosed?: (wasCompleted: boolean) => void;
}

export class BulkUploadSession {
  private ws: WebSocket | null = null;
  private isClosedManually = false;
  private isCompleted = false;
  private isHandshakeComplete = false;
  private handshakeRejector: ((err: Error) => void) | null = null;
  private handshakeResolver: (() => void) | null = null;

  private pendingQueries = new Map<string, (sim: SimulationEnvelope) => void>();
  private pendingQueryErrors = new Map<string, (err: Error) => void>();
  private requestCounter = 0;
  private pendingExport: {id: string; chunks: BlobPart[]; resolve: (blob: Blob) => void; reject: (err: Error) => void; timer: ReturnType<typeof setTimeout>} | null = null;

  // Controle de janela deslizante (sliding window)
  private ackPromiseResolver: (() => void) | null = null;
  private ackPromiseRejector: ((err: Error) => void) | null = null;
  private serverAckedBytes = 0;

  constructor(
    private file: File,
    private callbacks: BulkUploadCallbacks,
    private bulkPathOverride?: string,
    private tipoAnalise = 'novas_operacoes'
  ) {}

  public async start(): Promise<void> {
    const wsUrl = this.resolveWsUrl();

    return new Promise<void>((resolve, reject) => {
      this.handshakeResolver = resolve;
      this.handshakeRejector = reject;

      try {
        const WSClass = this.getWebSocketConstructor();
        this.ws = new WSClass(wsUrl);
        this.ws.binaryType = 'arraybuffer';
      } catch (err) {
        this.handshakeRejector = null;
        this.handshakeResolver = null;
        reject(new Error(`Falha ao iniciar conexão WebSocket: ${err instanceof Error ? err.message : String(err)}`));
        return;
      }

      this.ws.onopen = () => {
        // Envia handshake inicial conforme contrato v1
        const startMsg = JSON.stringify({
          type: 'start',
          size_bytes: this.file.size,
          filename: this.file.name,
          protocol_version: 1,
          tipo_analise: this.tipoAnalise,
        });
        this.ws?.send(startMsg);
      };

      this.ws.onmessage = async (event: MessageEvent) => {
        if (typeof event.data === 'string') {
          try {
            const data = JSON.parse(event.data);
            await this.handleServerMessage(data);
          } catch {
            // Log seguro sem expor payload bruto
            console.error('Mensagem recebida do servidor em formato inválido.');
          }
        }
      };

      this.ws.onerror = () => {
        const errMsg = 'Erro na comunicação via WebSocket durante o envio do arquivo.';
        if (!this.isHandshakeComplete && this.handshakeRejector) {
          this.handshakeRejector(new Error(errMsg));
          this.handshakeRejector = null;
          this.handshakeResolver = null;
        }
        if (!this.isClosedManually) {
          this.callbacks.onError({
            codigo: 'ERRO_CONEXAO_WEBSOCKET',
            mensagem: errMsg,
          });
        }
        this.wakeAndCancelAck(new Error(errMsg));
        this.rejectAllPendingQueries(new Error(errMsg));
      };

      this.ws.onclose = () => {
        const closeErr = new Error('Conexão WebSocket encerrada pelo servidor.');

        // Se fechou antes do handshake (ready), rejeita a promise de start
        if (!this.isHandshakeComplete && this.handshakeRejector) {
          this.handshakeRejector(closeErr);
          this.handshakeRejector = null;
          this.handshakeResolver = null;
        }

        // Acorda qualquer awaiter de ACK pendente para não travar o loop de fatiamento
        this.wakeAndCancelAck(closeErr);

        // Notifica callback informando se o upload já havia sido concluído ou se caiu durante a transmissão
        if (!this.isClosedManually) {
          this.callbacks.onSessionClosed?.(this.isCompleted);
        }

        this.rejectAllPendingQueries(closeErr);
      };
    });
  }

  private getWebSocketConstructor(): typeof WebSocket {
    if (typeof WebSocket !== 'undefined') {
      return WebSocket;
    }
    const g = globalThis;
    if ('WebSocket' in g && typeof g.WebSocket === 'function') {
      return g.WebSocket as unknown as typeof WebSocket;
    }
    throw new Error('Ambiente sem suporte a WebSocket nativo.');
  }

  private resolveWsUrl(): string {
    const loc = typeof window !== 'undefined' ? window.location : { protocol: 'http:', host: 'localhost:8000' };
    const protocol = loc.protocol === 'https:' ? 'wss:' : 'ws:';
    const path = this.bulkPathOverride
      ? (this.bulkPathOverride.startsWith('/') ? this.bulkPathOverride : `/${this.bulkPathOverride}`)
      : '/api/simulations/stream';

    // Se o override já for uma URL completa wss:// ou ws://, valida o protocolo
    if (this.bulkPathOverride && (this.bulkPathOverride.startsWith('ws://') || this.bulkPathOverride.startsWith('wss://'))) {
      if (loc.protocol === 'https:' && this.bulkPathOverride.startsWith('ws://')) {
        // Não permite ws:// inseguro se a página estiver em https://
        return this.bulkPathOverride.replace('ws://', 'wss://');
      }
      return this.bulkPathOverride;
    }

    return `${protocol}//${loc.host}${path}`;
  }

  private async handleServerMessage(data: Record<string, unknown>): Promise<void> {
    const msgType = data.type as string;

    switch (msgType) {
      case 'ready': {
        this.isHandshakeComplete = true;
        if (this.handshakeResolver) {
          this.handshakeResolver();
          this.handshakeResolver = null;
          this.handshakeRejector = null;
        }

        const chunkBytes = (data.chunk_bytes as number) || 262144; // 256 KiB
        const windowBytes = (data.window_bytes as number) || 4194304; // 4 MiB

        // Inicia a transmissão em streaming com controle de fluxo por janela
        this.streamFile(chunkBytes, windowBytes).catch((err) => {
          // Protege contra disparar onError se a sessão foi encerrada manualmente (troca de arquivo/unmount)
          if (!this.isClosedManually) {
            this.callbacks.onError({
              codigo: 'ERRO_STREAMING',
              mensagem: err instanceof Error ? err.message : String(err),
            });
          }
        });
        break;
      }

      case 'ack': {
        const receivedBytes = data.received_bytes as number;
        this.onAckReceived(receivedBytes);
        break;
      }

      case 'progress': {
        const rowsProcessed = (data.rows_processed as number) || 0;
        this.callbacks.onProgress({
          fase: 'processing',
          linhasProcessadas: rowsProcessed,
        });
        break;
      }

      case 'complete': {
        this.isCompleted = true;
        const simulation = data.simulation as SimulationEnvelope;
        this.callbacks.onComplete(simulation);
        break;
      }

      case 'page': {
        const reqId = data.request_id as string;
        const simulation = data.simulation as SimulationEnvelope;
        const resolver = this.pendingQueries.get(reqId);
        if (resolver) {
          this.pendingQueries.delete(reqId);
          this.pendingQueryErrors.delete(reqId);
          resolver(simulation);
        }
        break;
      }

      case 'export_chunk': {
        const pending = this.pendingExport;
        if (pending && pending.id === data.request_id) {
          const decoded = atob(data.data as string);
          const bytes = new Uint8Array(decoded.length);
          for (let i = 0; i < decoded.length; i++) bytes[i] = decoded.charCodeAt(i);
          pending.chunks.push(bytes);
        }
        break;
      }
      case 'export_complete': {
        const pending = this.pendingExport;
        if (pending && pending.id === data.request_id) {
          this.pendingExport = null;
          clearTimeout(pending.timer);
          pending.resolve(new Blob(pending.chunks, {type: data.media_type as string}));
        }
        break;
      }
      case 'error': {
        const reqId = data.request_id as string | undefined;
        const codigo = (data.codigo as string) || 'ERRO_MOTOR';
        const mensagem = (data.mensagem as string) || 'Ocorreu um erro no motor de simulação.';

        // Se ocorreu erro antes do handshake estar pronto, rejeita o start()
        if (!this.isHandshakeComplete && this.handshakeRejector) {
          this.handshakeRejector(new Error(`[${codigo}] ${mensagem}`));
          this.handshakeRejector = null;
          this.handshakeResolver = null;
        }

        if (reqId && this.pendingExport?.id === reqId) {
          clearTimeout(this.pendingExport.timer);
          this.pendingExport.reject(new Error(mensagem));
          this.pendingExport = null;
        } else if (reqId && this.pendingQueryErrors.has(reqId)) {
          const rejector = this.pendingQueryErrors.get(reqId);
          this.pendingQueries.delete(reqId);
          this.pendingQueryErrors.delete(reqId);
          rejector?.(new Error(`[${codigo}] ${mensagem}`));
        } else if (!this.isClosedManually) {
          this.callbacks.onError({ codigo, mensagem });
        }
        break;
      }
    }
  }

  private onAckReceived(receivedBytes: number): void {
    this.serverAckedBytes = receivedBytes;
    this.callbacks.onProgress({
      fase: 'uploading',
      bytesEnviados: receivedBytes,
      totalBytes: this.file.size,
    });
    if (this.ackPromiseResolver) {
      this.ackPromiseResolver();
      this.ackPromiseResolver = null;
      this.ackPromiseRejector = null;
    }
  }

  private wakeAndCancelAck(err: Error): void {
    if (this.ackPromiseRejector) {
      this.ackPromiseRejector(err);
      this.ackPromiseResolver = null;
      this.ackPromiseRejector = null;
    }
  }

  private async waitForWindow(sentBytes: number, windowBytes: number): Promise<void> {
    while (sentBytes - this.serverAckedBytes >= windowBytes && !this.isClosedManually) {
      if (!this.ws || this.ws.readyState !== 1 /* WebSocket.OPEN */) {
        throw new Error('Conexão encerrada enquanto aguardava confirmação de envio.');
      }
      await new Promise<void>((resolve, reject) => {
        this.ackPromiseResolver = resolve;
        this.ackPromiseRejector = reject;
      });
    }
  }

  private async streamFile(chunkSize: number, windowBytes: number): Promise<void> {
    const totalSize = this.file.size;
    let offset = 0;

    while (offset < totalSize && !this.isClosedManually) {
      // Espera se a janela negociada estiver cheia
      await this.waitForWindow(offset, windowBytes);

      if (this.isClosedManually || !this.ws || this.ws.readyState !== 1 /* WebSocket.OPEN */) {
        throw new Error('Conexão fechada durante o streaming do arquivo.');
      }

      const nextOffset = Math.min(offset + chunkSize, totalSize);
      const slice = this.file.slice(offset, nextOffset);
      const buffer = await slice.arrayBuffer();

      this.ws.send(buffer);
      offset = nextOffset;
    }

    // Aguarda todos os bytes serem confirmados (ACK total)
    while (this.serverAckedBytes < totalSize && !this.isClosedManually) {
      if (!this.ws || this.ws.readyState !== 1 /* WebSocket.OPEN */) {
        throw new Error('Conexão encerrada antes da confirmação final de recebimento.');
      }
      await new Promise<void>((resolve, reject) => {
        this.ackPromiseResolver = resolve;
        this.ackPromiseRejector = reject;
      });
    }

    if (!this.isClosedManually && this.ws && this.ws.readyState === 1 /* WebSocket.OPEN */) {
      // Envia evento de encerramento do stream mantendo a contagem de progresso de linhas monotônica
      this.ws.send(JSON.stringify({ type: 'finish' }));
    }
  }

  /**
   * Consulta paginada ou filtrada na MESMA conexão ativa.
   */
  public query(
    page: number = 1,
    pageSize: number = 50,
    statusFilter?: string,
    reasonFilter?: string
  ): Promise<SimulationEnvelope> {
    if (!this.ws || this.ws.readyState !== 1 /* WebSocket.OPEN */) {
      return Promise.reject(
        new Error('A sessão WebSocket desta simulação expirou ou foi fechada. Reenvie o arquivo para consultar novamente.')
      );
    }

    const requestId = `req_${++this.requestCounter}_${Date.now()}`;
    const queryMsg = JSON.stringify({
      type: 'query',
      request_id: requestId,
      page,
      page_size: pageSize,
      status: statusFilter && statusFilter !== 'todos' ? statusFilter : 'todos',
      reason: reasonFilter && reasonFilter !== 'todos' ? reasonFilter : 'todos',
    });

    return new Promise<SimulationEnvelope>((resolve, reject) => {
      this.pendingQueries.set(requestId, resolve);
      this.pendingQueryErrors.set(requestId, reject);
      this.ws?.send(queryMsg);
    });
  }

  public isAlive(): boolean {
    return Boolean(this.ws && this.ws.readyState === 1 /* WebSocket.OPEN */);
  }

  public exportResult(format: 'csv' | 'pdf' | 'violacoes'): Promise<Blob> {
    if (!this.isAlive() || !this.isCompleted) return Promise.reject(new Error('Sessão encerrada. Reenvie o CSV para exportar os resultados completos.'));
    if (this.pendingExport) return Promise.reject(new Error('Aguarde a exportação atual.'));
    const id = `export_${++this.requestCounter}`;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        if (this.pendingExport?.id === id) {
          this.pendingExport = null;
          reject(new Error('Tempo de exportação excedido. Tente novamente enquanto a sessão estiver ativa.'));
        }
      }, 120000);
      this.pendingExport = {id, chunks: [], resolve, reject, timer};
      this.ws?.send(JSON.stringify({type: 'export', request_id: id, format}));
    });
  }

  public getIsCompleted(): boolean {
    return this.isCompleted;
  }

  public close(): void {
    this.isClosedManually = true;
    const manualCloseErr = new Error('Sessão encerrada localmente.');
    this.wakeAndCancelAck(manualCloseErr);

    if (this.ws) {
      if (this.ws.readyState === 1 || this.ws.readyState === 0 /* OPEN or CONNECTING */) {
        this.ws.close();
      }
      this.ws = null;
    }
    this.rejectAllPendingQueries(manualCloseErr);
  }

  private rejectAllPendingQueries(err: Error): void {
    if (this.pendingExport) {
      clearTimeout(this.pendingExport.timer);
      this.pendingExport.reject(err);
      this.pendingExport = null;
    }
    for (const rejector of this.pendingQueryErrors.values()) {
      rejector(err);
    }
    this.pendingQueries.clear();
    this.pendingQueryErrors.clear();
  }
}
