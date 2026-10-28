"""Transferências constitucionais (FPM, FUNDEB, ITR, royalties...) - Tesouro Nacional.

É o dinheiro que a União repassa ao município por obrigação da Constituição.
Docs: https://apiapex.tesouro.gov.br/aria/v1/transferencias_constitucionais/docs

Cuidados (comportamento documentado pelo pacote tesouror):
- os códigos de estado e município são internos do Tesouro, não do IBGE;
- /por_estado_municipio usa parâmetros em minúsculas, p_municipio no singular
  e paginação page/pageSize; nomes errados são ignorados em silêncio;
- vários valores vão separados por dois-pontos, ex.: p_ano=2023:2024.
"""
import unicodedata
from collections import defaultdict
from datetime import date

from comum import CONFIG, SemDados, agora, get_json, salvar

BASE = "https://apiapex.tesouro.gov.br/aria/v1/transferencias_constitucionais/custom"
POR_PAGINA = 1000

UF_NOMES = {"BA": "bahia"}


def chaves_minusculas(d):
    return {str(k).lower(): v for k, v in d.items()} if isinstance(d, dict) else {}


def linhas(corpo):
    if isinstance(corpo, list):
        lista = corpo
    else:
        lista = corpo.get("registros") or corpo.get("items") or []
    return [chaves_minusculas(x) for x in lista]


def sem_acento(t):
    return "".join(c for c in unicodedata.normalize("NFD", str(t)) if unicodedata.category(c) != "Mn").lower().strip()


def codigo_estado():
    nome = UF_NOMES.get(CONFIG["uf"], CONFIG["uf"]).lower()
    for e in linhas(get_json(f"{BASE}/estados")):
        if sem_acento(e.get("nome")) == nome or str(e.get("sigla", "")).upper() == CONFIG["uf"]:
            return e["codigo"]
    raise RuntimeError(f"Estado {CONFIG['uf']} não encontrado em /estados")


def codigo_municipio(cod_uf):
    alvo = sem_acento(CONFIG["municipio"])
    for m in linhas(get_json(f"{BASE}/municipios", {"p_nome": CONFIG["municipio"], "p_uf": cod_uf})):
        if sem_acento(m.get("nome")) == alvo:
            return m["codigo"]
    raise RuntimeError(f"Município {CONFIG['municipio']} não encontrado em /municipios")


def buscar(cod_uf, cod_mun, anos):
    todas, pagina = [], 1
    while True:
        try:
            corpo = get_json(f"{BASE}/por_estado_municipio", {
                "p_estado": cod_uf, "p_municipio": cod_mun,
                "p_ano": ":".join(str(a) for a in anos),
                "page": pagina, "pageSize": POR_PAGINA,
            })
        except SemDados:
            break
        lote = linhas(corpo)
        todas += lote
        if len(lote) < POR_PAGINA:
            break
        pagina += 1
    return todas


def do_municipio(linha):
    ibge = "".join(c for c in str(linha.get("co_ibge") or "") if c.isdigit())
    if not ibge:
        return sem_acento(linha.get("municipio") or "") in ("", sem_acento(CONFIG["municipio"]))
    return ibge[:6] == CONFIG["ibge"][:6]


def coletar():
    print("Tesouro - Transferências constitucionais")
    cod_uf = codigo_estado()
    cod_mun = codigo_municipio(cod_uf)
    print(f"  códigos do Tesouro: estado {cod_uf}, município {cod_mun}")
    anos = list(range(CONFIG["ano_inicial"], date.today().year + 1))
    brutas = [l for l in buscar(cod_uf, cod_mun, anos) if do_municipio(l)]
    if not brutas:
        raise RuntimeError("A API de transferências não devolveu nada para o município")

    soma = defaultdict(float)
    for l in brutas:
        try:
            mes = f"{int(l['ano']):04d}-{int(l['mes']):02d}"
            valor = float(l.get("valor") or 0)
        except (KeyError, TypeError, ValueError):
            continue
        soma[(mes, str(l.get("transferencia") or "Outras").strip())] += valor

    serie = [{"mes": m, "transferencia": t, "valor": round(v, 2)} for (m, t), v in sorted(soma.items())]
    salvar("transferencias.json", {
        "fonte": "Tesouro Nacional - Transferências Constitucionais",
        "atualizado_em": agora(),
        "serie": serie,
    })


if __name__ == "__main__":
    coletar()
