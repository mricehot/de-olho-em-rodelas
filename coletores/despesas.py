"""Despesas detalhadas (cada empenho) da Prefeitura e da Câmara.

Fonte: portal "Transparência 131" da Fator Sistemas, que a Prefeitura e a
Câmara de Rodelas usam para publicar a execução da despesa:
  https://transparencia.fatorsistemas.com.br/dados/despesa.php?id=pm_rodelas
  https://transparencia.fatorsistemas.com.br/dados/despesa.php?id=cm_rodelas

Não há API oficial: lemos a mesma tabela que o portal carrega
(carregaDespesa.php), um mês por vez, com pausa entre as consultas.
O próprio portal já mascara o CPF de pessoas físicas (xxx.123.456-xx).

Saída: site/data/despesas/<orgao>-<ano>.json (um arquivo por ano, para o site
carregar só o ano escolhido) e site/data/despesas/indice.json.
"""
import calendar
import html
import json
import re
import time
from datetime import date
from urllib.parse import urlencode

from comum import CONFIG, PASTA_DADOS, agora, sessao

BASE = "https://transparencia.fatorsistemas.com.br/dados"
ORGAOS = {
    "prefeitura": {"id": "pm_rodelas", "unidade_gestora": 0, "nome": "Prefeitura (consolidado)"},
    "camara": {"id": "cm_rodelas", "unidade_gestora": 1, "nome": "Câmara Municipal"},
}
PAUSA = 2


def pasta():
    p = PASTA_DADOS / "despesas"
    p.mkdir(parents=True, exist_ok=True)
    return p


def url_mes(orgao, ano, mes):
    o = ORGAOS[orgao]
    ultimo = calendar.monthrange(ano, mes)[1]
    params = {
        "id": o["id"], "unidade_gestora": o["unidade_gestora"], "tipo": 1,
        "fornecedor": "", "cpfcnpj": "",
        "data_publicacao": f"01/{mes:02d}/{ano}", "data_publicacao_fim": f"{ultimo:02d}/{mes:02d}/{ano}",
        "Numero": "", "NProcesso": "", "funcao": -1, "subfuncao": -1, "Despesa": "", "Historico": "",
        "fonte": -1, "acao": -1, "Valor": "", "modalidade": -1, "Categoria_Economica": -1,
        "Grupo_Despesa": -1, "Modalidade_Aplicacao": -1, "Elemento": -1, "Subelemento": -1,
        "nContrato": "", "tipoFase": -1, "unidOrc": -1,
    }
    return f"{BASE}/carregaDespesa.php?{urlencode(params)}"


# ---------- leitura do HTML ----------

def texto(fragmento):
    t = re.sub(r"<[^>]+>", " ", fragmento)
    t = html.unescape(t).replace("\xa0", " ")
    return re.sub(r"\s+", " ", t).strip()


def numero_br(t):
    t = re.sub(r"[^\d,\-]", "", t or "")
    if not t:
        return 0.0
    return float(t.replace(",", "."))


def data_iso(t):
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", t or "")
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None


def sem_codigo(t):
    """'33901400 - Diarias - Civil ( 2026 )' -> 'Diarias - Civil'"""
    t = re.sub(r"\(\s*\d{4}\s*\)\s*$", "", t or "").strip()
    t = re.sub(r"^\s*\d+\s*-\s*", "", t)
    return re.sub(r"\s+-\s+", " - ", re.sub(r"\s{2,}", " ", t)).strip(" -") or None


ROTULO = re.compile(r"<(?:strong|b)>\s*([^<:]{2,40}?)\s*:\s*</(?:strong|b)>(.*?)(?=<(?:strong|b)>[^<]{2,40}:\s*</(?:strong|b)>|</p>|</div>)", re.S | re.I)


def campos_do_detalhe(bloco):
    campos = {}
    for rotulo, valor in ROTULO.findall(bloco):
        chave = texto(rotulo).lower()
        if chave not in campos:
            campos[chave] = texto(valor)
    return campos


