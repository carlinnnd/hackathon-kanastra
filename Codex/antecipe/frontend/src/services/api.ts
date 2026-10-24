/**
 * Serviço de Integração API Antecipe
 * Configurado com endpoints canônicos sem expor PII ou segredos.
 */

import {
  SimulationEnvelope,
  HealthResponse,
  PortfolioSummary,
  RuleVersion,
  ApiErrorResponse,
} from '../types';

const API_BASE = '/api';

export class ApiError extends Error {
  codigo?: string;
  status: number;

  constructor(message: string, status: number, codigo?: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.codigo = codigo;
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errorMsg = `Erro na requisição (Status ${res.status})`;
    let codigo: string | undefined;

    try {
      const errJson = (await res.json()) as ApiErrorResponse;
      if (errJson && errJson.detail) {
        if (typeof errJson.detail === 'string') {
          errorMsg = errJson.detail;
        } else if (errJson.detail.mensagem) {
          errorMsg = errJson.detail.mensagem;
          codigo = errJson.detail.codigo;
        }
      }
    } catch {
      // Se não for JSON, mantém mensagem genérica segura
      if (res.status === 503) {
        errorMsg = 'Serviço temporariamente indisponível. Verifique o status do motor.';
      } else if (res.status === 413) {
        errorMsg = 'Arquivo excede o limite máximo permitido para envio.';
      }
    }

    throw new ApiError(errorMsg, res.status, codigo);
  }

  return res.json() as Promise<T>;
}

export const api = {
  async getHealth(): Promise<HealthResponse> {
    const res = await fetch(`${API_BASE}/health`);
    return handleResponse<HealthResponse>(res);
  },

  async getPortfolioSummary(): Promise<PortfolioSummary> {
    const res = await fetch(`${API_BASE}/portfolio/summary`);
    return handleResponse<PortfolioSummary>(res);
  },

  async getRuleVersions(): Promise<RuleVersion[]> {
    const res = await fetch(`${API_BASE}/rules/versions`);
    return handleResponse<RuleVersion[]>(res);
  },

  async uploadSimulation(file: File): Promise<SimulationEnvelope> {
    const formData = new FormData();
    formData.append('file', file);

    const res = await fetch(`${API_BASE}/simulations`, {
      method: 'POST',
      body: formData,
    });
    return handleResponse<SimulationEnvelope>(res);
  },

  async getSimulation(
    id: string,
    page: number = 1,
    pageSize: number = 50,
    statusFilter?: string,
    reasonFilter?: string
  ): Promise<SimulationEnvelope> {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });

    if (statusFilter && statusFilter !== 'todos') {
      params.append('status', statusFilter);
    }
    if (reasonFilter && reasonFilter !== 'todos') {
      params.append('reason', reasonFilter);
    }

    const res = await fetch(`${API_BASE}/simulations/${id}?${params.toString()}`);
    return handleResponse<SimulationEnvelope>(res);
  },

  getDemoCsvUrl(): string {
    return `${API_BASE}/demo.csv`;
  },
};
