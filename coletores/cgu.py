"""Recursos federais que chegam a Rodelas - API do Portal da Transparência (CGU).

Precisa de uma chave gratuita: https://portaldatransparencia.gov.br/api-de-dados (botão "Cadastre-se")
No GitHub, guarde a chave como secret com o nome CGU_API_KEY.
Documentação: https://api.portaldatransparencia.gov.br/swagger-ui.html
"""
import os
import time
from datetime import date

from comum import CONFIG, SemDados, agora, get_json, salvar

BASE = "https://api.portaldatransparencia.gov.br/api-de-dados"
PAUSA = 1


def pegar(obj, *caminhos):
    """Primeiro valor não vazio entre vários caminhos 'a.b.c' (a API muda nomes às vezes)."""
    for caminho in caminhos:
        atual = obj
        for parte in caminho.split("."):
            atual = atual.get(parte) if isinstance(atual, dict) else None
        if atual not in (None, ""):
            return atual
    return None


def paginar(endpoint, params, cabecalho):
    pagina, itens = 1, []
    while True:
        time.sleep(PAUSA)
        try:
            lote = get_json(f"{BASE}/{endpoint}", {**params, "pagina": pagina}, cabecalho)
        except SemDados:
            return itens
        if not lote:
            return itens
        itens += lote
        pagina += 1


def meses():
    hoje = date.today()
    for ano in range(CONFIG["ano_inicial"], hoje.year + 1):
        for mes in range(1, 13):
            if (ano, mes) < (hoje.year, hoje.month):
                yield f"{ano}{mes:02d}"


def por_mes(endpoint, cabecalho):
    serie = []
    for mes_ano in meses():
        linhas = paginar(endpoint, {"mesAno": mes_ano, "codigoIbge": CONFIG["ibge"]}, cabecalho)
        if linhas:
            serie.append({
                "mes": f"{mes_ano[:4]}-{mes_ano[4:]}",
                "valor": round(sum(pegar(l, "valor") or 0 for l in linhas), 2),
                "beneficiados": sum(pegar(l, "quantidadeBeneficiados") or 0 for l in linhas),
            })
    return serie


def convenios(cabecalho):
    linhas = paginar("convenios", {"codigoIBGE": CONFIG["ibge"]}, cabecalho)
    saida = [{
        "numero": pegar(c, "dimConvenio.numero", "numero"),
        "objeto": pegar(c, "dimConvenio.objeto", "objeto"),
        "orgao": pegar(c, "orgao.nome", "orgao.orgaoMaximo.nome"),
        "convenente": pegar(c, "convenente.nome"),
        "situacao": pegar(c, "situacao"),
        "valor": pegar(c, "valor"),
        "valor_liberado": pegar(c, "valorLiberado"),
        "inicio": pegar(c, "dataInicioVigencia"),
        "fim": pegar(c, "dataFinalVigencia"),
    } for c in linhas]
    return sorted(saida, key=lambda c: c.get("inicio") or "", reverse=True)


def coletar():
    print("CGU - Portal da Transparência federal")
    chave = os.environ.get("CGU_API_KEY")
    if not chave:
        raise RuntimeError("Sem a chave CGU_API_KEY; recursos federais não foram atualizados")
    cabecalho = {"chave-api-dados": chave, "Accept": "application/json"}
    salvar("cgu.json", {
        "fonte": "Portal da Transparência - CGU",
        "atualizado_em": agora(),
        "convenios": convenios(cabecalho),
        "bolsa_familia": por_mes("novo-bolsa-familia-por-municipio", cabecalho),
        "bpc": por_mes("bpc-por-municipio", cabecalho),
    })


if __name__ == "__main__":
    coletar()
