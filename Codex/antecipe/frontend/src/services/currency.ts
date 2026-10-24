/**
 * Formatação exata de moeda BRL para strings decimais (Numeric(18,2)).
 * NUNCA utiliza parseFloat ou Number para valores financeiros, prevenindo
 * perda de precisão e arredondamento espúrio de centavos em números altos.
 */

export function formatarMoedaBRL(valStr: string | null | undefined): string {
  if (valStr === null || valStr === undefined) return 'R$ 0,00';
  const trimmed = String(valStr).trim();
  if (!trimmed || trimmed === '—' || trimmed === 'null' || trimmed === 'undefined') {
    return 'R$ 0,00';
  }

  // Normaliza sinal e separadores
  let negativo = false;
  let s = trimmed;

  if (s.startsWith('-')) {
    negativo = true;
    s = s.slice(1).trim();
  } else if (s.startsWith('+')) {
    s = s.slice(1).trim();
  }

  // Suporta formatos: "12345.67", "12.345,67", "12345,67", "12345"
  let parteInteiraStr = '';
  let parteDecimalStr = '';

  if (s.includes(',')) {
    // Ex: "1.234.567,89" ou "1234,56"
    const semPontoMilhar = s.replace(/\./g, '');
    const partes = semPontoMilhar.split(',');
    parteInteiraStr = partes[0].replace(/\D/g, '');
    parteDecimalStr = (partes[1] || '').replace(/\D/g, '');
  } else if (s.includes('.')) {
    // Ex: "1234567.89"
    const partes = s.split('.');
    parteInteiraStr = partes[0].replace(/\D/g, '');
    parteDecimalStr = (partes[1] || '').replace(/\D/g, '');
  } else {
    // Inteiro puro
    parteInteiraStr = s.replace(/\D/g, '');
    parteDecimalStr = '';
  }

  // Centavos: exatamente 2 dígitos sem perda
  let centavos = parteDecimalStr.slice(0, 2);
  while (centavos.length < 2) {
    centavos += '0';
  }

  // Inteiro: BigInt para suportar qualquer tamanho arbitrário (ex: Numeric(18,2))
  let inteiroBig: bigint;
  try {
    inteiroBig = parteInteiraStr ? BigInt(parteInteiraStr) : 0n;
  } catch {
    return 'R$ 0,00';
  }

  // Formata os milhares com separador ponto (.)
  const inteiroFormatado = inteiroBig.toLocaleString('pt-BR');

  const resultado = `R$ ${inteiroFormatado},${centavos}`;
  return negativo && (inteiroBig > 0n || centavos !== '00') ? `-${resultado}` : resultado;
}
