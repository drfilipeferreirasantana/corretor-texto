"""Reformulação com o modelo local."""
import json
import re
import time
import urllib.request

from . import verificacao
from .servicos import Modelo

ESTILOS = {
    "Só arrumar as frases (segundos)": "Mantenha as frases como estão, ajustando apenas o que estiver errado.",
    "Mais objetivo (até 3 minutos)": "Reescreva em frases curtas e diretas, cortando repetições e muletas, sem perder informação.",
    "Mais formal (até 3 minutos)": "Reescreva em tom profissional e cortês, trocando gírias e abreviações.",
    "Mais simples (até 3 minutos)": "Reescreva trocando termos jurídicos por palavras do dia a dia, para um cliente leigo entender.",
}
_ESTILO_RAPIDO = "Só arrumar as frases (segundos)"

_INSTRUCAO = (
    "Você reescreve mensagens em português do Brasil, escritas por um advogado para clientes em chats. "
    "{estilo} Corrija ortografia, concordância e pontuação. "
    "Não invente fatos nem acrescente frases novas. Não mude quem faz cada ação. "
    "Mantenha exatamente todos os nomes, valores, datas, prazos, números e negações. "
    "Mantenha o tratamento usado, como \"a senhora\" ou \"você\". "
    "Responda somente com o texto reescrito, sem aspas e sem comentários."
)


def limpar_resposta(resposta: str) -> str:
    return re.sub(r"<think>.*?</think>", "", resposta, flags=re.DOTALL).strip()


def reformular(texto: str, estilo: str, servico: Modelo) -> dict:
    url = servico.garantir()
    corpo = json.dumps({
        "messages": [
            {"role": "system", "content": _INSTRUCAO.format(estilo=ESTILOS[estilo])},
            # Sem a etapa de raciocínio é bem mais rápido, mas o modelo quase só corrige.
            {"role": "user", "content": f"{texto} /no_think" if estilo == _ESTILO_RAPIDO else texto},
        ],
        "temperature": 0.2,
        "max_tokens": 1200,
    }).encode()
    pedido = urllib.request.Request(f"{url}/v1/chat/completions", corpo, {"Content-Type": "application/json"})
    with urllib.request.urlopen(pedido, timeout=300) as resposta:
        sugestao = limpar_resposta(json.load(resposta)["choices"][0]["message"]["content"])
    servico.ultimo_uso = time.monotonic()
    return {"texto": sugestao, "motivos": [], "avisos": verificacao.comparar(texto, sugestao)}
