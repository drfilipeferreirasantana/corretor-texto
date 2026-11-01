"""Regras próprias do escritório, aplicadas antes do LanguageTool."""
import json
import re

from . import config


def carregar() -> dict:
    atualizado = config.COMPONENTES / "regras" / "regras.json"
    arquivo = atualizado if atualizado.exists() else config.DADOS / "regras.json"
    regras = json.loads(arquivo.read_text(encoding="utf-8"))
    pessoal = config.DADOS / "meu_dicionario.json"
    if pessoal.exists():
        regras["ignorar"] = regras.get("ignorar", []) + json.loads(pessoal.read_text(encoding="utf-8"))
    return regras


def _manter_caixa(original: str, nova: str) -> str:
    if original.isupper() and len(original) > 1:
        return nova.upper()
    if original[:1].isupper():
        return nova[:1].upper() + nova[1:]
    return nova


def aplicar(texto: str, regras: dict) -> tuple[str, list[str]]:
    """Devolve o texto com as regras aplicadas e o motivo de cada troca."""
    motivos = []
    for regra in regras.get("substituicoes", []):
        padrao = re.compile(regra["padrao"], re.IGNORECASE)

        def trocar(achado):
            nova = _manter_caixa(achado.group(0), achado.expand(regra["troca"]))
            motivos.append(f"{achado.group(0)} → {nova}: {regra['motivo']}")
            return nova

        texto = padrao.sub(trocar, texto)
    return texto, motivos
