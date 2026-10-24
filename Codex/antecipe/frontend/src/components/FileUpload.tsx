import React, { useRef, useState } from 'react';
import { UploadCloud, FileText, Download, AlertCircle } from 'lucide-react';
import { api } from '../services/api';

interface FileUploadProps {
  onFileSelected: (file: File) => void;
  onSimulateSampleBatch?: (rows: 100 | 1000 | 10000 | 100000) => void;
  isLoading: boolean;
  disabled?: boolean;
}

const LOTES_HOMOLOGACAO: Array<{ rows: 100 | 1000 | 10000 | 100000; label: string; slug: string }> = [
  { rows: 100, label: 'Remessa Compacta', slug: 'lote_compacto.csv' },
  { rows: 1000, label: 'Remessa Padrão', slug: 'lote_padrao.csv' },
  { rows: 10000, label: 'Remessa Corporativa', slug: 'lote_corporativo.csv' },
  { rows: 100000, label: 'Remessa Massiva', slug: 'lote_massivo.csv' },
];

export const FileUpload: React.FC<FileUploadProps> = ({
  onFileSelected,
  onSimulateSampleBatch,
  isLoading,
  disabled = false,
}) => {
  const [isDragActive, setIsDragActive] = useState(false);
  const [selectedFileName, setSelectedFileName] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const validateAndProcessFile = (file: File | undefined) => {
    if (!file) return;

    const isCsv = file.name.toLowerCase().endsWith('.csv');
    if (!isCsv) {
      setValidationError('Selecione um arquivo válido no formato CSV (.csv).');
      setSelectedFileName(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
      return;
    }

    setValidationError(null);
    setSelectedFileName(file.name);
    onFileSelected(file);

    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    if (!disabled && !isLoading) {
      setIsDragActive(true);
    }
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragActive(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragActive(false);
    if (disabled || isLoading) return;

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      validateAndProcessFile(e.dataTransfer.files[0]);
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      validateAndProcessFile(e.target.files[0]);
    }
  };

  const handleTriggerInput = () => {
    if (!disabled && !isLoading && fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  return (
    <section aria-labelledby="upload-section-title">
      <h2 id="upload-section-title" className="sr-only">
        Importação de remessa de recebíveis
      </h2>

      {validationError && (
        <div
          className="error-toast"
          role="alert"
          aria-live="assertive"
          style={{ marginBottom: '16px' }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <AlertCircle size={18} aria-hidden="true" />
            <span>{validationError}</span>
          </div>
          <button
            type="button"
            className="btn-secondary"
            onClick={() => setValidationError(null)}
            style={{ padding: '2px 8px', fontSize: '0.75rem' }}
            aria-label="Fechar alerta de validação"
          >
            Fechar
          </button>
        </div>
      )}

      <div
        className={`upload-card ${isDragActive ? 'drag-active' : ''}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        style={{ cursor: disabled || isLoading ? 'not-allowed' : 'default' }}
      >
        <input
          type="file"
          id="csv-file-input"
          ref={fileInputRef}
          onChange={handleInputChange}
          accept=".csv,text/csv"
          className="sr-only"
          disabled={disabled || isLoading}
          aria-label="Selecionar arquivo CSV de recebíveis"
        />

        <UploadCloud className="upload-icon" aria-hidden="true" />

        <div className="upload-heading">
          {selectedFileName ? (
            <span style={{ color: 'var(--text-primary)' }}>
              Remessa selecionada: <strong>{selectedFileName}</strong>
            </span>
          ) : (
            'Importar arquivo de remessa CSV'
          )}
        </div>

        <p className="upload-subtext">
          Arraste o arquivo delimitado por ponto e vírgula ou selecione a planilha no seu
          computador para iniciar a verificação de enquadramento.
        </p>

        <div className="upload-actions">
          <button
            type="button"
            className="btn-primary"
            onClick={handleTriggerInput}
            disabled={disabled || isLoading}
            aria-label="Abrir seletor de arquivos CSV"
          >
            <FileText size={15} aria-hidden="true" />
            <span>{selectedFileName ? 'Substituir arquivo CSV' : 'Selecionar arquivo CSV'}</span>
          </button>

          <a
            href={api.getDemoCsvUrl()}
            download="modelo_remessa_antecipe.csv"
            className="btn-secondary"
            aria-label="Baixar planilha modelo de demonstração"
          >
            <Download size={15} aria-hidden="true" />
            <span>Baixar planilha modelo</span>
          </a>
        </div>

        {onSimulateSampleBatch && (
          <div className="upload-homologation-bar">
            <span className="upload-homologation-label">Bases de homologação:</span>

            <div className="upload-homologation-actions">
              {LOTES_HOMOLOGACAO.map((item) => (
                <div key={item.rows} className="upload-homologation-item">
                  <button
                    type="button"
                    className="btn-secondary"
                    style={{ padding: '6px 12px', fontSize: '0.76rem' }}
                    disabled={disabled || isLoading}
                    onClick={() => {
                      setSelectedFileName(item.slug);
                      onSimulateSampleBatch(item.rows);
                    }}
                  >
                    <span>{item.label}</span>
                  </button>
                  <a
                    href={api.getSampleCsvUrl(item.rows)}
                    download={item.slug}
                    className="upload-homologation-dl"
                    title={`Baixar ${item.slug}`}
                  >
                    CSV
                  </a>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  );
};

