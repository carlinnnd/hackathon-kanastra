"""Contrato comum de decisões e agregações; valores monetários calculados em centavos."""
import json
from collections import Counter, defaultdict
from decimal import Decimal

from ..infrastructure.database.models import SimulationReportModel, SimulationItemDetailModel


def money(cents):
    return f"{Decimal(cents) / 100:.2f}"


def serializar_resultado(res):
    return {
        **res.detalhes,
        "linha": res.linha, "documento": res.documento, "sacado": res.sacado,
        "status": res.status, "elegivel": res.aprovado, "aprovado": res.aprovado,
        "valor_nominal": f"{res.valor_nominal:.2f}" if res.valor_nominal is not None else None,
        "valor_liquido": f"{res.valor_liquido:.2f}" if res.valor_liquido is not None else None,
        "valor_desconto": f"{res.desconto:.2f}" if res.aprovado and res.desconto is not None else None,
        "prazo_dias": res.dias_vencimento,
        "motivos": [{"codigo": m.codigo, "mensagem": m.mensagem, "dados": m.dados} for m in res.motivos],
        "codigos_recusa": [m.codigo for m in res.motivos], "quantidade_violacoes": len(res.motivos),
    }


class AgregadorResultados:
    def __init__(self, tipo_analise, config):
        self.tipo = tipo_analise
        self.config = config
        self.status = Counter()
        self.cadastro = Counter()
        self.nominais = Counter()
        self.motivos = defaultdict(lambda: [0, 0])
        self.faixas = Counter({s: 0 for s in ["Vencidos", "0–30", "31–60", "61–90", "91–180", "Acima de 180"]})
        self.exposicoes = Counter()
        self.fundos = Counter()
        self.ponderado = 0
        self.liquido = 0

    def adicionar(self, res):
        status = res.status
        cents = int(res.valor_nominal * 100) if res.valor_nominal is not None else 0
        self.status[status] += 1
        self.cadastro[res.detalhes.get("situacao_cadastral", "SEM_DADOS")] += 1
        self.nominais[status] += cents
        for m in res.motivos:
            self.motivos[m.codigo][0] += 1
            self.motivos[m.codigo][1] += cents
        dias = res.dias_vencimento
        if dias is not None:
            faixa = "Vencidos" if dias < 0 else "0–30" if dias <= 30 else "31–60" if dias <= 60 else "61–90" if dias <= 90 else "91–180" if dias <= 180 else "Acima de 180"
            self.faixas[faixa] += 1
        if res.aprovado:
            self.ponderado += cents * (dias or 0)
            self.liquido += int(res.valor_liquido * 100)
        if self.tipo == "carteira" and status == "CARTEIRA_HISTORICA":
            fund = res.detalhes["doc_fundo"]
            raiz = res.detalhes["raiz_cnpj_sacado"]
            self.exposicoes[(fund, raiz)] += cents
            self.fundos[fund] += cents

    def finalizar(self, estado):
        total = sum(self.nominais.values())
        elegivel = self.nominais["APROVADA"]
        if self.tipo == "carteira":
            exposicoes = [
                {"doc_fundo": f, "raiz": r, "valor_nominal": money(v),
                 "percentual": f"{Decimal(v) * 100 / self.fundos[f]:.2f}" if self.fundos[f] else "0.00"}
                for (f, r), v in self.exposicoes.most_common(20)
            ]
        else:
            exposicoes = [
                {"raiz": r, "valor_nominal": f"{v:.2f}",
                 "percentual": f"{v * 100 / estado.total_nominal:.2f}" if estado.total_nominal else "0.00"}
                for r, v in sorted(estado.exposicoes_sacado_raiz.items(), key=lambda x: x[1], reverse=True)[:20]
            ]
        return {
            "tipo_analise": self.tipo, "status_counts": dict(self.status),
            "cadastro_counts": dict(self.cadastro), "fundos_distintos": len(self.fundos),
            "grupos_sacado_distintos": len(self.exposicoes) if self.tipo == "carteira" else len(estado.exposicoes_sacado_raiz),
            "valor_nominal_total": money(total), "valor_nominal_elegivel": money(elegivel),
            "valor_desconto": money(elegivel - self.liquido), "valor_liquido": money(self.liquido),
            "aprovacao_valor_pct": f"{Decimal(elegivel) * 100 / total:.2f}" if total else "0.00",
            "prazo_medio_ponderado": f"{Decimal(self.ponderado) / elegivel:.2f}" if elegivel else None,
            "nominal_por_status": {k: money(v) for k, v in self.nominais.items()},
            "motivos": [{"codigo": k, "quantidade": v[0], "valor_nominal": money(v[1])} for k, v in sorted(self.motivos.items(), key=lambda x: x[1][0], reverse=True)],
            "motivos_sobrepostos": True, "faixas_vencimento": dict(self.faixas),
            "exposicoes": exposicoes, "exposicoes_limite_exibicao": 20,
            "regras": self.config.raw_config,
            "metodologia": "Carteira: análise descritiva, sem aprovação, aquisição ou precificação; concentração por fundo e raiz." if self.tipo == "carteira" else "Novas operações: regras ativas e duplicidade global/intralote; somente aprovações entram na projeção. Excesso histórico preservado; nova exposição acima do limite configurado é recusada.",
        }


def obter_analytics(db, simulation_id):
    report = db.get(SimulationReportModel, simulation_id)
    return json.loads(report.analytics_json) if report else None


def serializar_item_db(item, detail=None):
    if detail:
        return json.loads(detail.payload_json)
    return {"linha": item.linha, "documento": item.documento, "sacado": item.sacado,
            "aprovado": item.aprovado, "elegivel": item.aprovado,
            "status": "APROVADA" if item.aprovado else "RECUSADA",
            "valor_nominal": f"{item.valor_nominal:.2f}" if item.valor_nominal is not None else None,
            "valor_liquido": f"{item.valor_liquido:.2f}" if item.valor_liquido is not None else None,
            "motivos": json.loads(item.motivos_json)}


def serializar_pagina(db, simulation_id, items):
    # Uma única consulta de detalhes por página; sem N+1.
    lines = [it.linha for it in items]
    details = db.query(SimulationItemDetailModel).filter(
        SimulationItemDetailModel.simulation_id == simulation_id,
        SimulationItemDetailModel.linha.in_(lines)).all() if lines else []
    by_line = {d.linha: d for d in details}
    return [serializar_item_db(it, by_line.get(it.linha)) for it in items]
