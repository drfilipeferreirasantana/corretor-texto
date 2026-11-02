"""Reformulação com o modelo local."""
import json
import re
import urllib.request

from . import correcao, verificacao
from .servicos import LanguageTool, Modelo

ESTILO_RAPIDO = "Arrumar frases e pontuação (até 30 s)"
ESTILOS = {
    ESTILO_RAPIDO: "",
    "Mais objetivo (até 3 min)": "Reescreva em frases curtas e diretas, cortando repetições e muletas, sem perder informação.",
    "Mais formal (até 3 min)": "Reescreva em tom profissional e cortês, trocando gírias e abreviações.",
    "Mais simples (até 3 min)": "Reescreva trocando termos jurídicos por palavras do dia a dia, para um cliente leigo entender.",
}

_INSTRUCAO_RAPIDA = (
    "Você revisa mensagens em português do Brasil, escritas por um advogado para clientes. "
    "Corrija ortografia, acentuação, crase e concordância. "
    "Divida o texto em frases: coloque maiúscula no início, ponto final no fim de cada frase e as vírgulas necessárias. "
    "Use \"é\" quando for o verbo ser. "
    "Mantenha as mesmas palavras e a mesma ordem, sem acrescentar nem retirar informações. "
    "Responda somente com o texto revisado."
)
_INSTRUCAO = (
    "Você reescreve mensagens em português do Brasil, escritas por um advogado para clientes em chats. "
    "{estilo} Corrija ortografia, concordância e pontuação. "
    "Não invente fatos nem acrescente frases novas. Não mude quem faz cada ação. "
    "Mantenha exatamente todos os nomes, valores, datas, prazos, números e negações. "
    "Mantenha o tratamento usado, como \"a senhora\" ou \"você\". "
    "Responda somente com o texto reescrito, sem aspas e sem comentários."
)


def limpar_resposta(resposta: str) -> str:
    """Tira a etapa de raciocínio. Enquanto ela não termina, ainda não há texto para mostrar."""
    resposta = re.sub(r"<think>.*?</think>", "", resposta, flags=re.DOTALL)
    return resposta.split("<think>")[0].strip()


def acabamento(texto: str) -> str:
    if not texto:
        return texto
    texto = texto[0].upper() + texto[1:]
    return texto + "." if texto[-1].isalnum() else texto


def _gerar(sistema: str, usuario: str, url: str, ao_parcial, cancelar) -> str | None:
    corpo = json.dumps({
        "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
        "temperature": 0.1,
        "max_tokens": 1200,
        "stream": True,
    }).encode()
    pedido = urllib.request.Request(f"{url}/v1/chat/completions", corpo, {"Content-Type": "application/json"})
    acumulado = ""
    # Fechar a conexão faz o servidor parar, então cancelar libera o processador na hora.
    with urllib.request.urlopen(pedido, timeout=300) as resposta:
        for linha in resposta:
            if cancelar.is_set():
                return None
            if not linha.startswith(b"data: ") or linha.startswith(b"data: [DONE]"):
                continue
            delta = json.loads(linha[6:])["choices"][0]["delta"].get("content")
            if delta:
                acumulado += delta
                ao_parcial(limpar_resposta(acumulado))
    return limpar_resposta(acumulado)


def reformular(texto: str, estilo: str, modelo: Modelo, linguagem: LanguageTool, ao_parcial, cancelar) -> dict | None:
    url = modelo.garantir()
    modelo.marcar_uso()
    rapido = estilo == ESTILO_RAPIDO
    if rapido:
        # As regras e o LanguageTool acertam o que o modelo pequeno erra, como "Amém" e "mãe".
        base = correcao.corrigir(texto, linguagem)["texto"]
        gerado = _gerar(_INSTRUCAO_RAPIDA, f"{base} /no_think", url, ao_parcial, cancelar)
    else:
        base = texto
        gerado = _gerar(_INSTRUCAO.format(estilo=ESTILOS[estilo]), texto, url, ao_parcial, cancelar)
    modelo.marcar_uso()
    if gerado is None or cancelar.is_set():
        return None
    final = acabamento(correcao.corrigir(gerado, linguagem)["texto"])
    avisos = verificacao.comparar(texto, final)
    if rapido:
        retiradas = verificacao.palavras_retiradas(base, final)
        if retiradas:
            avisos.append("Palavras retiradas: " + ", ".join(retiradas[:6]))
    return {"texto": final, "motivos": [], "avisos": avisos}
