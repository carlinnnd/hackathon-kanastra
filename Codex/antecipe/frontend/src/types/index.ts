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
  status?: 'APROVADA' | 'RECUSADA' | 'CARTEIRA_HISTORICA';
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

export interface SimulationAnalytics {
  tipo_analise: 'novas_operacoes' | 'carteira';
  status_counts: Record<string, number>;
  valor_nominal_total: string;
  valor_nominal_elegivel: string;
  valor_desconto: string;
  valor_liquido: string;
  aprovacao_valor_pct: string;
  prazo_medio_ponderado: string | null;
  motivos: { codigo: string; quantidade: number; valor_nominal: string }[];
  faixas_vencimento: Record<string, number>;
  exposicoes: { doc_fundo?: string; raiz: string; percentual: string; valor_nominal: string }[];
  metodologia: string;
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
  resumo_motivos?: Record<string, number>;
  resultados: ResultadoItem[];
  pagination: PaginationMeta;
  auditoria: AuditoriaMeta;
  avisos: string[];
}

export interface UploadCapabilities {
  http_max_bytes: number;
  bulk_max_bytes: number;
  max_records: number;
  bulk_transport: 'websocket' | 'http';
  bulk_path: string;
}

export interface EconomicGroupBranch {
  doc_sacado: string;
  nome_sacado: string;
  tipo_unidade: string;
  qtd_titulos: number;
  valor_nominal: string;
  percentual_carteira: string;
}

export interface EconomicGroupXRay {
  raiz_cnpj: string;
  grupo_economico: string;
  total_carteira_fundo: string;
  exposicao_atual_grupo: string;
  concentracao_atual_pct: string;
  limite_regulamentar_pct: string;
  excesso_atual_brl: string;
  bloqueado_novas_aquisicoes: boolean;
  filiais: EconomicGroupBranch[];
}

export interface RuleValidatorItem {
  codigo: string;
  ativo: boolean;
  parametros: Record<string, unknown>;
  descricao?: string;
}

export interface RuleConfiguration {
  fundo: {
    nome: string;
    cnpj: string;
  };
  data_base?: string;
  validadores: RuleValidatorItem[];
  precificacao: {
    metodo: string;
    taxa_mensal_percentual: number;
    base_dias: number;
  };
}

export interface RuleVersionItem {
  id: number;
  version_number: number;
  created_at: string;
  created_by: string;
  change_reason: string | null;
  is_active: boolean;
  configuration_hash: string;
}

export interface WhatIfScenarioSummary {
  total_itens: number;
  aprovados: number;
  recusados: number;
  total_nominal: string;
  total_liquido: string;
  taxa_aprovacao_pct: string;
  resumo_motivos: Record<string, number>;
}

export interface WhatIfResult {
  baseline_version: number;
  data_base: string;
  baseline: WhatIfScenarioSummary;
  what_if: WhatIfScenarioSummary;
  delta: {
    aprovados_delta: number;
    liquido_delta_brl: string;
  };
}

export interface SingleReceivableInput {
  NOME_FUNDO?: string;
  DOC_FUNDO?: string;
  NOME_CEDENTE: string;
  DOC_CEDENTE: string;
  NOME_SACADO: string;
  DOC_SACADO: string;
  NU_DOCUMENTO: string;
  TIPO_RECEBIVEL: string;
  VALOR_NOMINAL: string;
  DATA_VENCIMENTO_ORIGINAL: string;
  DATA_AQUISICAO?: string;
}

export interface HealthResponse {
  data_base_atual?: string;
  fuso_horario?: string;
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
  configuration_hash?: string;
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

export interface AuthUser {
  id: string;
  nome: string;
  email: string;
  cargo: string;
  organizacao: string;
  token: string;
  modo_autenticacao: 'backend_jwt' | 'sessao_local_kanastra';
}

export interface LoginPayload {
  email: string;
  password: string;
  cargo?: string;
  name?: string;
  mode?: 'login' | 'signup';
}
