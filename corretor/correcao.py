"""Correção: regras próprias + LanguageTool."""
import json
import urllib.parse
import urllib.request

from . import regras as modulo_regras
from .servicos import ComponenteAusente, LanguageTool


def aplicar_achados(texto: str, achados: list[dict], ignorar: list[str]) -> tuple[str, list[str]]:
    """Aplica as sugestões. O LanguageTool conta posições em UTF-16, e emojis ocupam duas."""
    ignorados = {termo.casefold() for termo in ignorar}
    dados = texto.encode("utf-16-le")
    motivos = []
    for achado in sorted(achados, key=lambda a: a["offset"], reverse=True):
        inicio, fim = achado["offset"] * 2, (achado["offset"] + achado["length"]) * 2
        trecho = dados[inicio:fim].decode("utf-16-le")
        if trecho.casefold() in ignorados or not achado.get("replacements"):
            continue
        nova = achado["replacements"][0]["value"]
        dados = dados[:inicio] + nova.encode("utf-16-le") + dados[fim:]
        motivos.insert(0, f"{trecho} → {nova}: {achado.get('message', '')}")
    return dados.decode("utf-16-le"), motivos


def consultar(texto: str, url: str) -> list[dict]:
    corpo = urllib.parse.urlencode({"language": "pt-BR", "text": texto}).encode()
    with urllib.request.urlopen(f"{url}/v2/check", corpo, timeout=60) as resposta:
        return json.load(resposta)["matches"]


def corrigir(texto: str, servico: LanguageTool) -> dict:
    regras = modulo_regras.carregar()
    corrigido, motivos = modulo_regras.aplicar(texto, regras)
    aviso = ""
    try:
        url = servico.garantir()
        corrigido, motivos_lt = aplicar_achados(corrigido, consultar(corrigido, url), regras.get("ignorar", []))
        motivos += motivos_lt
    except ComponenteAusente:
        aviso = "Apenas as regras do escritório foram aplicadas: o LanguageTool não está instalado."
    return {"texto": corrigido, "motivos": motivos, "avisos": [aviso] if aviso else []}
