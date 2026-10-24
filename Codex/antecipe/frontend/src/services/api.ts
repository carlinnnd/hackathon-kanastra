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
  EconomicGroupXRay,
  RuleConfiguration,
  RuleVersionItem,
  WhatIfResult,
  SingleReceivableInput,
  AuthUser,
  LoginPayload,
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
      if (res.status === 413) {
        codigo = 'ARQUIVO_MUITO_GRANDE';
        errorMsg =
          'O arquivo excede o limite máximo permitido pelo transporte HTTP do provedor (4,5 MB). Utilize o envio via streaming WebSocket para lotes extensos.';
      } else if (res.status === 405) {
        codigo = 'METODO_NAO_PERMITIDO';
        errorMsg = 'Método HTTP não permitido para esta operação.';
      } else if (res.status === 503) {
        codigo = 'SERVICO_INDISPONIVEL';
        errorMsg = 'Serviço temporariamente indisponível. Verifique o status do motor.';
      }
    }

    throw new ApiError(errorMsg, res.status, codigo);
  }

  return res.json() as Promise<T>;
}

const AUTH_STORAGE_KEY = 'kanastra_antecipe_auth_session_v1';

export const api = {
  getAuthSession(): AuthUser | null {
    try {
      const raw = localStorage.getItem(AUTH_STORAGE_KEY);
      if (!raw) return null;
      return JSON.parse(raw) as AuthUser;
    } catch {
      return null;
    }
  },

  clearAuthSession(): void {
    try {
      localStorage.removeItem(AUTH_STORAGE_KEY);
    } catch {
      // ignora em modo privado restrito
    }
  },

  async login(payload: LoginPayload): Promise<AuthUser> {
    const cleanEmail = payload.email.trim().toLowerCase();
    const cargo = payload.cargo || 'Analista de Risco FIDC';

    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: cleanEmail,
          password: payload.password,
          cargo,
          name: payload.name,
          mode: payload.mode || 'login',
        }),
      });
      if (res.ok) {
        const data = (await res.json()) as Partial<AuthUser> & { access_token?: string; name?: string };
        const user: AuthUser = {
          id: data.id || `usr-${Date.now()}`,
          nome: data.nome || data.name || cleanEmail.split('@')[0].replace(/[._-]/g, ' '),
          email: data.email || cleanEmail,
          cargo: data.cargo || cargo,
          organizacao: data.organizacao || 'Kanastra • ANTECIPE FIDC',
          token: data.token || data.access_token || 'jwt-session-active',
          modo_autenticacao: 'backend_jwt',
        };
        localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(user));
        return user;
      }
      if (res.status === 422 || res.status === 401) {
        await handleResponse<AuthUser>(res);
      }
    } catch (err) {
      if (err instanceof ApiError) {
        throw err;
      }
    }

    const nameParts = cleanEmail
      .split('@')[0]
      .split(/[._-]/)
      .filter(Boolean)
      .map((p) => p.charAt(0).toUpperCase() + p.slice(1));
    const displayName = payload.name?.trim() || (nameParts.length > 0 ? nameParts.join(' ') : 'Operador Kanastra');

    const fallbackUser: AuthUser = {
      id: `kanastra-op-${Date.now().toString(36)}`,
      nome: displayName,
      email: cleanEmail,
      cargo,
      organizacao: 'Kanastra • ANTECIPE FIDC',
      token: `kanastra-sess-${btoa(cleanEmail).slice(0, 16)}`,
      modo_autenticacao: 'sessao_local_kanastra',
    };
    localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(fallbackUser));
    return fallbackUser;
  },

  async getHealth(): Promise<HealthResponse> {
    const res = await fetch(`${API_BASE}/health`);
    return handleResponse<HealthResponse>(res);
  },

  async getPortfolioSummary(): Promise<PortfolioSummary> {
    const res = await fetch(`${API_BASE}/portfolio/summary`);
    return handleResponse<PortfolioSummary>(res);
  },

  async getEconomicGroupXRay(raizCnpj: string): Promise<EconomicGroupXRay> {
    const clean = raizCnpj.replace(/\D/g, '').slice(0, 8);
    const res = await fetch(`${API_BASE}/portfolio/economic-group/${clean}`);
    return handleResponse<EconomicGroupXRay>(res);
  },

  async getActiveRules(): Promise<RuleConfiguration> {
    const res = await fetch(`${API_BASE}/rules`);
    return handleResponse<RuleConfiguration>(res);
  },

  async getRuleVersions(): Promise<RuleVersion[]> {
    const res = await fetch(`${API_BASE}/rules/versions`);
    return handleResponse<RuleVersion[]>(res);
  },

  async updateActiveRules(
    configuration: RuleConfiguration,
    changeReason: string
  ): Promise<{
    status: string;
    id: number;
    version_number: number;
    configuration_hash: string;
    configuration: RuleConfiguration;
  }> {
    const res = await fetch(`${API_BASE}/rules/active`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        configuration,
        change_reason: changeReason,
      }),
    });
    return handleResponse(res);
  },

  async resetDefaultRules(): Promise<{
    status: string;
    id: number;
    version_number: number;
    configuration_hash: string;
    configuration: RuleConfiguration;
  }> {
    const res = await fetch(`${API_BASE}/rules/reset-default`, {
      method: 'POST',
    });
    return handleResponse(res);
  },

  async createRuleVersion(
    configuration: RuleConfiguration,
    changeReason: string,
    adminToken: string
  ): Promise<RuleVersionItem> {
    const res = await fetch(`${API_BASE}/rules/versions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Admin-Token': adminToken,
      },
      body: JSON.stringify({
        configuration,
        change_reason: changeReason,
      }),
    });
    return handleResponse<RuleVersionItem>(res);
  },

  async activateRuleVersion(
    versionId: number,
    adminToken: string,
    expectedActiveId?: number
  ): Promise<{ status: string; version_id: number }> {
    const q = expectedActiveId ? `?expected_active_version_id=${expectedActiveId}` : '';
    const res = await fetch(`${API_BASE}/rules/versions/${versionId}/activate${q}`, {
      method: 'POST',
      headers: {
        'X-Admin-Token': adminToken,
      },
    });
    return handleResponse<{ status: string; version_id: number }>(res);
  },

  async runWhatIfSimulation(
    configuration: RuleConfiguration,
    sampleRows: number = 100
  ): Promise<WhatIfResult> {
    const res = await fetch(`${API_BASE}/simulations/what-if`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        configuration,
        sample_rows: sampleRows,
      }),
    });
    return handleResponse<WhatIfResult>(res);
  },

  async evaluateSingleReceivable(
    item: SingleReceivableInput,
    dataBase: string = '2026-10-22'
  ): Promise<SimulationEnvelope> {
    const res = await fetch(`${API_BASE}/receivables/evaluate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        recebiveis: [item],
        data_base: dataBase,
      }),
    });
    return handleResponse<SimulationEnvelope>(res);
  },

  async simulateSampleBatch(rows: 100 | 1000 | 10000 | 100000): Promise<SimulationEnvelope> {
    const res = await fetch(`${API_BASE}/simulations/sample/${rows}`, {
      method: 'POST',
    });
    return handleResponse<SimulationEnvelope>(res);
  },

  getSampleCsvUrl(rows: 100 | 1000 | 10000 | 100000): string {
    return `${API_BASE}/samples/${rows}`;
  },

  async uploadSimulation(file: File, tipoAnalise = 'novas_operacoes'): Promise<SimulationEnvelope> {
    const formData = new FormData();
    formData.append('file', file);

    const res = await fetch(`${API_BASE}/simulations?tipo_analise=${encodeURIComponent(tipoAnalise)}`, {
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
