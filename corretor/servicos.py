"""Inicia e encerra os servidores locais (somente em 127.0.0.1)."""
import subprocess
import time
import urllib.parse
import urllib.request

from . import config

SEM_JANELA = 0x08000000


class ComponenteAusente(Exception):
    pass


def _responde(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=2) as resposta:
            return resposta.status == 200
    except OSError:
        return False


def _aguardar(url: str, processo: subprocess.Popen, segundos: int, nome: str) -> None:
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        if processo.poll() is not None:
            raise RuntimeError(f"{nome} encerrou ao iniciar (código {processo.returncode}).")
        if _responde(url):
            return
        time.sleep(0.5)
    raise RuntimeError(f"{nome} não respondeu em {segundos} segundos.")


class Servico:
    def __init__(self):
        self.processo = None

    def parar(self) -> None:
        if self.processo and self.processo.poll() is None:
            self.processo.terminate()
            try:
                self.processo.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.processo.kill()
        self.processo = None


class LanguageTool(Servico):
    def url(self) -> str:
        return f"http://127.0.0.1:{config.carregar()['porta_languagetool']}"

    def garantir(self) -> str:
        url = self.url()
        if self.processo and self.processo.poll() is None and _responde(f"{url}/v2/languages"):
            return url
        jars = sorted((config.COMPONENTES / "languagetool").glob("**/languagetool-server.jar"))
        javas = sorted((config.COMPONENTES / "java").glob("**/bin/java.exe"))
        if not jars or not javas:
            raise ComponenteAusente("LanguageTool não instalado.")
        self.processo = subprocess.Popen(
            [str(javas[-1]), "-Xmx1g", "-cp", jars[-1].name, "org.languagetool.server.HTTPServer",
             "--port", url.rsplit(":", 1)[1], "--allow-origin", "http://127.0.0.1"],
            cwd=str(jars[-1].parent), creationflags=SEM_JANELA,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        _aguardar(f"{url}/v2/languages", self.processo, 60, "LanguageTool")
        # A primeira consulta carrega as regras de português e pode levar mais de um minuto.
        corpo = urllib.parse.urlencode({"language": "pt-BR", "text": "Olá."}).encode()
        with urllib.request.urlopen(f"{url}/v2/check", corpo, timeout=300):
            pass
        return url


class Modelo(Servico):
    def __init__(self):
        super().__init__()
        self.ultimo_uso = 0.0

    def url(self) -> str:
        return f"http://127.0.0.1:{config.carregar()['porta_modelo']}"

    def garantir(self) -> str:
        self.ultimo_uso = time.monotonic()
        url = self.url()
        if self.processo and self.processo.poll() is None:
            return url
        cfg = config.carregar()
        executaveis = sorted((config.COMPONENTES / "llama").glob("**/llama-server.exe"))
        modelos = sorted((config.COMPONENTES / "modelo").glob("*.gguf"))
        if not executaveis or not modelos:
            raise ComponenteAusente("Modelo de reformulação não instalado.")
        self.processo = subprocess.Popen(
            [str(executaveis[-1]), "-m", str(modelos[-1]), "--host", "127.0.0.1",
             "--port", url.rsplit(":", 1)[1], "--ctx-size", "4096", "--parallel", "1", "--threads", str(cfg["threads_modelo"])],
            creationflags=SEM_JANELA, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        _aguardar(f"{url}/health", self.processo, 120, "Modelo")
        return url

    def marcar_uso(self) -> None:
        self.ultimo_uso = time.monotonic()

    def liberar_se_ocioso(self) -> None:
        minutos = config.carregar()["minutos_para_liberar_modelo"]
        if self.processo and time.monotonic() - self.ultimo_uso > minutos * 60:
            self.parar()
