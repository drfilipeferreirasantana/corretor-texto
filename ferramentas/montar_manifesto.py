"""Gera o manifesto de atualização a partir dos arquivos prontos em uma pasta.

Uso: python montar_manifesto.py PASTA URL_BASE nome=versao=arquivo ...
"""
import hashlib
import json
import sys
from pathlib import Path


def resumo(arquivo: Path) -> str:
    calculo = hashlib.sha256()
    with arquivo.open("rb") as entrada:
        while bloco := entrada.read(1024 * 1024):
            calculo.update(bloco)
    return calculo.hexdigest()


def montar(pasta: Path, url_base: str, itens: list[str]) -> dict:
    componentes = {}
    for item in itens:
        nome, versao, arquivo = item.split("=", 2)
        componentes[nome] = {
            "versao": versao,
            "url": f"{url_base}/{arquivo}",
            "sha256": resumo(pasta / arquivo),
            "tamanho": (pasta / arquivo).stat().st_size,
        }
    return {"componentes": componentes}


if __name__ == "__main__":
    pasta = Path(sys.argv[1])
    manifesto = montar(pasta, sys.argv[2], sys.argv[3:])
    (pasta / "manifesto.json").write_text(json.dumps(manifesto, indent=2), encoding="utf-8")