def ler_tabela(pagina):
    """Devolve a lista de empenhos de uma resposta do carregaDespesa.php."""
    itens = []
    partes = re.split(r"<tr data-dialog-id=", pagina)[1:]
    for parte in partes:
        tds = [texto(td) for td in re.findall(r"<td[^>]*>(.*?)</td>", parte.split("</tr>", 1)[0], re.S)]
        if len(tds) < 7:
            continue
        detalhe = campos_do_detalhe(parte.split("</tr>", 1)[1] if "</tr>" in parte else "")
        doc = detalhe.get("cnpj") or detalhe.get("cpf") or detalhe.get("cpf/cnpj")
        contrato = detalhe.get("nº contrato", "").strip(" -") or None
        licitacao = detalhe.get("processo licitatório", "").strip(" -") or None
        itens.append({
            "data": data_iso(tds[0]),
            "empenho": tds[1],
            "fase": tds[2].title(),
            "credor": tds[3],
            "documento": doc or None,
            "unidade": sem_codigo(detalhe.get("unidade orçamentária")),
            "objeto": detalhe.get("bem /serviço prestado") or detalhe.get("bem/serviço prestado") or None,
            "funcao": (sem_codigo(detalhe.get("função")) or "").upper() or None,
            "elemento": sem_codigo(detalhe.get("elemento de despesa")),
            "modalidade": (detalhe.get("modalidade") or None) if detalhe.get("modalidade") != "Não se Aplica" else None,
            "contrato": contrato,
            "licitacao": licitacao,
            "processo": detalhe.get("nº do processo") or None,
            "empenhado": numero_br(tds[4]),
            "liquidado": numero_br(tds[5]),
            "pago": numero_br(tds[6]),
        })
    return itens


# ---------- coleta ----------

def baixar_mes(orgao, ano, mes):
    time.sleep(PAUSA)
    for tentativa in range(3):
        try:
            r = sessao.get(url_mes(orgao, ano, mes), timeout=120)
            r.raise_for_status()
            r.encoding = r.encoding or "utf-8"
            if "<table" not in r.text:
                raise RuntimeError("resposta sem tabela")
            return ler_tabela(r.text)
        except Exception as e:  # noqa: BLE001
            if tentativa == 2:
                raise
            print(f"  ! {orgao} {mes:02d}/{ano}: {e}; tentando de novo")
            time.sleep(10 * (tentativa + 1))
    return []


def arquivo(orgao, ano):
    return pasta() / f"{orgao}-{ano}.json"


def anos_a_atualizar(orgao):
    hoje = date.today()
    anos = []
    for ano in range(CONFIG["ano_inicial"], hoje.year + 1):
        recente = ano == hoje.year or (ano == hoje.year - 1 and hoje.month <= 2)
        if recente or not arquivo(orgao, ano).exists():
            anos.append(ano)
    return anos


def coletar_ano(orgao, ano):
    hoje = date.today()
    ultimo_mes = hoje.month if ano == hoje.year else 12
    itens = []
    for mes in range(1, ultimo_mes + 1):
        lote = baixar_mes(orgao, ano, mes)
        print(f"  {orgao} {mes:02d}/{ano}: {len(lote)} empenhos")
        itens += lote
    vistos, unicos = set(), []
    for i in sorted(itens, key=lambda x: (x["data"] or "", x["empenho"]), reverse=True):
        chave = (i["empenho"], i["data"], i["credor"])
        if chave not in vistos:
            vistos.add(chave)
            unicos.append(i)
    arquivo(orgao, ano).write_text(json.dumps({
        "orgao": orgao, "ano": ano, "atualizado_em": agora(),
        "fonte": f"{BASE}/despesa.php?id={ORGAOS[orgao]['id']}",
        "empenhos": unicos,
    }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return len(unicos)


def gravar_indice():
    indice = {"atualizado_em": agora(), "orgaos": {}}
    for orgao, info in ORGAOS.items():
        anos = sorted(int(p.stem.split("-")[1]) for p in pasta().glob(f"{orgao}-*.json"))
        indice["orgaos"][orgao] = {"nome": info["nome"], "anos": anos,
                                   "fonte": f"{BASE}/despesa.php?id={info['id']}"}
    (pasta() / "indice.json").write_text(json.dumps(indice, ensure_ascii=False, indent=1), encoding="utf-8")


def coletar():
    print("Despesas detalhadas (Fator Sistemas)")
    total = 0
    falhas = []
    for orgao in ORGAOS:
        for ano in anos_a_atualizar(orgao):
            try:
                total += coletar_ano(orgao, ano)
            except Exception as e:  # noqa: BLE001
                falhas.append(f"{orgao} {ano}: {e}")
                print(f"  ! {orgao} {ano} falhou: {e}")
    gravar_indice()
    if falhas and total == 0:
        raise RuntimeError("; ".join(falhas)[:300])


if __name__ == "__main__":
    coletar()
