"""Virada do dia, paridade das entradas e auditoria de simulacoes anteriores."""
import csv
import io
import json
from datetime import date, datetime, timezone

import pytest
from backend.domain import calendar
from backend.domain.calendar import data_atual as real_data_atual
from backend.tests.test_result_reporting import isolated, lote, upload
from backend.infrastructure.database.models import RuleVersionModel


@pytest.mark.parametrize('instant,expected', [
    ('2026-10-25T02:59:59+00:00', date(2026, 10, 24)),
    ('2026-10-25T03:00:00+00:00', date(2026, 10, 25)),
])
def test_virada_em_brasilia_e_nao_utc(monkeypatch, instant, expected):
    class Clock:
        @staticmethod
        def now(tz):
            return datetime.fromisoformat(instant).astimezone(tz)
    monkeypatch.setattr(calendar, 'datetime', Clock)
    assert real_data_atual() == expected


def test_csv_json_dia_seguinte_e_auditoria_congelada(isolated, monkeypatch):
    db, client, _ = isolated
    current = [date(2026, 10, 24)]
    monkeypatch.setattr(calendar, 'data_atual', lambda: current[0])
    # Nem uma data fixa na configuracao pode congelar novas operacoes.
    version = db.query(RuleVersionModel).first()
    cfg = json.loads(version.configuration_json)
    cfg['data_base'] = '2026-10-22'
    version.configuration_json = json.dumps(cfg)
    db.commit()
    text = lote([{'DATA_VENCIMENTO_ORIGINAL': '24/10/2026'}])
    rows = list(csv.DictReader(io.StringIO(text), delimiter=';'))
    for day, approved in [(date(2026, 10, 24), 1), (date(2026, 10, 25), 0)]:
        current[0] = day
        health = client.get('/api/health')
        assert health.json()['data_base_atual'] == day.isoformat()
        assert health.headers['cache-control'] == 'no-store'
        result = upload(client, text)
        api = client.post('/api/receivables/evaluate', json={'recebiveis': rows})
        assert api.status_code == 200
        assert result['data_base'] == api.json()['data_base'] == day.isoformat()
        assert result['aprovados'] == api.json()['aprovados'] == approved
        if approved:
            original = result
        else:
            assert 'NAO_VENCIDA' in [m['codigo'] for m in result['resultados'][0]['motivos']]
    saved = client.get('/api/simulations/' + original['simulation_id']).json()
    assert saved['data_base'] == '2026-10-24'
    assert saved['aprovados'] == 1
    exported = client.get('/api/simulations/' + original['simulation_id'] + '/export?format=csv')
    assert '24/10/2026' in exported.content.decode('utf-8-sig')
    rejected_override = client.post('/api/receivables/evaluate', json={'recebiveis': rows, 'data_base': '2026-10-22'})
    assert rejected_override.status_code == 422


def test_websocket_usa_dia_atual(isolated, monkeypatch):
    _, client, _ = isolated
    monkeypatch.setattr(calendar, 'data_atual', lambda: date(2026, 10, 25))
    text = lote([{'DATA_VENCIMENTO_ORIGINAL': '24/10/2026'}]).encode()
    with client.websocket_connect('/api/simulations/stream') as ws:
        ws.send_json({'type': 'start', 'filename': 'lote.csv', 'size_bytes': len(text), 'protocol_version': 1})
        assert ws.receive_json()['type'] == 'ready'
        ws.send_bytes(text)
        while ws.receive_json()['type'] != 'ack':
            pass
        ws.send_json({'type': 'finish'})
        while True:
            event = ws.receive_json()
            assert event['type'] != 'error'
            if event['type'] == 'complete':
                break
        assert event['simulation']['data_base'] == '2026-10-25'
        assert event['simulation']['recusados'] == 1
        ws.send_json({'type': 'close'})
