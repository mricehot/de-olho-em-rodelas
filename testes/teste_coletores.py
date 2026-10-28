"""Testa os coletores sem internet: troca as chamadas HTTP por respostas no
formato das APIs oficiais e confere os arquivos gerados.

Rodar:  python testes/teste_coletores.py
Os arquivos de teste vão para testes/saida/ (o site real não é tocado).
"""
import json
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "coletores"))

import comum  # noqa: E402

SAIDA = RAIZ / "testes" / "saida"
comum.PASTA_DADOS = SAIDA

import cgu  # noqa: E402
import despesas  # noqa: E402
import transferencias  # noqa: E402
import coletar_tudo  # noqa: E402
import pncp  # noqa: E402
import siconfi  # noqa: E402

pncp.PAUSA = cgu.PAUSA = 0
CNPJ = comum.CONFIG["cnpj_prefeitura"]


def falso_siconfi(url, params=None, headers=None):
    p = params or {}
    if p.get("an_exercicio") != 2025:
        raise comum.SemDados(url)
    if url.endswith("/rreo"):
        if p["nr_periodo"] != 4:  # só o 4º bimestre "existe"
            raise comum.SemDados(url)
        if p["no_anexo"] == "RREO-Anexo 01":
            itens = [
                {"conta": "RECEITAS (EXCETO INTRA-ORÇAMENTÁRIAS) (I)", "coluna": "Até o Bimestre (c)", "valor": 31500000.5, "cod_conta": "a", "rotulo": "Padrão"},
                {"conta": "RECEITAS (EXCETO INTRA-ORÇAMENTÁRIAS) (I)", "coluna": "PREVISÃO INICIAL", "valor": 45000000, "cod_conta": "a", "rotulo": "Padrão"},
                {"conta": "DESPESAS (EXCETO INTRA-ORÇAMENTÁRIAS) (VIII)", "coluna": "DESPESAS LIQUIDADAS ATÉ O BIMESTRE (h)", "valor": 28900000, "cod_conta": "b", "rotulo": "Padrão"},
            ]
        else:
            itens = [
                {"conta": "Saúde", "coluna": "DESPESAS LIQUIDADAS ATÉ O BIMESTRE (d)", "valor": 7900000, "cod_conta": "c", "rotulo": "x"},
                {"conta": "Educação", "coluna": "DESPESAS LIQUIDADAS ATÉ O BIMESTRE (d)", "valor": 12100000, "cod_conta": "d", "rotulo": "x"},
                {"conta": "Educação", "coluna": "DOTAÇÃO INICIAL", "valor": 15000000, "cod_conta": "d", "rotulo": "x"},
            ]
        # testa a paginação: primeira página diz que tem mais
        if p.get("offset", 0) == 0:
            return {"items": itens[:1], "hasMore": True}
        return {"items": itens[1:], "hasMore": False}
    if url.endswith("/rgf") and p["co_poder"] == "L":
        if (p["in_periodicidade"], p["nr_periodo"]) != ("Q", 3):
            raise comum.SemDados(url)
        return {"items": [
            {"conta": "DESPESA TOTAL COM PESSOAL - DTP (VIII) = (IIIa + IIIb)", "coluna": "TOTAL (ÚLTIMOS 12 MESES) (a)", "valor": 1300000, "cod_conta": "e", "rotulo": "x"},
            {"conta": "DESPESA TOTAL COM PESSOAL - DTP (VIII) = (IIIa + IIIb)", "coluna": "% SOBRE A RCL AJUSTADA", "valor": 3.1, "cod_conta": "e", "rotulo": "x"},
        ], "hasMore": False}
    if url.endswith("/rgf"):
        if (p["in_periodicidade"], p["nr_periodo"], p["co_tipo_demonstrativo"]) != ("S", 1, "RGF"):
            raise comum.SemDados(url)
        return {"items": [
            {"conta": "DESPESA TOTAL COM PESSOAL - DTP (VIII) = (IIIa + IIIb)", "coluna": "TOTAL (ÚLTIMOS 12 MESES) (a)", "valor": 21000000, "cod_conta": "e", "rotulo": "x"},
            {"conta": "DESPESA TOTAL COM PESSOAL - DTP (VIII) = (IIIa + IIIb)", "coluna": "% SOBRE A RCL AJUSTADA", "valor": 51.37, "cod_conta": "e", "rotulo": "x"},
        ], "hasMore": False}
    raise AssertionError(url)


