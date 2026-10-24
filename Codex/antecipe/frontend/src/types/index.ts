/**
 * Tipos do Domínio e Contrato de Integração Antecipe
 * Alinhado com Codex/antecipe/docs/EXECUTION_PLAN.md e rotas FastAPI
 */

export interface MotivoRecusa {
  codigo: string;
  mensagem: string;
  dados?: Record<string, unknown>;
}

export interface ResultadoItem {
  linha: number;
  documento: string;
  sacado: string;
  aprovado: boolean;
  valor_nominal: string | null;
  valor_liquido: string | null;
  motivos: MotivoRecusa[];
}

export interface PaginationMeta {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface AuditoriaMeta {
  cadastro_fonte: string;
  carteira_referencia: string;
  configuration_hash: string;
}

export interface SimulationEnvelope {
  simulation_id: string;
  rule_version: number;
  rule_version_id: number;
  data_base: string;
  status: string;
  total_itens: number;
  aprovados: number;
  recusados: number;
  total_nominal: string;
  total_liquido: string;
  resultados: ResultadoItem[];
  pagination: PaginationMeta;
  auditoria: AuditoriaMeta;
  avisos: string[];
}

export interface HealthResponse {
  status: string;
  estoque_carregado: boolean;
  fundo: string;
  total_registros_estoque: number;
  rule_version?: number;
  cadastro_fonte?: string;
  aviso_demo_publica?: string;
}

export interface PortfolioSummary {
  nome_fundo: string;
  cnpj_fundo: string;
  total_nominal: string;
  total_recebiveis: number;
  maior_concentracao_raiz_pct: string;
  avisos?: string[];
}

export interface RuleVersion {
  id: number;
  version_number: number;
  created_at: string;
  created_by: string;
  change_reason: string;
  is_active: boolean;
}

export interface ApiErrorDetail {
  codigo?: string;
  mensagem?: string;
}

export interface ApiErrorResponse {
  detail?: string | ApiErrorDetail;
}
