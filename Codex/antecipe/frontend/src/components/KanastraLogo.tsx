import React from 'react';

interface LogoProps {
  size?: number;
  showText?: boolean;
  subtitle?: string;
}

/**
 * Marca institucional Antecipe (identidade visual moderna de antecipação de recebíveis)
 */
export const KanastraLogo: React.FC<LogoProps> = ({
  size = 30,
  showText = true,
  subtitle = 'Backoffice FIDC',
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
        <rect width="40" height="40" rx="8" fill="#059669" />
        <path d="M12 28L20 12L28 28H23L20 21L17 28H12Z" fill="#FFFFFF" />
        <circle cx="20" cy="17" r="2.5" fill="#A7F3D0" />
      </svg>

      {showText && (
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '10px' }}>
          <span
            style={{
              fontSize: '1.18rem',
              fontWeight: 800,
              letterSpacing: '-0.02em',
              color: '#f8fafc',
            }}
          >
            Antecipe
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

