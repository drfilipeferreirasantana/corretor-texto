"""Atualização sob demanda. É o único módulo que acessa a internet, e nunca envia texto."""
import hashlib
import json
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

from . import config


def _numero_versao(versao: str) -> tuple[int, ...]:
    return tuple(int(parte) for parte in versao.split("."))


def _exigir_https(url: str) -> None:
    if not url.startswith("https://"):
        raise ValueError(f"Endereço sem HTTPS recusado: {url}")


def versoes_instaladas() -> dict:
    if config.VERSOES.exists():
        return json.loads(config.VERSOES.read_text(encoding="utf-8"))
    return {}


def pendentes(manifesto: dict, instaladas: dict) -> dict:
    return {
        nome: info for nome, info in manifesto.get("componentes", {}).items()
        if nome not in instaladas or _numero_versao(info["versao"]) > _numero_versao(instaladas[nome])
    }


def verificar(url_manifesto: str) -> dict:
    _exigir_https(url_manifesto)
    with urllib.request.urlopen(url_manifesto, timeout=20) as resposta:
        return pendentes(json.load(resposta), versoes_instaladas())


def extrair_com_seguranca(arquivo_zip: Path, destino: Path) -> None:
    """Recusa pacotes que tentem gravar fora da pasta de destino."""
    with zipfile.ZipFile(arquivo_zip) as pacote:
        for nome in pacote.namelist():
            caminho = PurePosixPath(nome.replace("\\", "/"))
            if caminho.is_absolute() or ".." in caminho.parts or ":" in nome:
                raise ValueError(f"Pacote com caminho inseguro: {nome}")
        pacote.extractall(destino)


def _baixar(url: str, destino: Path, progresso=None) -> str:
    _exigir_https(url)
    resumo = hashlib.sha256()
    with urllib.request.urlopen(url, timeout=60) as resposta, destino.open("wb") as saida:
        total = int(resposta.headers.get("Content-Length") or 0)
        baixado = 0
        while bloco := resposta.read(1024 * 1024):
            saida.write(bloco)
            resumo.update(bloco)
            baixado += len(bloco)
            if progresso:
                progresso(baixado, total)
    return resumo.hexdigest()


def instalar(nome: str, info: dict, progresso=None) -> None:
    """Baixa, confere o SHA-256 e só então troca o componente. Em caso de erro, o atual é mantido."""
    config.COMPONENTES.mkdir(parents=True, exist_ok=True)
    pasta_final = config.COMPONENTES / ("programa_pendente" if nome == "programa" else nome)
    with tempfile.TemporaryDirectory(dir=config.COMPONENTES) as temporaria:
        temporaria = Path(temporaria)
        arquivo_nome = PurePosixPath(info["url"].split("?")[0]).name
        baixado = temporaria / arquivo_nome
        if _baixar(info["url"], baixado, progresso) != info["sha256"].lower():
            raise ValueError(f"{nome}: o arquivo baixado não confere com o SHA-256 do manifesto.")
        novo = temporaria / "novo"
        novo.mkdir()
        if arquivo_nome.lower().endswith(".zip"):
            extrair_com_seguranca(baixado, novo)
        else:
            shutil.move(str(baixado), novo / arquivo_nome)
        if pasta_final.exists():
            shutil.rmtree(pasta_final)
        shutil.move(str(novo), pasta_final)
    instaladas = versoes_instaladas()
    instaladas[nome] = info["versao"]
    config.VERSOES.write_text(json.dumps(instaladas, indent=2), encoding="utf-8")


def aplicar_programa_pendente() -> bool:
    """Chamado ao iniciar, antes de carregar o programa, porque um módulo em uso não deve ser trocado."""
    pendente = config.COMPONENTES / "programa_pendente" / "corretor"
    if not pendente.exists():
        return False
    shutil.copytree(pendente, config.RAIZ / "corretor", dirs_exist_ok=True)
    shutil.rmtree(pendente.parent)
    return True
