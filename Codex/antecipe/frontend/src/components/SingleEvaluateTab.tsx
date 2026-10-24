import React, { useRef, useState } from 'react';
import {
  FileCode2,
  Send,
  CheckCircle2,
  XCircle,
} from 'lucide-react';
import { SimulationEnvelope, SingleReceivableInput } from '../types';
import { api } from '../services/api';
import { formatarMoedaBRL } from '../services/currency';
import { obterExplicacaoRecusa } from '../services/rejections';
import { EconomicGroupCard } from './EconomicGroupCard';

export const SingleEvaluateTab: React.FC = () => {
  const [form, setForm] = useState<SingleReceivableInput>({
    NOME_FUNDO: 'ANTECIPE FIDC',
    DOC_FUNDO: '92.234.400/0001-80',
    NOME_CEDENTE: '',
    DOC_CEDENTE: '',
    NOME_SACADO: '',
    DOC_SACADO: '',
    NU_DOCUMENTO: '',
    TIPO_RECEBIVEL: '',
    VALOR_NOMINAL: '',
    DATA_VENCIMENTO_ORIGINAL: '',
  });

  const [xmlNotice, setXmlNotice] = useState<string | null>(null);
  const [result, setResult] = useState<SimulationEnvelope | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const xmlInputRef = useRef<HTMLInputElement | null>(null);

  const handleXmlUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    setXmlNotice(null);
    try {
      const text = await file.text();
      const getTag = (tag: string): string => {
        const match = text.match(new RegExp(`<${tag}>([^<]+)</${tag}>`, 'i'));
        return match ? match[1].trim() : '';
      };
      const nNF = getTag('nNF');
      const vNF = getTag('vNF').replace('.', ',');
      const dVencIso = getTag('dVenc');
      if (!nNF || !vNF || !dVencIso) throw new Error('XML incompleto');
      const dVencBr = dVencIso.includes('-')
        ? dVencIso.split('-').reverse().join('/')
        : dVencIso;

      setForm((prev) => ({
        ...prev,
        NU_DOCUMENTO: `NFE-${nNF}`,
        VALOR_NOMINAL: vNF,
        DATA_VENCIMENTO_ORIGINAL: dVencBr,
      }));
      setXmlNotice(`Arquivo XML (${file.name}) importado com sucesso.`);
    } catch {
      setError('XML incompleto ou inválido. Confira número, valor e vencimento do título.');
    }
  };

  const handleEvaluate = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await api.evaluateSingleReceivable(form);
      setResult(res);
    } catch (err: unknown) {
      if (err instanceof Error) setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const itemResultado = result?.resultados?.[0] || null;
  const motivoConcentracao = itemResultado?.motivos?.find(
    (m) => m.codigo === 'CONCENTRACAO_MAXIMA_SACADO'
  );

  return (
    <section aria-labelledby="single-eval-title">
      <div className="table-section" style={{ padding: '24px', marginBottom: '24px' }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            flexWrap: 'wrap',
            gap: '16px',
            marginBottom: '20px',
            paddingBottom: '16px',
            borderBottom: '1px solid var(--border-subtle)',
          }}
        >
          <div>
            <h2
              id="single-eval-title"
              style={{
                fontSize: '1.05rem',
                fontWeight: 600,
                color: 'var(--text-primary)',
              }}
            >
              Consulta de Enquadramento e Cálculo de Deságio
            </h2>
            <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginTop: 2 }}>
              Preencha os dados do título comercial ou importe o XML da Nota Fiscal para simular a
              aquisição individual.
            </p>
          </div>

          <div>
            <input
              ref={xmlInputRef}
              type="file"
              accept=".xml,text/xml"
              className="sr-only"
              onChange={handleXmlUpload}
              aria-label="Importar arquivo XML de Nota Fiscal Eletrônica"
            />
            <button
              type="button"
              className="btn-secondary"
              onClick={() => xmlInputRef.current?.click()}
            >
              <FileCode2 size={15} aria-hidden="true" />
              <span>Importar XML NF-e</span>
            </button>
          </div>
        </div>

        {xmlNotice && (
          <div
            style={{
              marginBottom: '16px',
              fontSize: '0.8125rem',
              color: '#6ee7b7',
              backgroundColor: 'var(--status-success-bg)',
              border: '1px solid var(--status-success-border)',
              borderRadius: 'var(--radius-sm)',
              padding: '8px 12px',
            }}
          >
            {xmlNotice}
          </div>
        )}

        {error && (
          <div className="error-toast" role="alert">
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleEvaluate}>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
              gap: '14px',
              marginBottom: '20px',
            }}
          >
            <div>
              <label
                style={{
                  display: 'block',
                  fontSize: '0.75rem',
                  color: 'var(--text-secondary)',
                  marginBottom: 4,
                  fontWeight: 500,
                }}
              >
                Razão Social do Cedente
              </label>
              <input
                type="text"
                className="select-control"
                style={{ width: '100%' }}
                value={form.NOME_CEDENTE}
                onChange={(e) => setForm({ ...form, NOME_CEDENTE: e.target.value })}
                required
              />
            </div>

            <div>
              <label
                style={{
                  display: 'block',
                  fontSize: '0.75rem',
                  color: 'var(--text-secondary)',
                  marginBottom: 4,
                  fontWeight: 500,
                }}
              >
                CNPJ do Cedente
              </label>
              <input
                type="text"
                className="select-control"
                style={{ width: '100%', fontFamily: 'var(--font-mono)' }}
                value={form.DOC_CEDENTE}
                onChange={(e) => setForm({ ...form, DOC_CEDENTE: e.target.value })}
                required
              />
            </div>

            <div>
              <label
                style={{
                  display: 'block',
                  fontSize: '0.75rem',
                  color: 'var(--text-secondary)',
                  marginBottom: 4,
                  fontWeight: 500,
                }}
              >
                Razão Social do Sacado
              </label>
              <input
                type="text"
                className="select-control"
                style={{ width: '100%' }}
                value={form.NOME_SACADO}
                onChange={(e) => setForm({ ...form, NOME_SACADO: e.target.value })}
                required
              />
            </div>

            <div>
              <label
                style={{
                  display: 'block',
                  fontSize: '0.75rem',
                  color: 'var(--text-secondary)',
                  marginBottom: 4,
                  fontWeight: 500,
                }}
              >
                CNPJ do Sacado
              </label>
              <input
                type="text"
                className="select-control"
                style={{ width: '100%', fontFamily: 'var(--font-mono)' }}
                value={form.DOC_SACADO}
                onChange={(e) => setForm({ ...form, DOC_SACADO: e.target.value })}
                required
              />
            </div>

            <div>
              <label
                style={{
                  display: 'block',
                  fontSize: '0.75rem',
                  color: 'var(--text-secondary)',
                  marginBottom: 4,
                  fontWeight: 500,
                }}
              >
                Número do Documento
              </label>
              <input
                type="text"
                className="select-control"
                style={{ width: '100%', fontFamily: 'var(--font-mono)' }}
                value={form.NU_DOCUMENTO}
                onChange={(e) => setForm({ ...form, NU_DOCUMENTO: e.target.value })}
                required
              />
            </div>

            <div>
              <label
                style={{
                  display: 'block',
                  fontSize: '0.75rem',
                  color: 'var(--text-secondary)',
                  marginBottom: 4,
                  fontWeight: 500,
                }}
              >
                Modalidade do Recebível
              </label>
              <select
                className="select-control"
                style={{ width: '100%' }}
                value={form.TIPO_RECEBIVEL}
                onChange={(e) => setForm({ ...form, TIPO_RECEBIVEL: e.target.value })}
              >
                <option value="" disabled>Selecione a modalidade</option>
                <option value="Duplicata">Duplicata</option>
                <option value="Duplicata de Serviço">Duplicata de Serviço</option>
                <option value="Cheque">Cheque</option>
                <option value="CCB">CCB</option>
                <option value="Nota Comercial">Nota Comercial</option>
              </select>
            </div>

            <div>
              <label
                style={{
                  display: 'block',
                  fontSize: '0.75rem',
                  color: 'var(--text-secondary)',
                  marginBottom: 4,
                  fontWeight: 500,
                }}
              >
                Valor Nominal
              </label>
              <input
                type="text"
                className="select-control"
                style={{ width: '100%', fontFamily: 'var(--font-mono)' }}
                value={form.VALOR_NOMINAL}
                onChange={(e) => setForm({ ...form, VALOR_NOMINAL: e.target.value })}
                required
              />
            </div>

            <div>
              <label
                style={{
                  display: 'block',
                  fontSize: '0.75rem',
                  color: 'var(--text-secondary)',
                  marginBottom: 4,
                  fontWeight: 500,
                }}
              >
                Data de Vencimento
              </label>
              <input
                type="text"
                className="select-control"
                style={{ width: '100%', fontFamily: 'var(--font-mono)' }}
                value={form.DATA_VENCIMENTO_ORIGINAL}
                onChange={(e) => setForm({ ...form, DATA_VENCIMENTO_ORIGINAL: e.target.value })}
                required
              />
            </div>
          </div>

          <button type="submit" className="btn-primary" disabled={loading}>
            <Send size={15} aria-hidden="true" />
            <span>{loading ? 'Validando...' : 'Avaliar Recebível'}</span>
          </button>
        </form>
      </div>

      {/* Resultado da Avaliação Síncrona */}
      {itemResultado && (
        <div
          className="table-section"
          style={{
            padding: '22px',
            borderLeft: itemResultado.aprovado ? '4px solid #10b981' : '4px solid #ef4444',
          }}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: 12,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              {itemResultado.aprovado ? (
                <CheckCircle2 size={24} color="#10b981" />
              ) : (
                <XCircle size={24} color="#ef4444" />
              )}
              <div>
                <h3 style={{ fontSize: '1.05rem', fontWeight: 600 }}>
                  Documento {itemResultado.documento} —{' '}
                  {itemResultado.aprovado
                    ? 'Elegível para Aquisição'
                    : 'Recusado pela Política do Fundo'}
                </h3>
                <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                  Sacado: {itemResultado.sacado}
                </p>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '24px', fontFamily: 'var(--font-mono)' }}>
              <div>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
                  VALOR NOMINAL
                </div>
                <strong style={{ fontSize: '1.1rem' }}>
                  {formatarMoedaBRL(itemResultado.valor_nominal)}
                </strong>
              </div>
              <div>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
                  VALOR LÍQUIDO DE CESSÃO
                </div>
                <strong
                  style={{
                    fontSize: '1.1rem',
                    color: itemResultado.aprovado ? '#34d399' : 'var(--text-muted)',
                  }}
                >
                  {itemResultado.aprovado ? formatarMoedaBRL(itemResultado.valor_liquido) : '—'}
                </strong>
              </div>
            </div>
          </div>

          {!itemResultado.aprovado && itemResultado.motivos.length > 0 && (
            <div className="rejection-details" style={{ marginTop: '16px' }}>
              {itemResultado.motivos.map((m, idx) => {
                const exp = obterExplicacaoRecusa(m.codigo, m.mensagem);
                return (
                  <div
                    key={idx}
                    style={{ marginBottom: idx < itemResultado.motivos.length - 1 ? 10 : 0 }}
                  >
                    <div className="rejection-details-title">
                      {exp.titulo} [{m.codigo}]
                    </div>
                    <div className="rejection-details-desc">{exp.descricao}</div>
                    <div className="rejection-details-action">
                      Recomendação: {exp.acaoRecomendada}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {motivoConcentracao && (
            <EconomicGroupCard
              raizCnpj={String(
                motivoConcentracao.dados?.raiz_cnpj ||
                  form.DOC_SACADO.replace(/\D/g, '').slice(0, 8)
              )}
              dadosMotivo={motivoConcentracao.dados}
            />
          )}
        </div>
      )}
    </section>
  );
};
