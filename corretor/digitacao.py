"""Correção ao digitar. O texto digitado fica só na memória e é descartado a cada mensagem."""
import json
import queue
import re
import threading
import time
from dataclasses import dataclass

from . import config, correcao, janelas, regras as modulo_regras
from .regras import _manter_caixa

_NUCLEO = re.compile(r"^([^\w]*)([^\W\d_]+(?:[-'][^\W\d_]+)*)([^\w]*)$", re.UNICODE)
_ABREVIACOES = {"dr", "dra", "sr", "sra", "srta", "prof", "profa", "art", "arts", "av", "n", "nº",
                "fls", "pág", "p", "etc", "ex", "exa", "exmo", "exma", "v"}
_TAMANHO_MINIMO_CONSULTA = 4
_MEMORIA_CONTEXTO = 120
_MAXIMO_PENDENTES = 8


@dataclass
class Acao:
    apagar: int
    escrever: str
    enter: bool = False


@dataclass
class Consulta:
    numero: int
    nucleo: str


class Motor:
    """Regras de correção, sem acesso ao teclado, para poderem ser testadas."""

    def __init__(self, correcoes: dict[str, str], ignorar: list[str] | None = None, regras: dict | None = None,
                 pontuar: bool = False):
        self.correcoes = {chave.casefold(): valor for chave, valor in correcoes.items()}
        self.ignorar = {termo.casefold() for termo in ignorar or []}
        self.regras = regras
        self.pontuar = pontuar
        self.trava = threading.RLock()
        self.nova_mensagem()

    def _limpar(self):
        self.token = ""
        self.recente = ""
        self.palavras = 0
        self.desfazer = None
        self.pular_proximo = False
        self.pendentes = {}
        self.numero_consulta = getattr(self, "numero_consulta", 0)

    def _ajustar_pendentes(self, acao: Acao, somente_antes_de: int | None = None, exceto: int | None = None) -> None:
        """A tela mudou à direita das palavras aguardando resposta, e a contagem delas precisa acompanhar."""
        for numero, consulta in list(self.pendentes.items()):
            if numero == exceto or (somente_antes_de is not None and numero >= somente_antes_de):
                continue
            depois = consulta["depois"]
            if acao.apagar > len(depois):
                del self.pendentes[numero]  # a própria palavra mudou
            else:
                consulta["depois"] = depois[:len(depois) - acao.apagar] + acao.escrever
                if len(consulta["depois"]) > _MEMORIA_CONTEXTO:
                    del self.pendentes[numero]

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
            self._ajustar_pendentes(Acao(1, ""))
            if desfazer:
                corrigido, original, nucleo = desfazer
                self.token = original
                self.recente = ""
                self.pular_proximo = True
                if nucleo:
                    self.ignorar.add(nucleo.casefold())
                acao = Acao(len(corrigido), original)
                self._ajustar_pendentes(acao)
                return acao
            self.recente = self.recente[:-1]
            if self.token:
                self.token = self.token[:-1]
            else:
                self.inicio_frase = False
            return None

    def digitar(self, caractere: str) -> tuple[Acao | None, Consulta | None]:
        with self.trava:
            self.desfazer = None
            self.recente = (self.recente + caractere)[-_MEMORIA_CONTEXTO:]
            self._ajustar_pendentes(Acao(0, caractere))
            if not caractere.isspace():
                self.token += caractere
                return None, None
            token, self.token = self.token, ""
            if not token:
                return None, None
            self.palavras += 1
            acao, consulta = self._avaliar(token, caractere)
            if acao:
                self._ajustar_pendentes(acao, exceto=consulta.numero if consulta else None)
            return self._aplicar_contexto(acao, consulta)

    def _aplicar_contexto(self, acao: Acao | None, consulta: Consulta | None) -> tuple[Acao | None, Consulta | None]:
        """Regras que olham as palavras anteriores, como "você e uma" → "você é uma"."""
        antes = self.recente
        if acao:
            if acao.apagar > len(antes):
                self.recente = ""
                return acao, consulta
            antes_token = antes[:len(antes) - acao.apagar] + acao.escrever
        else:
            antes_token = antes
        if not self.regras:
            self.recente = antes_token
            return acao, consulta
        novo = modulo_regras.aplicar(antes_token, self.regras)[0]
        self.recente = novo[-_MEMORIA_CONTEXTO:]
        if novo == antes_token:
            return acao, consulta
        def inicio_igual(a: str, b: str) -> int:
            comum = 0
            while comum < min(len(a), len(b)) and a[comum] == b[comum]:
                comum += 1
            return comum

        mudanca = inicio_igual(antes_token, novo)
        self._ajustar_pendentes(Acao(len(antes_token) - mudanca, novo[mudanca:]))
        if consulta and consulta.numero not in self.pendentes:
            consulta = None
        comum = inicio_igual(antes, novo)
        self.desfazer = (novo[comum:-1], antes[comum:-1], None)
        return Acao(len(antes) - comum, novo[comum:]), consulta

    def finalizar(self) -> Acao | None:
        """Antes de enviar: corrige a última palavra e, em mensagens de 4 palavras ou mais, coloca o ponto."""
        with self.trava:
            token = self.token
            palavras = self.palavras + (1 if token else 0)
            acao = None
            if token:
                inicio = self.inicio_frase
                avaliada, _ = self._avaliar(token, " ")
                self.inicio_frase = inicio
                novo = avaliada.escrever[:-1] if avaliada else token
                apagar = len(token)
            else:
                ultimo = self.recente.rstrip().rsplit(None, 1)[-1] if self.recente.strip() else ""
                novo, apagar = ultimo, len(self.recente) - len(self.recente.rstrip())
            achado = _NUCLEO.match(novo)
            final = novo
            if self.pontuar and palavras >= 4 and achado and not achado.group(3):
                final = novo + "."
            if token and final != token:
                acao = Acao(apagar, final, enter=True)
            elif not token and final != novo:
                acao = Acao(apagar, ".", enter=True)
            self.nova_mensagem()
            return acao

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
            corrigido = antes + novo + depois
            self.desfazer = (corrigido, token, nucleo if chave in self.correcoes else None)
            acao = Acao(len(token) + 1, corrigido + espaco)
        consulta = None
        nome_proprio = nucleo[0].isupper() and not inicio
        if chave not in self.correcoes and len(nucleo) >= _TAMANHO_MINIMO_CONSULTA and not nome_proprio:
            self.numero_consulta += 1
            self.pendentes[self.numero_consulta] = {
                "nucleo": nucleo, "antes": antes, "fim": depois, "espaco": espaco,
                "escrito": antes + novo + depois + espaco, "depois": "",
            }
            if len(self.pendentes) > _MAXIMO_PENDENTES:
                del self.pendentes[min(self.pendentes)]
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
            if not sugestao:
                self.pendentes.pop(numero, None)
                return None
            consulta = self.pendentes.pop(numero, None)
            if not consulta:
                return None
            nucleo_escrito = consulta["escrito"].removeprefix(consulta["antes"])
            maiuscula = nucleo_escrito[:1].isupper()
            nova = sugestao[0].upper() + sugestao[1:] if maiuscula else sugestao
            corrigido = consulta["antes"] + nova + consulta["fim"]
            if not consulta["depois"]:
                self.desfazer = (corrigido, consulta["escrito"].rstrip(), consulta["nucleo"])
            acao = Acao(len(consulta["escrito"]) + len(consulta["depois"]),
                        corrigido + consulta["espaco"] + consulta["depois"])
            self._ajustar_pendentes(acao, somente_antes_de=numero)
            if acao.apagar <= len(self.recente):
                self.recente = self.recente[:len(self.recente) - acao.apagar] + acao.escrever
            else:
                self.recente = ""
            return acao