def falso_pncp(url, params=None, headers=None):
    p = params or {}
    if p.get("dataInicial", "").startswith("2025") is False:
        raise comum.SemDados(url)
    org = {"cnpj": CNPJ}
    outro = {"cnpj": "00000000000191"}  # simula filtro ignorado pela API
    if "contratacoes" in url:
        if p["codigoModalidadeContratacao"] != 6:
            raise comum.SemDados(url)
        return {"data": [
            {"numeroControlePNCP": "x-1/2025", "numeroCompra": "12", "objetoCompra": "Aquisição de merenda escolar",
             "modalidadeNome": "Pregão - Eletrônico", "situacaoCompraNome": "Divulgada no PNCP",
             "valorTotalEstimado": 350000, "valorTotalHomologado": None, "dataPublicacaoPncp": "2025-03-10T10:00:00",
             "anoCompra": 2025, "sequencialCompra": 1, "orgaoEntidade": org},
            {"numeroControlePNCP": "y-1/2025", "objetoCompra": "De outro órgão", "orgaoEntidade": outro},
        ], "totalPaginas": 1}
    return {"data": [
        {"numeroControlePNCP": "c-1/2025", "numeroContratoEmpenho": "045/2025", "objetoContrato": "Transporte escolar",
         "nomeRazaoSocialFornecedor": "JOSE DA SILVA", "niFornecedor": "12345678901", "tipoPessoa": "PF",
         "valorInicial": 80000, "valorGlobal": 96000, "dataAssinatura": "2025-02-01", "dataVigenciaFim": "2025-12-31",
         "anoContrato": 2025, "sequencialContrato": 3, "orgaoEntidade": org},
    ], "totalPaginas": 1}


def falso_transf(url, params=None, headers=None):
    p = params or {}
    if url.endswith("/estados"):
        return {"registros": [{"CODIGO": 4, "NOME": "BAHIA"}, {"CODIGO": 16, "NOME": "PERNAMBUCO"}]}
    if url.endswith("/municipios"):
        assert p["p_uf"] == 4
        return {"registros": [{"codigo": 2671, "codigo_uf": 4, "nome": "RODELAS"}]}
    assert url.endswith("/por_estado_municipio"), url
    assert p["p_municipio"] == 2671 and p["p_estado"] == 4 and "2025" in p["p_ano"]
    reg = lambda mes, t, v, ibge="2927101": {"UF": "BA", "ANO": "2025", "MES": mes, "TRANSFERENCIA": t,
                                            "codigo_siafi": 3871, "CO_IBGE": ibge, "MUNICIPIO": "RODELAS", "VALOR": v}
    if p["page"] == 1:
        # pageSize grande: devolve página curta e encerra
        return {"registros": [reg("01", "FPM", 900000.10), reg("01", "FUNDEB", 700000), reg("02", "FPM", 950000),
                              reg("01", "FPM", 5, ibge="2900000")], "page": 1}
    raise AssertionError("não devia pedir página 2")


def falso_cgu(url, params=None, headers=None):
    assert headers["chave-api-dados"] == "teste"
    p = params or {}
    if p["pagina"] > 1:
        raise comum.SemDados(url)
    if url.endswith("/convenios"):
        return [{"dimConvenio": {"numero": "900123", "objeto": "Pavimentação de vias"}, "orgao": {"nome": "Ministério das Cidades"},
                 "situacao": "EM EXECUÇÃO", "valor": 500000, "valorLiberado": 250000,
                 "dataInicioVigencia": "2024-05-01", "dataFinalVigencia": "2026-05-01"}]
    if p["mesAno"] in ("202501", "202502"):
        return [{"valor": 1200000.5, "quantidadeBeneficiados": 1800}]
    raise comum.SemDados(url)


