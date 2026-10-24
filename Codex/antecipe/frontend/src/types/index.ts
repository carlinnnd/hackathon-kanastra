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
  status?: string;
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
  tipo_analise?: 'novas_operacoes' | 'carteira';
  analytics?: SimulationAnalytics | null;
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

export interface SimulationAnalytics {
  tipo_analise: 'novas_operacoes' | 'carteira';
  status_counts: Record<string, number>;
  valor_nominal_total: string;
  valor_nominal_elegivel: string;
  valor_desconto: string;
  valor_liquido: string;
  aprovacao_valor_pct: string;
  prazo_medio_ponderado: string | null;
  motivos: {codigo: string; quantidade: number; valor_nominal: string}[];
  faixas_vencimento: Record<string, number>;
  exposicoes: {doc_fundo?: string; raiz: string; percentual: string; valor_nominal: string}[];
  metodologia: string;
}

export interface UploadCapabilities {
  http_max_bytes: number;
  bulk_max_bytes: number;
  max_records: number;
  bulk_transport: 'websocket' | 'http';
  bulk_path: string;
}

export interface HealthResponse {
  status: string;
  estoque_carregado: boolean;
  fundo: string;
  total_registros_estoque: number;
  rule_version?: number;
  cadastro_fonte?: string;
  aviso_demo_publica?: string;
  upload_capabilities?: UploadCapabilities;
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

export interface StreamProgressInfo {
  fase: 'uploading' | 'processing';
  bytesEnviados?: number;
  totalBytes?: number;
  linhasProcessadas?: number;
}
