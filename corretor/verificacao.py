"""Compara o original e a reformulação para avisar sobre mudanças de sentido."""
import difflib
import re

_NUMERO = re.compile(r"\d[\d.,/:\-]*\d|\d")
_PALAVRA = re.compile(r"\w+", re.UNICODE)
_NOME = re.compile(r"(?<![.!?\n]\s)(?<!^)\b[A-ZÀ-Ý][a-zà-ÿ]{2,}\b")
_TEMPO = {
    "segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo",
    "janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
    "setembro", "outubro", "novembro", "dezembro", "hoje", "amanhã", "ontem",
}
_NEGACAO = {"não", "nao", "nunca", "nem", "jamais", "sem", "nenhum", "nenhuma"}


def _palavras(texto: str) -> list[str]:
    return [p.casefold() for p in _PALAVRA.findall(texto)]


def comparar(original: str, sugestao: str) -> list[str]:
    avisos = []
    numeros_o, numeros_s = set(_NUMERO.findall(original)), set(_NUMERO.findall(sugestao))
    if numeros_o - numeros_s:
        avisos.append("Número, valor ou data removido: " + ", ".join(sorted(numeros_o - numeros_s)))
    if numeros_s - numeros_o:
        avisos.append("Número, valor ou data acrescentado: " + ", ".join(sorted(numeros_s - numeros_o)))

    palavras_o, palavras_s = _palavras(original), _palavras(sugestao)
    tempo_o, tempo_s = set(palavras_o) & _TEMPO, set(palavras_s) & _TEMPO
    if tempo_o != tempo_s:
        avisos.append("Referência de data mudou: " + ", ".join(sorted(tempo_o ^ tempo_s)))

    nomes_o = set(_NOME.findall(original))
    faltando = sorted(n for n in nomes_o if n.casefold() not in palavras_s and n.casefold() not in _TEMPO)
    if faltando:
        avisos.append("Nome removido: " + ", ".join(faltando))

    negacoes_o = sum(p in _NEGACAO for p in palavras_o)
    negacoes_s = sum(p in _NEGACAO for p in palavras_s)
    if negacoes_o != negacoes_s:
        avisos.append("A quantidade de negações mudou (\"não\", \"nunca\", \"sem\"...). Confira o sentido.")
    return avisos


def trechos(a: str, b: str) -> tuple[list[tuple[str, bool]], list[tuple[str, bool]]]:
    """Divide os dois textos em pedaços marcados como alterados ou não, para o destaque na tela."""
    dividir = lambda s: re.findall(r"\s+|\w+|[^\w\s]", s, re.UNICODE)
    ta, tb = dividir(a), dividir(b)
    saida_a, saida_b = [], []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ta, tb, autojunk=False).get_opcodes():
        alterado = op != "equal"
        if i2 > i1:
            saida_a.append(("".join(ta[i1:i2]), alterado))
        if j2 > j1:
            saida_b.append(("".join(tb[j1:j2]), alterado))
    return saida_a, saida_b
