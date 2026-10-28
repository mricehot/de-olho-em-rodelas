"""Roda todos os coletores. Se uma fonte falhar, as outras continuam
e o site mostra quando cada fonte foi atualizada pela última vez."""
import json
import sys
import traceback

import cgu
import despesas
import pncp
import siconfi
import transferencias
from comum import CONFIG, PASTA_DADOS, agora, salvar

FONTES = {"siconfi": siconfi, "transferencias": transferencias, "despesas": despesas, "pncp": pncp, "cgu": cgu}


def main():
    try:
        meta = json.loads((PASTA_DADOS / "meta.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        meta = {"fontes": {}}
    meta["municipio"] = CONFIG
    so = set(sys.argv[1:]) or set(FONTES)

    falhas = 0
    for nome, modulo in FONTES.items():
        if nome not in so:
            continue
        estado = meta["fontes"].setdefault(nome, {})
        estado["tentativa"] = agora()
        try:
            modulo.coletar()
            estado.update(ok=True, sucesso=estado["tentativa"], erro=None)
        except Exception as e:  # noqa: BLE001 - registrar e seguir
            falhas += 1
            traceback.print_exc()
            estado.update(ok=False, erro=str(e)[:300])
    salvar("meta.json", meta)
    if falhas == len(so):
        sys.exit(1)


if __name__ == "__main__":
    main()
