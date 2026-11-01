"""Correção ao digitar. O texto digitado fica só na memória e é descartado a cada mensagem."""
import json
import queue
import re
import threading
from dataclasses import dataclass

from . import config, correcao, janelas, regras as modulo_regras
from .regras import _manter_caixa

_NUCLEO = re.compile(r"^([^\w]*)([^\W\d_]+(?:[-'][^\W\d_]+)*)([^\w]*)$", re.UNICODE)
_ABREVIACOES = {"dr", "dra", "sr", "sra", "srta", "prof", "profa", "art", "arts", "av", "n", "nº",
                "fls", "pág", "p", "etc", "ex", "exa", "exmo", "exma", "v"}
_TAMANHO_MINIMO_CONSULTA = 4


@dataclass
class Acao:
    apagar: int
    escrever: str


@dataclass
class Consulta:
    numero: int
    nucleo: str


class Motor:
    """Regras de correção, sem acesso ao teclado, para poderem ser testadas."""

    def __init__(self, correcoes: dict[str, str], ignorar: list[str] | None = None):
        self.correcoes = {chave.casefold(): valor for chave, valor in correcoes.items()}
        self.ignorar = {termo.casefold() for termo in ignorar or []}
        self.trava = threading.RLock()
        self.nova_mensagem()

    def _limpar(self):
        self.token = ""
        self.desfazer = None
        self.pular_proximo = False
        self.consulta = None
        self.numero_consulta = getattr(self, "numero_consulta", 0)

    def nova_mensagem(self):
        """Enter, clique ou troca de janela: o próximo texto é tratado como início de frase."""
        with self.trava:
            self._limpar()
            self.inicio_frase = True

    def cursor_movido(self):
        """Setas, Ctrl+algo: posição desconhecida, então não coloca maiúscula."""
        with self.trava:
            self._limpar()
            self.inicio_frase = False

    def apagar(self) -> Acao | None:
        with self.trava:
            desfazer, self.desfazer = self.desfazer, None
            self.consulta = None
            if desfazer:
                corrigido, original, nucleo = desfazer
                self.token = original
                self.pular_proximo = True
                if nucleo:
                    self.ignorar.add(nucleo.casefold())
                return Acao(len(corrigido), original)
            if self.token:
                self.token = self.token[:-1]
            else:
                self.inicio_frase = False
            return None

    def digitar(self, caractere: str) -> tuple[Acao | None, Consulta | None]:
        with self.trava:
            self.desfazer = None
            if self.consulta:
                self.consulta["depois"] += caractere
            if not caractere.isspace():
                self.token += caractere
                return None, None
            token, self.token = self.token, ""
            if not token:
                return None, None
            return self._avaliar(token, caractere)

    def _avaliar(self, token: str, espaco: str) -> tuple[Acao | None, Consulta | None]:
        pular, self.pular_proximo = self.pular_proximo, False
        inicio, self.inicio_frase = self.inicio_frase, self._termina_frase(token)
        achado = _NUCLEO.match(token)
        if not achado or pular:
            return None, None
        antes, nucleo, depois = achado.groups()
        chave = nucleo.casefold()
        if chave in self.ignorar:
            return None, None
        novo = _manter_caixa(nucleo, self.correcoes[chave]) if chave in self.correcoes else nucleo
        if inicio and novo[0].islower():
            novo = novo[0].upper() + novo[1:]

        acao = None
        if novo != nucleo:
            self.consulta = None  # a tela mudou, e a contagem de uma resposta pendente deixaria de valer
            corrigido = antes + novo + depois
            self.desfazer = (corrigido, token, nucleo if chave in self.correcoes else None)
            acao = Acao(len(token) + 1, corrigido + espaco)
        consulta = None
        nome_proprio = nucleo[0].isupper() and not inicio
        if chave not in self.correcoes and len(nucleo) >= _TAMANHO_MINIMO_CONSULTA and not nome_proprio:
            self.numero_consulta += 1
            self.consulta = {"numero": self.numero_consulta, "nucleo": nucleo, "antes": antes, "fim": depois,
                             "espaco": espaco, "escrito": antes + novo + depois + espaco, "depois": ""}
            consulta = Consulta(self.numero_consulta, nucleo)
        return acao, consulta

    def _termina_frase(self, token: str) -> bool:
        if not token.endswith((".", "!", "?", "…")):
            return False
        achado = _NUCLEO.match(token)
        return not (achado and token.endswith(".") and achado.group(2).casefold() in _ABREVIACOES)

    def resposta_consulta(self, numero: int, sugestao: str | None) -> Acao | None:
        """Resposta do LanguageTool, que pode chegar quando já se digitou mais."""
        with self.trava:
            consulta = self.consulta
            if not sugestao or not consulta or consulta["numero"] != numero:
                return None
            self.consulta = None
            nucleo_escrito = consulta["escrito"].removeprefix(consulta["antes"])
            maiuscula = nucleo_escrito[:1].isupper()
            nova = sugestao[0].upper() + sugestao[1:] if maiuscula else sugestao
            corrigido = consulta["antes"] + nova + consulta["fim"]
            if not consulta["depois"]:
                self.desfazer = (corrigido, consulta["escrito"].rstrip(), consulta["nucleo"])
            return Acao(len(consulta["escrito"]) + len(consulta["depois"]),
                        corrigido + consulta["espaco"] + consulta["depois"])


