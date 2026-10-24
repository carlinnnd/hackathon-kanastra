"""
Validação e normalização matemática de CNPJ (dígitos verificadores oficiais da Receita Federal).
Funções puras sem efeitos colaterais.
"""
import re
from typing import Optional, Tuple

# Padrão estrito de CNPJ: 14 dígitos puros ou formato XX.XXX.XXX/XXXX-XX
PADRAO_CNPJ_FORMATADO = re.compile(r"^\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}$")
PADRAO_CNPJ_NUMERICO = re.compile(r"^\d{14}$")


def normalizar_cnpj(cnpj: Optional[str]) -> Tuple[bool, str]:
    """
    Normaliza CNPJ e valida formato sintático.
    Rejeita textos com letras ou caracteres anômalos (não apaga letras silenciosamente).
    Retorna (valido_sintaticamente, numeros_14_digitos).
    """
    if not cnpj or not isinstance(cnpj, str):
        return False, ""
    
    texto = cnpj.strip()
    if not texto:
        return False, ""
        
    if PADRAO_CNPJ_NUMERICO.match(texto):
        return True, texto
        
    if PADRAO_CNPJ_FORMATADO.match(texto):
        numeros = re.sub(r"\D", "", texto)
        return True, numeros

    # Se contém letras ou pontuação fora do padrão oficial, rejeita sintaticamente
    return False, ""


def validar_cnpj(cnpj: str) -> bool:
    """
    Valida os dígitos verificadores de um CNPJ (14 dígitos numéricos).
    Rejeita tamanhos incorretos, formatos corrompidos ou sequências repetidas.
    """
    ok_formato, numeros = normalizar_cnpj(cnpj)
    if not ok_formato or len(numeros) != 14:
        return False
    
    # Rejeitar se todos os dígitos forem iguais
    if numeros == numeros[0] * 14:
        return False
    
    # Primeiro dígito verificador
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma1 = sum(int(n) * p for n, p in zip(numeros[:12], pesos1))
    resto1 = soma1 % 11
    dv1 = 0 if resto1 < 2 else 11 - resto1
    
    if int(numeros[12]) != dv1:
        return False
        
    # Segundo dígito verificador
    pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma2 = sum(int(n) * p for n, p in zip(numeros[:13], pesos2))
    resto2 = soma2 % 11
    dv2 = 0 if resto2 < 2 else 11 - resto2
    
    return int(numeros[13]) == dv2
