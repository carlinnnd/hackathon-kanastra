/**
 * Dicionário Acessível de Mensagens e Códigos de Recusa do Motor Antecipe
 * Alinhado com WCAG 2.2 (3.3.1 Identificação e 3.3.3 Sugestão de Correção)
 * Utiliza estritamente os códigos canônicos definidos em validadores_antecipe.json e backend domain/DTO.
 * NUNCA expõe dados brutos de CSV nem PII.
 */

export interface ExplicacaoRecusa {
  titulo: string;
  descricao: string;
  acaoRecomendada: string;
  badgeVariant: 'warning' | 'danger' | 'info';
}

export const DICIONARIO_RECUSAS: Record<string, {
  titulo: string;
  descricaoPadrao: string;
  acaoRecomendada: string;
  badgeVariant: 'warning' | 'danger' | 'info';
}> = {
  // Códigos canônicos de regras ativas
  VALOR_MINIMO: {
    titulo: 'Valor Nominal Inferior ao Mínimo',
    descricaoPadrao: 'O título possui valor de face inferior ao piso estabelecido pela política de risco do fundo.',
    acaoRecomendada: 'Confira o valor de face com o documento fiscal original; o piso regulamentar é por título individual.',
    badgeVariant: 'warning',
  },
  PRAZO_MAXIMO: {
    titulo: 'Prazo de Vencimento Superior ao Limite',
    descricaoPadrao: 'O prazo residual entre a data-base de cálculo e o vencimento do título excede o limite máximo permitido pelo fundo.',
    acaoRecomendada: 'Submeta recebíveis com data de vencimento compatível com o prazo operacional do fundo.',
    badgeVariant: 'warning',
  },
  NAO_VENCIDA: {
    titulo: 'Título Já Vencido',
    descricaoPadrao: 'A data de vencimento do título é anterior à data-base da operação, inviabilizando a simulação de antecipação.',
    acaoRecomendada: 'Envie apenas títulos com vencimento igual ou posterior à data-base da esteira (títulos vigentes ou vencendo hoje).',
    badgeVariant: 'danger',
  },
  SITUACAO_CADASTRAL_SACADO: {
    titulo: 'Situação Cadastral Incompatível do Sacado',
    descricaoPadrao: 'A situação cadastral do sacado consultada na fonte do motor não atende aos critérios da política do fundo.',
    acaoRecomendada: 'Verifique a regularidade do CNPJ do sacado na base cadastral antes de submeter.',
    badgeVariant: 'danger',
  },
  TIPO_RECEBIVEL: {
    titulo: 'Tipo de Recebível Não Aceito',
    descricaoPadrao: 'A modalidade do título não é aceita pela política do fundo.',
    acaoRecomendada: 'Envie apenas modalidades aceitas pelo fundo, como duplicatas mercantis ou de serviço.',
    badgeVariant: 'warning',
  },
  CNPJ_SACADO_VALIDO: {
    titulo: 'CNPJ do Sacado Inválido',
    descricaoPadrao: 'O documento do sacado possui dígitos verificadores inconsistentes ou formatação inválida.',
    acaoRecomendada: 'Corrija o CNPJ do sacado na planilha de remessa e envie novamente.',
    badgeVariant: 'danger',
  },
  CONCENTRACAO_MAXIMA_SACADO: {
    titulo: 'Limite de Concentração por Raiz Excedido',
    descricaoPadrao: 'A exposição acumulada deste sacado (mesma raiz de 8 dígitos do CNPJ) ultrapassa o teto permitido da carteira do fundo.',
    acaoRecomendada: 'Reduza o volume alocado a esta mesma raiz de CNPJ para enquadramento na política do fundo.',
    badgeVariant: 'danger',
  },
  DUPLICIDADE_HISTORICA: {
    titulo: 'Título Já Presente no Estoque Histórico',
    descricaoPadrao: 'A chave global do título (cedente, sacado, documento e vencimento) coincide com título previamente adquirido na carteira do fundo.',
    acaoRecomendada: 'Verifique se este título já não foi antecipado ou registrado em operação anterior.',
    badgeVariant: 'danger',
  },
  DUPLICIDADE_LOTE: {
    titulo: 'Título Duplicado Dentro do Próprio Lote',
    descricaoPadrao: 'A mesma chave de recebível aparece repetida em mais de uma linha da remessa enviada.',
    acaoRecomendada: 'Remova a linha duplicada da planilha de remessa e reenvie o arquivo.',
    badgeVariant: 'danger',
  },

  // Regras adicionais ou inativas configuradas no fundo
  PRAZO_MINIMO: {
    titulo: 'Prazo Inferior ao Mínimo Permitido',
    descricaoPadrao: 'O prazo residual entre a data-base e o vencimento é inferior à carência mínima estipulada.',
    acaoRecomendada: 'Envie títulos com vencimento posterior à carência mínima estabelecida.',
    badgeVariant: 'warning',
  },
  CONCENTRACAO_MAXIMA_CEDENTE: {
    titulo: 'Limite de Concentração do Cedente Excedido',
    descricaoPadrao: 'A exposição do cedente excede o limite percentual permitido na carteira.',
    acaoRecomendada: 'Ajuste a carteira de recebíveis submetida para este cedente.',
    badgeVariant: 'danger',
  },
  CALCULO_FINANCEIRO_INVALIDO: {
    titulo: 'Cálculo Financeiro Resultou em Valor Inválido',
    descricaoPadrao: 'O cálculo de desconto comercial produziu valor líquido nulo ou negativo.',
    acaoRecomendada: 'Revise taxa, prazo e valor nominal do título submetido.',
    badgeVariant: 'danger',
  },

  // Capacidade numérica e limites técnicos do motor
  VALOR_EXCEDE_CAPACIDADE: {
    titulo: 'Valor Excede Capacidade Técnica do Sistema',
    descricaoPadrao: 'O valor nominal informado supera o limite máximo de precisão numérica suportado pelo sistema (R$ 9.999.999.999.999,99).',
    acaoRecomendada: 'Verifique a digitação do montante na planilha; títulos acima do teto de capacidade técnica não podem ser processados com exatidão.',
    badgeVariant: 'danger',
  },
  TOTAL_EXCEDE_CAPACIDADE: {
    titulo: 'Total excede a capacidade técnica do sistema',
    descricaoPadrao: 'O total nominal do lote ou o total líquido aprovado ultrapassa o limite de representação suportado.',
    acaoRecomendada: 'Submeta o lote fracionado em remessas menores para que os totalizadores possam ser apurados com exatidão.',
    badgeVariant: 'danger',
  },

  // Códigos de erro de ingestão e formatação
  CAMPOS_OBRIGATORIOS_VAZIOS: {
    titulo: 'Campos Obrigatórios em Branco',
    descricaoPadrao: 'A linha possui campos essenciais vazios necessários para a identificação e avaliação.',
    acaoRecomendada: 'Preencha todas as colunas obrigatórias da planilha antes do envio.',
    badgeVariant: 'danger',
  },
  FORMATO_INVALIDO_DOCUMENTO_SACADO: {
    titulo: 'Formato do Documento do Sacado Inválido',
    descricaoPadrao: 'O documento do sacado contém caracteres não permitidos ou tamanho divergente de CNPJ/CPF.',
    acaoRecomendada: 'Revise o preenchimento do documento do sacado na planilha.',
    badgeVariant: 'danger',
  },
  FORMATO_INVALIDO_DOCUMENTO_CEDENTE: {
    titulo: 'Formato do Documento do Cedente Inválido',
    descricaoPadrao: 'O documento do cedente contém caracteres inválidos ou formato incompatível.',
    acaoRecomendada: 'Revise o preenchimento do documento do cedente na planilha.',
    badgeVariant: 'danger',
  },
  FORMATO_INVALIDO_VALOR: {
    titulo: 'Formato do Valor Nominal Inválido',
    descricaoPadrao: 'O valor nominal possui formato não numérico ou casas decimais além de centavos.',
    acaoRecomendada: 'Informe valores com separador decimal correto (ex: 1500,00 ou 1500.00).',
    badgeVariant: 'danger',
  },
  FORMATO_INVALIDO_DATA_VENCIMENTO: {
    titulo: 'Data de Vencimento Inválida',
    descricaoPadrao: 'A data de vencimento não corresponde ao formato esperado (dd/mm/aaaa ou aaaa-mm-dd).',
    acaoRecomendada: 'Ajuste o formato da data de vencimento original.',
    badgeVariant: 'danger',
  },
  FORMATO_INVALIDO_DATA_AQUISICAO: {
    titulo: 'Data de Aquisição Inválida',
    descricaoPadrao: 'A data de aquisição informada está em formato incorreto.',
    acaoRecomendada: 'Corrija ou deixe em branco a data de aquisição.',
    badgeVariant: 'danger',
  },
  LINHA_MALFORMADA_COLUNAS: {
    titulo: 'Linha com Número Divergente de Colunas',
    descricaoPadrao: 'A linha possui quantidade de campos diferente dos 11 cabeçalhos definidos.',
    acaoRecomendada: 'Verifique se não há separadores de ponto e vírgula extras na linha.',
    badgeVariant: 'danger',
  },
  CABECALHO_INVALIDO: {
    titulo: 'Estrutura de Cabeçalho Inválida',
    descricaoPadrao: 'O arquivo enviado não possui os 11 cabeçalhos padronizados ou delimitador de ponto e vírgula.',
    acaoRecomendada: 'Baixe a planilha modelo de demonstração pelo link e alinhe as colunas antes de reenviar.',
    badgeVariant: 'danger',
  },
  FORMATO_ARQUIVO_INVALIDO: {
    titulo: 'Formato de Arquivo Inválido',
    descricaoPadrao: 'O arquivo enviado não é um arquivo CSV com codificação UTF-8 válido.',
    acaoRecomendada: 'Salve seu arquivo no formato CSV codificado em UTF-8.',
    badgeVariant: 'danger',
  },
};

export function obterExplicacaoRecusa(codigo: string, mensagemOriginal?: string): ExplicacaoRecusa {
  const config = codigo ? DICIONARIO_RECUSAS[codigo] : undefined;

  // PRIORIDADE: se o backend enviou mensagemOriginal com detalhes (ex: R$ 50.00 < R$ 100.00 ou 231 dias > 180 dias),
  // exibe essa mensagem rica diretamente para não perder números e diagnósticos auditáveis.
  const descricao =
    mensagemOriginal && mensagemOriginal.trim() !== ''
      ? mensagemOriginal.trim()
      : config
      ? config.descricaoPadrao
      : 'O recebível não atendeu a um ou mais critérios da política de risco do fundo.';

  if (config) {
    return {
      titulo: config.titulo,
      descricao,
      acaoRecomendada: config.acaoRecomendada,
      badgeVariant: config.badgeVariant,
    };
  }

  return {
    titulo: codigo ? `Recusa: ${codigo}` : 'Critério da Política do Fundo Não Atendido',
    descricao,
    acaoRecomendada: 'Consulte os parâmetros de validação ativos na política do fundo.',
    badgeVariant: 'warning',
  };
}
