"""Confronto integral: gabarito recebido, mock e motor atual. Não usa rótulos como cadastro."""
import csv
import hashlib
import json
import sys
from collections import Counter
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[1]
sys.path.insert(0, str(PROJECT))
from backend.config import settings
from backend.application.cadastral_service import carregar_cadastro
from backend.api.bulk_routes import criar_sessao_isolada_para_conexao
from backend.infrastructure.repositories.receivables_repository import ReceivablesRepository
from backend.domain.engine import MotorAvaliacao, carregar_configuracao
from backend.domain.ingestion import parse_linha_csv
from backend.domain.models import EstadoProjetadoLote


def comparar():
    source = ROOT / 'estoque_antecipe_100k/estoque_antecipe.csv'
    expected_path = ROOT / 'resultado_esperado_100k.json'
    mock_path = PROJECT / 'data/cnpj_situacao_mock.csv'
    cfg_path = ROOT / 'validadores_antecipe.json'
    expected = json.loads(expected_path.read_text(encoding='utf-8'))
    by_line = {e['linha']: e for e in expected}
    assert len(expected) == len(by_line), 'Linhas duplicadas no gabarito'
    settings.ENABLE_DEMO_CADASTRO = True
    settings.PUBLIC_DEMO_MODE = True
    settings.CADASTRO_MOCK_PATH = str(mock_path)
    cad, fonte = carregar_cadastro()
    cfg = carregar_configuracao(json.loads(cfg_path.read_text(encoding='utf-8'), parse_float=Decimal))
    db, engine = criar_sessao_isolada_para_conexao()
    from backend.infrastructure.database.models import FundModel
    fund = db.query(FundModel).filter(FundModel.nome.ilike('%ANTECIPE%')).first()
    snapshot = ReceivablesRepository(db).carregar_snapshot_carteira(fund.id, chaves_candidatas=None)
    state = EstadoProjetadoLote(snapshot.total_nominal, dict(snapshot.exposicoes_sacado_raiz), dict(snapshot.exposicoes_cedente))
    motor = MotorAvaliacao(cfg)
    combos, coverage, actual, expected_counts, motives = Counter(), Counter(), Counter(), Counter(), Counter()
    contradictions = Counter()
    exact_status = exact_motives = count = 0
    output = PROJECT / '.data/gabarito-conference'
    output.mkdir(parents=True, exist_ok=True)
    with source.open(encoding='utf-8-sig', newline='') as stream, (output/'divergencias.csv').open('w',encoding='utf-8-sig',newline='') as out:
        writer = csv.writer(out, delimiter=';')
        writer.writerow(['linha','documento','status_gabarito','status_motor_atual','motivos_gabarito','motivos_motor'])
        for line, row in enumerate(csv.DictReader(stream, delimiter=';'), 2):
            count += 1
            reference = by_line[line]
            assert str(reference['id']).strip() == row['NU_DOCUMENTO'].strip(), 'Documento/linha divergentes'
            item, erro = parse_linha_csv(line,row)
            result = erro or motor.avaliar_recebivel(item,cad,state,snapshot)
            codes = [m.codigo for m in result.motivos]
            for c in codes: motives[c] += 1
            normalized = 'APROVADO' if result.aprovado else 'BARRADO' if result.status == 'RECUSADA' else result.status
            actual[result.status] += 1; expected_counts[reference['status']] += 1
            combos[f"{reference['status']} -> {result.status}"] += 1
            same_status = normalized == reference['status']
            same_motives = sorted(codes) == sorted(reference.get('barrado_por', []))
            exact_status += same_status; exact_motives += same_motives
            doc = item.doc_sacado if item else ''
            situacao = cad.get(doc,'NAO_VERIFICADA')
            coverage[situacao] += 1
            blocked_cadastro = 'SITUACAO_CADASTRAL_SACADO' in reference.get('barrado_por',[])
            if situacao == 'ATIVA' and blocked_cadastro: contradictions['cadastro_ativo_no_mock_mas_barrado_no_gabarito'] += 1
            if situacao not in {'ATIVA','NAO_VERIFICADA'} and not blocked_cadastro: contradictions['cadastro_nao_ativo_mock_sem_motivo_no_gabarito'] += 1
            if situacao == 'NAO_VERIFICADA' and reference['status']=='APROVADO': contradictions['aprovado_gabarito_sem_cadastro_mock'] += 1
            if not same_status or not same_motives:
                from backend.application.exports import csv_safe
                writer.writerow([csv_safe(v) for v in [line,row['NU_DOCUMENTO'],reference['status'],result.status,' | '.join(reference.get('barrado_por',[])),' | '.join(codes)]])
    assert count == len(expected)
    db.close();engine.dispose()
    result = {
        'executado_utc': datetime.now(timezone.utc).isoformat(),
        'fontes_sha256': {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [source,expected_path,mock_path,cfg_path]},
        'linhas_e_documentos_conferidos': count, 'gabarito_status': dict(expected_counts),
        'motor_atual_status': dict(actual), 'concordancia_status': exact_status,
        'concordancia_todos_motivos': exact_motives, 'matriz_comparacao': dict(combos),
        'cadastro_cobertura_registros': dict(coverage), 'conflitos_fontes': dict(contradictions),
        'motivos_motor_atual':dict(motives), 'cadastro_fonte':fonte,
        'escopo': 'Motor de novas operações contra seed público de 5 títulos, data-base JSON/22-10-2026. Não é reclassificação do histórico nem comparação de valores financeiros ausentes no gabarito.',
        'criterio_pendencia': 'Cadastro ausente não aprova; pendente se nenhuma violação confirmada, recusada se houver outra violação confirmada.',
        'reconciliacao': 'Gabarito e mock têm contradições verificadas. Os rótulos não são usados para inferir cadastro ou alterar regras. Correspondência integral exige resolver esses conflitos e alinhar cenário/carteira/data-base.',
        'detalhamento_privado': str(output/'divergencias.csv'),
    }
    (PROJECT/'qa/relatorio_gabarito_mock.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__ == '__main__': comparar()
