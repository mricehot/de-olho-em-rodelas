"""Licitações e contratos publicados no PNCP (Portal Nacional de Contratações Públicas).

Desde a Lei 14.133/2021 as prefeituras são obrigadas a publicar ali.
Manual da API de consulta: https://www.gov.br/pncp/pt-br/acesso-a-informacao/manuais

Cuidados (comportamento observado da API):
- 204 sem corpo = nenhum registro;
- alguns filtros são ignorados em silêncio, então conferimos o CNPJ de cada registro;
- limite de requisições não documentado: fazemos uma chamada a cada ~5 s.
"""
import json
import time
from datetime import date, timedelta

import requests

from comum import CONFIG, PASTA_DADOS, SemDados, agora, get_json, mascarar_cpf, salvar

BASE = "https://pncp.gov.br/api/consulta/v1"
CNPJ = CONFIG["cnpj_prefeitura"]
MODALIDADES = range(1, 15)
PAUSA = 5


def fmt(d):
    return d.strftime("%Y%m%d")


def paginar(caminho, params, tamanho):
    pagina, itens = 1, []
    while True:
        time.sleep(PAUSA)
        dados = get_json(f"{BASE}/{caminho}", {**params, "pagina": pagina, "tamanhoPagina": tamanho})
        itens += dados.get("data") or []
        if pagina >= (dados.get("totalPaginas") or 1):
            return itens
        pagina += 1


def buscar_periodo(caminho, params, inicio, fim, tamanho):
    """Busca um intervalo; se a API recusar o intervalo, divide ao meio."""
    try:
        return paginar(caminho, {**params, "dataInicial": fmt(inicio), "dataFinal": fmt(fim)}, tamanho)
    except SemDados:
        return []
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code in (400, 422) and (fim - inicio).days > 31:
            meio = inicio + (fim - inicio) / 2
            return (buscar_periodo(caminho, params, inicio, meio, tamanho)
                    + buscar_periodo(caminho, params, meio + timedelta(days=1), fim, tamanho))
        raise


def do_orgao(registro):
    org = registro.get("orgaoEntidade") or {}
    return "".join(c for c in str(org.get("cnpj", "")) if c.isdigit()) == CNPJ


def link_pncp(tipo, r, ano_campo, seq_campo):
    ano, seq = r.get(ano_campo), r.get(seq_campo)
    if ano and seq:
        return f"https://pncp.gov.br/app/{tipo}/{CNPJ}/{ano}/{seq}"
    return None


def resumir_contratacao(r):
    return {
        "id": r.get("numeroControlePNCP"),
        "numero": r.get("numeroCompra"),
        "processo": r.get("processo"),
        "objeto": r.get("objetoCompra"),
        "modalidade": r.get("modalidadeNome"),
        "situacao": r.get("situacaoCompraNome"),
        "valor_estimado": r.get("valorTotalEstimado"),
        "valor_homologado": r.get("valorTotalHomologado"),
        "data": (r.get("dataPublicacaoPncp") or "")[:10],
        "abertura": (r.get("dataAberturaProposta") or "")[:10],
        "link": link_pncp("editais", r, "anoCompra", "sequencialCompra"),
    }


def resumir_contrato(r):
    pf = r.get("tipoPessoa") == "PF"
    doc = r.get("niFornecedor")
    return {
        "id": r.get("numeroControlePNCP"),
        "numero": r.get("numeroContratoEmpenho"),
        "objeto": r.get("objetoContrato"),
        "fornecedor": r.get("nomeRazaoSocialFornecedor"),
        "documento": mascarar_cpf(doc) if pf else doc,
        "tipo": (r.get("tipoContrato") or {}).get("nome"),
        "valor_inicial": r.get("valorInicial"),
        "valor_global": r.get("valorGlobal"),
        "assinatura": (r.get("dataAssinatura") or "")[:10],
        "vigencia_fim": (r.get("dataVigenciaFim") or "")[:10],
        "link": link_pncp("contratos", r, "anoContrato", "sequencialContrato"),
    }


def anteriores():
    try:
        return json.loads((PASTA_DADOS / "pncp.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def mesclar(antigos, novos):
    por_id = {i["id"]: i for i in antigos if i.get("id")}
    por_id.update({i["id"]: i for i in novos if i.get("id")})
    return sorted(por_id.values(), key=lambda i: i.get("data") or i.get("assinatura") or "", reverse=True)


def coletar():
    print("PNCP (licitações e contratos)")
    antes = anteriores()
    hoje = date.today()
    # Primeira coleta: tudo desde ano_inicial. Depois: só desde 1º de janeiro do ano passado.
    inicio_ano = CONFIG["ano_inicial"] if not antes else hoje.year - 1
    contratacoes, contratos = [], []

    for ano in range(inicio_ano, hoje.year + 1):
        ini, fim = date(ano, 1, 1), min(date(ano, 12, 31), hoje)
        print(f"  ano {ano}")
        for mod in MODALIDADES:
            achados = buscar_periodo("contratacoes/publicacao",
                                     {"codigoModalidadeContratacao": mod, "cnpj": CNPJ},
                                     ini, fim, 50)
            contratacoes += [resumir_contratacao(r) for r in achados if do_orgao(r)]
        achados = buscar_periodo("contratos", {"cnpjOrgao": CNPJ}, ini, fim, 500)
        contratos += [resumir_contrato(r) for r in achados if do_orgao(r)]

    salvar("pncp.json", {
        "fonte": "PNCP - Portal Nacional de Contratações Públicas",
        "atualizado_em": agora(),
        "contratacoes": mesclar((antes or {}).get("contratacoes", []), contratacoes),
        "contratos": mesclar((antes or {}).get("contratos", []), contratos),
    })


if __name__ == "__main__":
    coletar()
