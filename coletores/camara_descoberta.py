"""Reconhecimento da API da Câmara Municipal (api.imap.org.br).

Ainda não sabemos os endpoints nem o código do órgão da Câmara de Rodelas,
porque a documentação não abre fora do Brasil/fora de um navegador.
Este script roda no GitHub, baixa o que conseguir e guarda em dados_brutos/
para montarmos o coletor de despesas da Câmara depois. Nunca derruba a coleta.
"""
import json
import re
from pathlib import Path

from comum import RAIZ, agora, sessao

PASTA = RAIZ / "dados_brutos"
SWAGGERS = [
    "https://api.imap.org.br/swagger/v1/swagger.json",
    "https://api.imap.org.br/swagger/v1.0/swagger.json",
    "https://api.imap.org.br/swagger/swagger.json",
]
PAGINAS_CAMARA = [
    "https://transparencia.camararodelas.ba.gov.br/dados-abertos",
    "https://transparencia.camararodelas.ba.gov.br/",
]


def tentar(url):
    try:
        r = sessao.get(url, timeout=60)
        return r.status_code, r.text
    except Exception as e:  # noqa: BLE001
        return None, str(e)


def main():
    PASTA.mkdir(exist_ok=True)
    relatorio = {"quando": agora(), "swagger": None, "pistas_codigo_orgao": [], "tentativas": []}

    for url in SWAGGERS:
        status, texto = tentar(url)
        relatorio["tentativas"].append({"url": url, "status": status})
        if status == 200 and texto.lstrip().startswith("{"):
            (PASTA / "imap-swagger.json").write_text(texto, encoding="utf-8")
            relatorio["swagger"] = url
            break

    scripts = set()
    for url in PAGINAS_CAMARA:
        status, texto = tentar(url)
        relatorio["tentativas"].append({"url": url, "status": status})
        if status != 200:
            continue
        nome = re.sub(r"\W+", "_", url.split("//", 1)[1]).strip("_")[:60]
        (PASTA / f"camara-{nome}.html").write_text(texto, encoding="utf-8")
        for src in re.findall(r'<script[^>]+src="([^"]+)"', texto):
            scripts.add(src if src.startswith("http") else url.split("/", 3)[0] + "//" + url.split("/")[2] + "/" + src.lstrip("/"))

    for src in sorted(scripts)[:15]:
        status, texto = tentar(src)
        if status != 200:
            continue
        for m in re.finditer(r"(?i)(orgao|codigoOrgao|idOrgao|cod_orgao|entidade)\W{0,4}[:=]\W{0,3}(\d{2,6})", texto):
            relatorio["pistas_codigo_orgao"].append({"script": src, "trecho": m.group(0)})
        for m in re.finditer(r"https?://api\.imap\.org\.br[^\"'`\s]*", texto):
            relatorio["pistas_codigo_orgao"].append({"script": src, "url_api": m.group(0)})

    (PASTA / "camara-descoberta.json").write_text(json.dumps(relatorio, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(relatorio, ensure_ascii=False, indent=1)[:3000])


if __name__ == "__main__":
    main()
