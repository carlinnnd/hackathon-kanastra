import React from 'react';

interface KanastraLogoProps {
  size?: number;
  showText?: boolean;
  subtitle?: string;
}

/**
 * Marca institucional Kanastra (símbolo geométrico modular em camadas + tipografia limpa)
 */
export const KanastraLogo: React.FC<KanastraLogoProps> = ({
  size = 30,
  showText = true,
  subtitle = 'Antecipe FIDC',
}) => {
  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: '10px' }}>
      <svg
        width={size}
        height={size}
        viewBox="0 0 40 40"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
        style={{
          borderRadius: '7px',
          flexShrink: 0,
        }}
      >
        <rect width="40" height="40" rx="8" fill="#14735A" />
        <rect x="9" y="9" width="10" height="22" rx="1.8" fill="#FFFFFF" />
        <rect x="21.5" y="9" width="9.5" height="9.5" rx="1.8" fill="#A7F3D0" />
        <rect x="21.5" y="21.5" width="9.5" height="9.5" rx="1.8" fill="#FFFFFF" />
      </svg>

      {showText && (
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '10px' }}>
          <span
            style={{
              fontSize: '1.15rem',
              fontWeight: 700,
              letterSpacing: '-0.03em',
              color: '#f8fafc',
            }}
          >
            kanastra
          </span>
          {subtitle && (
            <>
              <span
                style={{
                  width: '1px',
                  height: '16px',
                  backgroundColor: 'var(--border-subtle)',
                }}
                aria-hidden="true"
              />
              <span
                style={{
                  fontSize: '0.82rem',
                  fontWeight: 500,
                  color: 'var(--text-secondary)',
                }}
              >
                {subtitle}
              </span>
            </>
          )}
        </div>
      )}
    </div>
  );
};
