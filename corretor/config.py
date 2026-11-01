"""Caminhos e configuração do programa."""
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "dados"
COMPONENTES = RAIZ / "componentes"
VERSOES = COMPONENTES / "versoes.json"

PADRAO = {
    "atalhos": {
        "corrigir": ["ctrl+shift+y", "ctrl+shift+1"],
        "reformular": ["ctrl+shift+u", "ctrl+shift+2"],
        "ligar_digitacao": ["ctrl+shift+f"],
        "desligar_digitacao": ["ctrl+shift+g"],
    },
    "barra_ligada": True,
    "barra_posicao": None,
    "porta_languagetool": 18765,
    "porta_modelo": 18766,
    "threads_modelo": 4,
    "minutos_para_liberar_modelo": 10,
    "url_manifesto": "https://github.com/drfilipeferreirasantana/corretor-texto/releases/download/componentes/manifesto.json",
    "digitacao_ligada": False,
    "digitacao_janelas": ["WhatsApp", "Telegram", "Messenger", "Instagram", "Microsoft Teams", "Slack"],
}


def carregar() -> dict:
    config = dict(PADRAO)
    arquivo = DADOS / "config.json"
    if arquivo.exists():
        config.update(json.loads(arquivo.read_text(encoding="utf-8")))
    return config


def salvar(chave: str, valor) -> None:
    arquivo = DADOS / "config.json"
    atual = json.loads(arquivo.read_text(encoding="utf-8")) if arquivo.exists() else {}
    atual[chave] = valor
    arquivo.write_text(json.dumps(atual, indent=2, ensure_ascii=False), encoding="utf-8")
