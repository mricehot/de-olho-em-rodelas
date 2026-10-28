"""Funções compartilhadas pelos coletores."""
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parent.parent
PASTA_DADOS = RAIZ / "site" / "data"
CONFIG = json.loads((RAIZ / "config.json").read_text(encoding="utf-8"))

sessao = requests.Session()
sessao.headers["User-Agent"] = "transparencia-rodelas (projeto cidadao; github)"


class SemDados(Exception):
    """A API respondeu, mas não há registros (ex.: HTTP 204)."""


def get_json(url, params=None, headers=None, tentativas=4, pausa=5):
    """GET com novas tentativas. Devolve o JSON, ou lança SemDados em 204/404."""
    for i in range(tentativas):
        try:
            r = sessao.get(url, params=params, headers=headers, timeout=60)
        except requests.RequestException as e:
            if i == tentativas - 1:
                raise
            print(f"  ! erro de rede ({e}); tentando de novo")
            time.sleep(pausa * (i + 1))
            continue
        if r.status_code in (204, 404):
            raise SemDados(url)
        if r.status_code == 429 or r.status_code >= 500:
            espera = pausa * (i + 2) * 2
            print(f"  ! HTTP {r.status_code}; aguardando {espera}s")
            time.sleep(espera)
            continue
        r.raise_for_status()
        if not r.content.strip():
            raise SemDados(url)
        return r.json()
    raise RuntimeError(f"Falhou depois de {tentativas} tentativas: {url}")


def salvar(nome, dados):
    PASTA_DADOS.mkdir(parents=True, exist_ok=True)
    caminho = PASTA_DADOS / nome
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  -> {caminho.relative_to(RAIZ)}")


def agora():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def mascarar_cpf(doc):
    """Mostra só os 6 dígitos do meio, como faz o Portal da Transparência."""
    d = "".join(c for c in str(doc or "") if c.isdigit())
    if len(d) == 11:
        return f"***.{d[3:6]}.{d[6:9]}-**"
    return doc