def janela_permitida(titulo: str, permitidos: list[str]) -> bool:
    titulo = titulo.casefold()
    return any(item.casefold() in titulo for item in permitidos)


def localizar_erros(palavras: list[str], achados: list[dict]) -> dict[int, str]:
    """Liga cada erro do LanguageTool à palavra do lote, pela posição no texto enviado."""
    posicoes, posicao = {}, 0
    for indice, palavra in enumerate(palavras):
        tamanho = len(palavra.encode("utf-16-le")) // 2
        posicoes[(posicao, tamanho)] = indice
        posicao += tamanho + 1
    sugestoes = {}
    for achado in achados:
        indice = posicoes.get((achado.get("offset"), achado.get("length")))
        if indice is not None and achado.get("rule", {}).get("issueType") == "misspelling" and achado.get("replacements"):
            sugestoes[indice] = achado["replacements"][0]["value"]
    return sugestoes


def consultar_ortografia(palavras: list[str], url: str) -> dict[int, str]:
    return localizar_erros(palavras, correcao.consultar("\n".join(palavras), url))


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
        regras = modulo_regras.carregar()
        return Motor(correcoes, regras.get("ignorar", []), regras, config.carregar()["ponto_final_ao_enviar"])

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

    def _ao_teclar(self, tipo: str, caractere: str | None) -> bool:
        """Devolve True quando a tecla deve ser retida: o Enter só segue depois da correção."""
        if not self._ativo():
            return False
        if tipo == "enter":
            acao = self.motor.finalizar()
            if acao:
                self.fila_acoes.put(acao)
                return True
        elif tipo == "quebra":
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
        return False

    def _enviar(self) -> None:
        while (acao := self.fila_acoes.get()) is not None:
            janelas.substituir_digitado(acao.apagar, acao.escrever, acao.enter)

    def _consultar(self) -> None:
        while (consulta := self.fila_consultas.get()) is not None:
            lote = [consulta]
            while not self.fila_consultas.empty():
                proxima = self.fila_consultas.get_nowait()
                if proxima is None:
                    return
                lote.append(proxima)
            processo = self.linguagem.processo
            if not processo or processo.poll() is not None:
                continue
            try:
                sugestoes = consultar_ortografia([c.nucleo for c in lote], self.linguagem.url())
            except (OSError, ValueError):
                continue
            # Teclas enviadas entre o acento e a letra fariam o Windows perder o acento.
            limite = time.monotonic() + 3
            while self.gancho and self.gancho.acento and time.monotonic() < limite:
                time.sleep(0.02)
            for indice, item in enumerate(lote):
                acao = self.motor.resposta_consulta(item.numero, sugestoes.get(indice))
                if acao:
                    self.fila_acoes.put(acao)
