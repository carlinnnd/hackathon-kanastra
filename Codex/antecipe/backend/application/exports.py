"""Exportações de uma simulação: cursor limitado para CSV e agregações para PDF."""
import csv
import io
import json
from decimal import Decimal
from xml.sax.saxutils import escape

from sqlalchemy import select
from ..domain.ingestion import CABECALHOS_OBRIGATORIOS
from ..infrastructure.database.models import SimulationItemDetailModel
from .result_reporting import obter_analytics, normalizar_resultado

EXPORT_FIELDS = [
    "id_recebivel", "linha_original", "status", "elegivel", "codigos_recusa", "motivos_recusa", "quantidade_violacoes",
    "doc_fundo", "doc_cedente", "doc_sacado", "nu_documento", "tipo_recebivel", "data_vencimento",
    "valor_nominal", "prazo_dias", "taxa_mensal", "valor_desconto", "valor_liquido", "raiz_cnpj_sacado",
    "situacao_cadastral", "concentracao_atual_pct", "concentracao_projetada_pct", "duplicado",
    "id_simulacao", "versao_regras", "data_base", "processado_em", "cadastro_fonte", "tipo_analise",
]


def csv_safe(value):
    if value is None:
        return ""
    text = str(value)
    # Também cobre fórmulas precedidas de espaços/controles, sem remover os dados originais.
    if text.lstrip().startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n")):
        return "'" + text
    return text


def iter_resultados(db, simulation_id):
    stmt = select(SimulationItemDetailModel.payload_json).where(
        SimulationItemDetailModel.simulation_id == simulation_id
    ).order_by(SimulationItemDetailModel.linha).execution_options(yield_per=256, stream_results=True)
    for payload in db.execute(stmt).scalars():
        yield normalizar_resultado(json.loads(payload))


def gerar_csv(db, sim, violacoes=False):
    rows = iter_resultados(db, sim.id)
    first = next(rows, None)
    originals = list(dict.fromkeys(list(CABECALHOS_OBRIGATORIOS) + list((first or {}).get("originais", {}))))
    fields = ["id_simulacao", "linha_original", "nu_documento", "status", "codigo", "motivo"] if violacoes else originals + EXPORT_FIELDS
    buf = io.StringIO(newline="")
    writer = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    writer.writerow([csv_safe(field) for field in fields])
    yield ("\ufeff" + buf.getvalue()).encode("utf-8")
    buf.seek(0); buf.truncate(0)
    import itertools
    for row in itertools.chain([first] if first else [], rows):
        if violacoes:
            for motivo in row["motivos"]:
                writer.writerow([csv_safe(v) for v in [sim.id, row["linha"], row["documento"], row["status"], motivo["codigo"], motivo["mensagem"]]])
        else:
            values = {**row, "id_recebivel": f"{sim.id}:{row['linha']}", "linha_original": row["linha"],
                "id_simulacao": sim.id, "versao_regras": sim.rule_version.version_number,
                "data_base": sim.data_base.strftime("%d/%m/%Y"),
                "processado_em": sim.created_at.isoformat() + "Z", "cadastro_fonte": sim.cadastro_fonte,
                "codigos_recusa": " | ".join(m["codigo"] for m in row["motivos"]),
                "motivos_recusa": " | ".join(m["mensagem"] for m in row["motivos"])}
            for key in ["valor_nominal", "valor_desconto", "valor_liquido", "taxa_mensal", "concentracao_atual_pct", "concentracao_projetada_pct"]:
                if values.get(key) is not None:
                    values[key] = str(values[key]).replace(".", ",")
            writer.writerow([csv_safe(row.get("originais", {}).get(k, "")) for k in originals] + [csv_safe(values.get(k)) for k in EXPORT_FIELDS])
        if buf.tell() >= 32768:
            yield buf.getvalue().encode("utf-8")
            buf.seek(0); buf.truncate(0)
    if buf.tell():
        yield buf.getvalue().encode("utf-8")