def main():
    SAIDA.mkdir(parents=True, exist_ok=True)
    import shutil
    shutil.rmtree(SAIDA, ignore_errors=True)
    SAIDA.mkdir(parents=True)
    for m in (siconfi, pncp, cgu, transferencias, despesas, coletar_tudo):
        if hasattr(m, "PASTA_DADOS"):
            m.PASTA_DADOS = SAIDA
    siconfi.get_json = falso_siconfi
    pncp.get_json = falso_pncp
    cgu.get_json = falso_cgu
    transferencias.get_json = falso_transf
    despesas.PAUSA = 0
    amostras = {"prefeitura": despesas.ler_tabela((RAIZ / "testes/fixtures/fator_despesa_prefeitura.html").read_text(encoding="utf-8")),
                "camara": despesas.ler_tabela((RAIZ / "testes/fixtures/fator_despesa_amostra.html").read_text(encoding="utf-8"))}
    pedidos = []

    def falso_mes(orgao, ano, mes):
        pedidos.append((orgao, ano, mes))
        return [dict(i, data=f"{ano}-{mes:02d}-02") for i in amostras[orgao]] if (ano, mes) == (2025, 9) else []
    despesas.baixar_mes = falso_mes
    os.environ["CGU_API_KEY"] = "teste"
    sys.argv = ["coletar_tudo.py"]
    coletar_tudo.main()

    s = json.loads((SAIDA / "siconfi.json").read_text())
    a = s["anos"]["2025"]
    assert a["rreo_01"]["periodo"] == 4 and len(a["rreo_01"]["linhas"]) == 3, "paginação do Siconfi"
    assert a["rgf_01"]["periodicidade"] == "S", "RGF semestral"
    assert set(s["anos"]) == {"2025"}

    assert a["rgf_01_camara"]["periodicidade"] == "Q", "RGF da Câmara"
    assert s["anos"]["2025"]["rgf_01"]["linhas"][1]["valor"] == 51.37

    t = json.loads((SAIDA / "transferencias.json").read_text())
    assert t["serie"] == [
        {"mes": "2025-01", "transferencia": "FPM", "valor": 900000.1},
        {"mes": "2025-01", "transferencia": "FUNDEB", "valor": 700000.0},
        {"mes": "2025-02", "transferencia": "FPM", "valor": 950000.0},
    ], t["serie"]

    # leitura do HTML real do portal
    pref = amostras["prefeitura"]
    assert [i["credor"] for i in pref] == ["COELBA - IMOVEL LOCADO", "INSTITUTO MOVIMENTA NORDESTE", "EUSTECLIANA DE SOUZA NASCIMENTO"]
    assert pref[1]["empenhado"] == 249000.0 and pref[1]["contrato"] == "001/2026TERMO" and pref[1]["modalidade"] == "Credenciamento"
    assert pref[2]["documento"] == "xxx.584.365-xx" and pref[2]["elemento"] == "Diarias - Civil"
    assert pref[0]["unidade"] == "SECRETARIA MUNICIPAL DE SAÚDE" and pref[0]["funcao"] == "SAÚDE" and pref[0]["modalidade"] is None
    cam = amostras["camara"]
    assert "&" in cam[1]["objeto"] and cam[1]["empenhado"] == 12345.67
    assert [i["chave"] for i in pref] == ["3_2601020161_15139629000194", "3_2602180001_39514474000197", "6_2609020001_xxx_584_365_xx"]
    # acentos: o portal manda UTF-8 sem avisar; decodificar() não pode estragar
    bruto = (RAIZ / "testes/fixtures/fator_despesa_prefeitura.html").read_bytes()
    assert despesas.ler_tabela(despesas.decodificar(bruto))[0]["unidade"] == "SECRETARIA MUNICIPAL DE SAÚDE"
    # mesmo número de empenho em fundos diferentes não pode ser descartado
    dup = [dict(pref[0], chave="2_X"), dict(pref[0], chave="3_X")]
    despesas.baixar_mes = lambda o, a, m: dup if (a, m) == (2024, 5) else []
    assert despesas.coletar_ano("prefeitura", 2024) == 2
    despesas.baixar_mes = falso_mes
    d25 = json.loads((SAIDA / "despesas" / "prefeitura-2025.json").read_text())
    assert len(d25["empenhos"]) == 3
    ind = json.loads((SAIDA / "despesas" / "indice.json").read_text())
    assert 2025 in ind["orgaos"]["camara"]["anos"]
    assert ("camara", 2025, 12) in pedidos

    p = json.loads((SAIDA / "pncp.json").read_text())
    assert len(p["contratacoes"]) == 1, "filtro de CNPJ"
    assert p["contratacoes"][0]["link"] == f"https://pncp.gov.br/app/editais/{CNPJ}/2025/1"
    assert p["contratos"][0]["documento"] == "***.456.789-**", "CPF mascarado"

    c = json.loads((SAIDA / "cgu.json").read_text())
    assert [x["mes"] for x in c["bolsa_familia"]] == ["2025-01", "2025-02"]
    assert c["convenios"][0]["objeto"] == "Pavimentação de vias"

    m = json.loads((SAIDA / "meta.json").read_text())
    assert all(m["fontes"][k]["ok"] for k in ("siconfi", "transferencias", "despesas", "pncp", "cgu"))

    # sem chave da CGU: as outras fontes seguem e o erro fica registrado
    del os.environ["CGU_API_KEY"]
    coletar_tudo.main()
    m = json.loads((SAIDA / "meta.json").read_text())
    assert m["fontes"]["cgu"]["ok"] is False and m["fontes"]["siconfi"]["ok"] is True
    assert (SAIDA / "cgu.json").exists(), "dados antigos da CGU preservados"
    print("\nTODOS OS TESTES PASSARAM")


if __name__ == "__main__":
    main()
