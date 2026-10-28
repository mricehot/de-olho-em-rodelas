"""Relatórios fiscais oficiais (RREO e RGF) do Tesouro Nacional - Siconfi.

RREO Anexo 01: receitas e despesas do orçamento.
RREO Anexo 02: despesas por função (saúde, educação...).
RGF  Anexo 01: despesa com pessoal e limite da LRF (Prefeitura e Câmara).

Docs: https://apidatalake.tesouro.gov.br/docs/siconfi/
"""
from datetime import date

from comum import CONFIG, SemDados, agora, get_json, salvar

BASE = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt"
CAMPOS = ("conta", "cod_conta", "coluna", "rotulo", "valor")


def buscar_tudo(endpoint, params):
    """Segue a paginação do ORDS (hasMore/offset) e devolve todos os itens."""
    itens, offset = [], 0
    while True:
        dados = get_json(f"{BASE}/{endpoint}", {**params, "offset": offset})
        lote = dados.get("items", [])
        itens += lote
        if not dados.get("hasMore") or not lote:
            return itens
        offset += len(lote)


def enxugar(itens):
    return [{k: i.get(k) for k in CAMPOS} for i in itens]


def rreo(ano, anexo):
    """Último bimestre publicado do ano (6 = ano fechado)."""
    for periodo in range(6, 0, -1):
        try:
            itens = buscar_tudo("rreo", {
                "an_exercicio": ano, "nr_periodo": periodo,
                "co_tipo_demonstrativo": "RREO", "no_anexo": anexo,
                "co_esfera": "M", "id_ente": CONFIG["ibge"],
            })
        except SemDados:
            continue
        if itens:
            return {"periodo": periodo, "linhas": enxugar(itens)}
    return None


def rgf_pessoal(ano, poder="E"):
    """Poder "E" = Prefeitura, "L" = Câmara Municipal.
    Municípios pequenos podem publicar o RGF por semestre (S) ou quadrimestre (Q),
    e às vezes na versão simplificada."""
    for tipo in ("RGF", "RGF Simplificado"):
        for periodicidade, ultimo in (("Q", 3), ("S", 2)):
            for periodo in range(ultimo, 0, -1):
                try:
                    itens = buscar_tudo("rgf", {
                        "an_exercicio": ano, "in_periodicidade": periodicidade,
                        "nr_periodo": periodo, "co_tipo_demonstrativo": tipo,
                        "no_anexo": "RGF-Anexo 01", "co_esfera": "M",
                        "co_poder": poder, "id_ente": CONFIG["ibge"],
                    })
                except SemDados:
                    continue
                if itens:
                    return {"periodo": periodo, "periodicidade": periodicidade,
                            "tipo": tipo, "linhas": enxugar(itens)}
    return None


def coletar():
    print("Siconfi (Tesouro Nacional)")
    saida = {"fonte": "Siconfi - Tesouro Nacional", "atualizado_em": agora(), "anos": {}}
    for ano in range(CONFIG["ano_inicial"], date.today().year + 1):
        print(f"  ano {ano}")
        bloco = {
            "rreo_01": rreo(ano, "RREO-Anexo 01"),
            "rreo_02": rreo(ano, "RREO-Anexo 02"),
            "rgf_01": rgf_pessoal(ano),
            "rgf_01_camara": rgf_pessoal(ano, "L"),
        }
        if any(bloco.values()):
            saida["anos"][str(ano)] = bloco
    if not saida["anos"]:
        raise RuntimeError("Siconfi não devolveu nenhum relatório para o município")
    salvar("siconfi.json", saida)


if __name__ == "__main__":
    coletar()