def gerar_pdf(sim, analytics):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Flowable
    from reportlab.graphics.shapes import Drawing, Rect, String

    buffer = io.BytesIO()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Brand", fontName="Helvetica-Bold", fontSize=33, leading=42, textColor=colors.HexColor("#193e39")))
    styles["Title"].textColor = colors.HexColor("#193e39")
    navy = colors.HexColor("#122e39")
    teal = colors.HexColor("#16786b")
    muted = colors.HexColor("#617780")
    styles["Title"].fontSize = 26
    styles["Title"].leading = 32
    styles["Title"].alignment = 0
    styles["Title"].spaceAfter = 18
    styles["Title"].textColor = navy
    styles["Heading1"].textColor = navy
    styles["Heading2"].textColor = teal
    styles["BodyText"].fontSize = 9
    styles["BodyText"].leading = 12
    styles["BodyText"].textColor = navy
    styles.add(ParagraphStyle(name="Eyebrow", fontSize=9, leading=14, textColor=teal, spaceAfter=10))
    class MetricCards(Flowable):
        def __init__(self, cards):
            Flowable.__init__(self)
            self.cards = cards
            self.width, self.height = 500, 166
        def draw(self):
            c = self.canv
            for i, (label, value) in enumerate(self.cards):
                x, y = (i % 2) * 254, 86 if i < 2 else 4
                c.setFillColor(colors.HexColor('#f1f6f6'))
                c.roundRect(x, y, 242, 72, 7, fill=1, stroke=0)
                c.setFillColor(teal); c.rect(x, y+14, 3, 44, fill=1, stroke=0)
                c.setFillColor(muted); c.setFont('Helvetica', 9)
                c.drawString(x+15, y+49, label)
                c.setFillColor(navy); c.setFont('Helvetica-Bold', 17)
                c.drawString(x+15, y+20, str(value))
    story = []
    def p(text, style="BodyText"):
        story.append(Paragraph(escape(str(text)), styles[style])); story.append(Spacer(1, 7))
    def brl(value):
        return "R$ " + f"{Decimal(str(value)):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    def table(rows, widths=None):
        rows = [[Paragraph(escape(str(c)), styles["BodyText"]) for c in row] for row in rows]
        t = Table(rows, colWidths=widths or [255, 245], repeatRows=1, hAlign="LEFT")
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e3eee9")),
            ("LINEBELOW", (0, 0), (-1, 0), .6, colors.HexColor("#193e39")),
            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f8f9")]),
            ("LINEBELOW", (0, 1), (-1, -1), .25, colors.HexColor("#dce6e8")),
            ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(t); story.append(Spacer(1, 16))
    def chart(items):
        items = list(items)[:8]
        d = Drawing(500, len(items) * 32 + 10)
        maximum = max([int(n) for _, n in items] + [1])
        for i, (label, n) in enumerate(items):
            y = (len(items) - i - 1) * 32 + 8
            d.add(String(0, y + 5, str(label)[:36], fontSize=8))
            width = int(n) / maximum * 225
            d.add(Rect(230, y, width, 17, fillColor=colors.HexColor("#3d7d6f"), strokeColor=None))
            d.add(String(465, y + 5, str(n), fontSize=8))
        story.append(d)
    counts = analytics["status_counts"]
    historical = analytics["tipo_analise"] == "carteira"
    p("ANTECIPE FIDC  /  INTELIGÊNCIA EM RECEBÍVEIS", "Eyebrow")
    story.append(Spacer(1, 12))
    p("Seu resultado, em perspectiva.", "Title")
    p("Análise de carteira histórica" if historical else "Análise de elegibilidade de recebíveis", "Heading1")
    p(f"ANTECIPE FIDC - Data-base: {sim.data_base.strftime('%d/%m/%Y')}")
    p(f"Relatório executivo • Emissão {sim.created_at.strftime('%d/%m/%Y')} • Referência {sim.id[:8].upper()}", "Eyebrow")
    story.append(MetricCards([
        ("Volume nominal analisado", brl(analytics['valor_nominal_total'])),
        ("Total a receber" if not historical else "Títulos na carteira", brl(analytics['valor_liquido']) if not historical else sim.total_itens),
        ("Notas aprovadas" if not historical else "Modalidade", counts.get('APROVADA', 0) if not historical else "Carteira histórica"),
        ("Notas recusadas" if not historical else "Data-base", counts.get('RECUSADA', 0) if not historical else sim.data_base.strftime('%d/%m/%Y'))]))
    story.append(Spacer(1, 18))
    table([["Indicador", "Resultado"], ["Títulos analisados", sim.total_itens],
        ["Valor nominal analisado", brl(analytics["valor_nominal_total"])],
        ["Valor nominal elegível", "Não aplicável à carteira" if historical else brl(analytics["valor_nominal_elegivel"])],
        ["Desconto total", "Não aplicável" if historical else brl(analytics["valor_desconto"])],
        ["Valor líquido aprovado", "Não aplicável" if historical else brl(analytics["valor_liquido"])],
        ["Aprovação por quantidade", "Não aplicável" if historical else f"{counts.get('APROVADA', 0) * 100 / max(1, sim.total_itens):.2f}%"],
        ["Aprovação em valor", "Não aplicável" if historical else analytics["aprovacao_valor_pct"] + "%"]])
    p(analytics["metodologia"])
    story.append(PageBreak())
    p("Decisões e perfil de vencimentos", "Title")
    table([["Classificação", "Quantidade"]] + list(counts.items()))
    p("Vencimentos em relação à data-base", "Heading2")
    chart(analytics["faixas_vencimento"].items())
    p(f"Prazo médio ponderado das aprovadas: {analytics['prazo_medio_ponderado'] or 'Não aplicável'} dias.")
    p("Principais motivos", "Heading2")
    if analytics["motivos"]:
        chart([(m["codigo"], m["quantidade"]) for m in analytics["motivos"]])
    else:
        p("Nenhuma violação registrada. Carteira histórica não passa por decisão de nova operação." if historical else "Nenhuma violação identificada neste lote.")
    p("Os motivos podem se sobrepor: uma nota com duas violações aparece em ambos os grupos. Valores por motivo não devem ser somados como total recusado.")
    story.append(PageBreak())
    p("Concentração e exposição", "Title")
    p("Maiores exposições por fundo e raiz do CNPJ." if historical else "Maiores exposições projetadas após incluir somente as aprovações do lote.")
    table([["Fundo / raiz", "Nominal / concentração"]] + [
        [f"{v.get('doc_fundo', 'ANTECIPE')} / {v['raiz']}", f"{brl(v['valor_nominal'])} / {v['percentual']}%"]
        for v in analytics["exposicoes"][:15]])
    p("Exibição das 15 maiores exposições. O CSV preserva o detalhamento completo dos títulos.")
    p("Histórico acima do limite é preservado. Nas novas operações, a exposição projetada é comparada ao limite ativo do JSON; igualdade ao limite é permitida.")
    story.append(PageBreak())
    p("Regras, metodologia e auditoria", "Title")
    table([["Validador", "Estado / parâmetros"]] + [[r["codigo"], ("Ativo" if r["ativo"] else "Inativo") + " / " + json.dumps(r["parametros"], ensure_ascii=False)] for r in analytics["regras"]["validadores"]])
    p("Precificação: desconto comercial simples com arredondamento HALF_UP por título, usando apenas notas aprovadas. Parâmetros: " + json.dumps(analytics["regras"]["precificacao"], ensure_ascii=False))
    p(f"Simulação: {sim.id}. Versão base do regulamento: {sim.rule_version.version_number}.")
    p(f"Hash da configuração: {sim.configuration_hash}")
    p(f"Cadastro: {sim.cadastro_fonte}")
    p(f"Carteira de referência: {sim.carteira_referencia}")
    p(f"Processado em (UTC): {sim.created_at.isoformat()}")
    for aviso in json.loads(sim.avisos_json):
        p(aviso)
    p("Próximos passos: revisar os motivos das recusas, corrigir os dados ou confirmar a situação cadastral e enviar novamente. O cadastro mock não constitui comprovação cadastral oficial.")
    def footer(canvas, doc):
        canvas.saveState()
        width, height = A4
        canvas.setFillColor(navy)
        canvas.rect(0, height-58, width, 58, fill=1, stroke=0)
        canvas.setFillColor(colors.white); canvas.setFont('Helvetica-Bold', 17)
        canvas.drawString(46, height-35, 'Antecipe')
        canvas.setFont('Helvetica', 9); canvas.drawRightString(width-46, height-33, 'ANTECIPE FIDC  |  RELATÓRIO EXECUTIVO')
        canvas.setStrokeColor(colors.HexColor('#dce6e8')); canvas.line(46, 43, width-46, 43)
        canvas.setFont('Helvetica', 8); canvas.setFillColor(muted)
        canvas.drawString(46, 28, f'Antecipe • Ref. {sim.id[:8].upper()} • Uso gerencial')
        canvas.drawRightString(width-46, 28, f'{doc.page:02d}')
        canvas.restoreState()
    SimpleDocTemplate(buffer, pagesize=A4, rightMargin=46, leftMargin=46, topMargin=82, bottomMargin=58,
        title=f"Antecipe - Relatório {sim.id[:8]}", author="Antecipe").build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()


def exportar(db, sim, formato):
    analytics = obter_analytics(db, sim.id)
    if not analytics:
        raise ValueError("Esta simulação é anterior ao detalhamento de exportação. Reprocesse o arquivo.")
    if formato == "pdf":
        return iter([gerar_pdf(sim, analytics)]), "application/pdf"
    if formato in {"csv", "violacoes"}:
        return gerar_csv(db, sim, violacoes=formato == "violacoes"), "text/csv; charset=utf-8"
    raise ValueError("Formato inválido. Use csv, pdf ou violacoes.")