def janela_permitida(titulo: str, permitidos: list[str]) -> bool:
    titulo = titulo.casefold()
    return any(item.casefold() in titulo for item in permitidos)


def consultar_ortografia(palavra: str, url: str) -> str | None:
    for achado in correcao.consultar(palavra, url):
        rule = achado.get("rule", {})
        if rule.get("issueType") == "misspelling" and achado.get("offset") == 0 \
                and achado.get("length") == len(palavra) and achado.get("replacements"):
            return achado["replacements"][0]["value"]
    return None


class CorrecaoAoDigitar:
    """Liga o gancho do teclado ao motor. Só atua nas janelas de chat configuradas."""

    def __init__(self, linguagem):
        self.linguagem = linguagem
        self.fila_acoes = queue.Queue()
        self.fila_consultas = queue.Queue()
        self.gancho = None
        self.janela_atual = None

    def _motor_novo(self) -> Motor:
        atualizado = config.COMPONENTES / "regras" / "correcoes_digitacao.json"
        arquivo = atualizado if atualizado.exists() else config.DADOS / "correcoes_digitacao.json"
        correcoes = json.loads(arquivo.read_text(encoding="utf-8"))
        return Motor(correcoes, modulo_regras.carregar().get("ignorar", []))

    def ligar(self) -> None:
        if self.gancho:
            return
        self.motor = self._motor_novo()
        self.permitidos = config.carregar()["digitacao_janelas"]
        self.gancho = janelas.GanchoEntrada(self._ao_teclar, self._ao_clicar)
        self.gancho.start()
        threading.Thread(target=self._enviar, daemon=True).start()
        threading.Thread(target=self._consultar, daemon=True).start()

    def desligar(self) -> None:
        if self.gancho:
            self.gancho.encerrar()
            self.gancho = None
            self.motor.nova_mensagem()
            self.fila_acoes.put(None)
            self.fila_consultas.put(None)

    def _ativo(self) -> bool:
        janela = janelas.janela_ativa()
        if janela != self.janela_atual:
            self.janela_atual = janela
            self.motor.nova_mensagem()
        return janela_permitida(janelas.titulo_janela(janela), self.permitidos)

    def _ao_clicar(self) -> None:
        self.motor.nova_mensagem()

    def _ao_teclar(self, tipo: str, caractere: str | None) -> None:
        if not self._ativo():
            return
        if tipo == "enter":
            self.motor.nova_mensagem()
        elif tipo == "mover":
            self.motor.cursor_movido()
        elif tipo == "apagar":
            acao = self.motor.apagar()
            if acao:
                self.fila_acoes.put(acao)
        elif tipo == "caractere":
            acao, consulta = self.motor.digitar(caractere)
            if acao:
                self.fila_acoes.put(acao)
            if consulta:
                self.fila_consultas.put(consulta)

    def _enviar(self) -> None:
        while (acao := self.fila_acoes.get()) is not None:
            janelas.substituir_digitado(acao.apagar, acao.escrever)

    def _consultar(self) -> None:
        while (consulta := self.fila_consultas.get()) is not None:
            processo = self.linguagem.processo
            if not processo or processo.poll() is not None:
                continue
            try:
                sugestao = consultar_ortografia(consulta.nucleo, self.linguagem.url())
            except OSError:
                continue
            acao = self.motor.resposta_consulta(consulta.numero, sugestao)
            if acao:
                self.fila_acoes.put(acao)
