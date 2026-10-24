import React, { useRef, useState } from 'react';
import { UploadCloud, FileText, Download, AlertCircle } from 'lucide-react';
import { api } from '../services/api';

interface FileUploadProps {
  onFileSelected: (file: File) => void;
  isLoading: boolean;
  disabled?: boolean;
}

export const FileUpload: React.FC<FileUploadProps> = ({
  onFileSelected,
  isLoading,
  disabled = false,
}) => {
  const [isDragActive, setIsDragActive] = useState(false);
  const [selectedFileName, setSelectedFileName] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const validateAndProcessFile = (file: File | undefined) => {
    if (!file) return;

    // Validação case-insensitive da extensão .csv
    const isCsv = file.name.toLowerCase().endsWith('.csv');
    if (!isCsv) {
      setValidationError('Por favor, selecione um arquivo no formato CSV (.csv).');
      setSelectedFileName(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
      return;
    }

    setValidationError(null);
    setSelectedFileName(file.name);
    onFileSelected(file);

    // Permite reenviar o mesmo arquivo selecionando novamente
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
        Área de envio de lote de recebíveis
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
              Arquivo: <strong>{selectedFileName}</strong>
            </span>
          ) : (
            'Arraste e solte o arquivo CSV ou clique no botão abaixo'
          )}
        </div>

        <p className="upload-subtext">
          Formato CSV delimitado por ponto e vírgula (;), codificação UTF-8 com os 11 cabeçalhos
          requeridos. O motor processará a simulação de elegibilidade de ponta a ponta.
        </p>

        <div className="upload-actions">
          <button
            type="button"
            className="btn-primary"
            onClick={handleTriggerInput}
            disabled={disabled || isLoading}
            aria-label="Abrir seletor de arquivos CSV"
          >
            <FileText size={16} aria-hidden="true" />
            <span>{selectedFileName ? 'Trocar arquivo' : 'Selecionar arquivo CSV'}</span>
          </button>

          <a
            href={api.getDemoCsvUrl()}
            download="demo_recebiveis.csv"
            className="btn-secondary"
            aria-label="Baixar planilha de demonstração sintética com exemplos de aprovação e recusa"
          >
            <Download size={16} aria-hidden="true" />
            <span>Baixar CSV de demonstração</span>
          </a>
        </div>
      </div>
    </section>
  );
};
