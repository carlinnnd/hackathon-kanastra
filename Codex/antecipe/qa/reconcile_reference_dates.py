"""Reproduce date-only reference projection and full engine decisions separately."""
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
from backend.infrastructure.database.models import FundModel
from backend.infrastructure.repositories.receivables_repository import ReceivablesRepository
from backend.domain.engine import MotorAvaliacao, carregar_configuracao
from backend.domain.ingestion import parse_linha_csv
from backend.domain.models import EstadoProjetadoLote


def main():
    source = ROOT / 'estoque_antecipe_100k/estoque_antecipe.csv'
    reference_path = ROOT / 'resultado_esperado_100k.json'
    mock = ROOT / 'cnpj_situacao_mock.csv'
    rules = ROOT / 'validadores_antecipe.json'
    expected = json.loads(reference_path.read_text(encoding='utf-8-sig'))
    reference = {entry['linha']: entry for entry in expected}
    assert len(expected) == len(reference)
    settings.PUBLIC_DEMO_MODE = True
    settings.ENABLE_DEMO_CADASTRO = True
    settings.CADASTRO_MOCK_PATH = str(mock)
    cadastro, _ = carregar_cadastro()
    raw_config = json.loads(rules.read_text(encoding='utf-8-sig'), parse_float=Decimal)
    db, engine = criar_sessao_isolada_para_conexao()
    try:
        fund = db.query(FundModel).filter(FundModel.nome.ilike('%ANTECIPE%')).first()
        snapshot = ReceivablesRepository(db).carregar_snapshot_carteira(fund.id, chaves_candidatas=None)
        scenarios = {}
        for day in (date(2026, 10, 22), date(2026, 10, 24)):
            motor = MotorAvaliacao(carregar_configuracao(raw_config, day))
            state = EstadoProjetadoLote(snapshot.total_nominal, dict(snapshot.exposicoes_sacado_raiz), dict(snapshot.exposicoes_cedente))
            counts, motives, coverage = Counter(), Counter(), Counter()
            liquid = Decimal('0')
            projection_approved = lost_to_expiry = total = 0
            with source.open(encoding='utf-8-sig', newline='') as stream:
                for line, row in enumerate(csv.DictReader(stream, delimiter=';'), 2):
                    entry = reference[line]
                    assert str(entry['id']).strip() == row['NU_DOCUMENTO'].strip()
                    item, error = parse_linha_csv(line, row)
                    assert item is not None and error is None
                    total += 1
                    was_approved = entry['status'] == 'APROVADO'
                    expired = item.data_vencimento < day
                    projection_approved += int(was_approved and not expired)
                    lost_to_expiry += int(was_approved and expired)
                    coverage[cadastro.get(item.doc_sacado, 'NAO_VERIFICADA')] += 1
                    result = motor.avaliar_recebivel(item, cadastro, state, snapshot)
                    counts[result.status] += 1
                    motives.update(reason.codigo for reason in result.motivos)
                    if result.aprovado:
                        liquid += result.valor_liquido
            assert total == len(expected) == sum(counts.values())
            scenarios[day.isoformat()] = {
                'motor': dict(counts), 'liquido_motor': str(liquid),
                'motivos_sobrepostos': dict(motives), 'cobertura_cadastral': dict(coverage),
                'projecao_gabarito_so_vencimento': {
                    'APROVADA': projection_approved, 'RECUSADA': total - projection_approved,
                    'aprovadas_gabarito_agora_vencidas': lost_to_expiry,
                },
            }
        report = {
            'executado_utc': datetime.now(timezone.utc).isoformat(),
            'fontes_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (source, reference_path, mock, rules)},
            'gabarito_original': dict(Counter(e['status'] for e in expected)),
            'cenario_motor': 'Novas operacoes contra seed publico; mock fornecido; regras completas.',
            'cenario_projecao': 'Preserva recusas do gabarito e recusa aprovadas cujo vencimento e anterior a data. Nao recalcula demais regras nem preco.',
            'datas': scenarios,
        }
        output = PROJECT / 'qa/relatorio_reconciliacao_datas.json'
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        db.close()
        engine.dispose()


if __name__ == '__main__':
    main()
