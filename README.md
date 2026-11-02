# Corretor de texto

Corrige e reformula o texto selecionado em qualquer chat do Windows, sem enviar nada para a internet.

## Uso

1. Inicie com `pythonw iniciar.pyw`. O ícone aparece na bandeja.
2. Selecione o texto no chat.
3. Clique em **Corrigir** ou **Reformular** na barra flutuante, que pode ser arrastada pela alça. Também valem os atalhos `Ctrl+Shift+Y` ou `Ctrl+Shift+1` para corrigir, e `Ctrl+Shift+U` ou `Ctrl+Shift+2` para reformular.
4. Confira a sugestão e clique em **Substituir**. O programa nunca envia a mensagem.

## Correção ao digitar

`Ctrl+Shift+F` liga e `Ctrl+Shift+G` desliga. O botão **Ao digitar** da barra e o ícone da bandeja fazem o mesmo. Vem desligada.

- Ao terminar uma palavra com espaço, corrige grafia e acento e coloca a maiúscula no início da frase.
- `Backspace` logo depois de uma correção desfaz a troca.
- Só atua em janelas cujo título contenha um dos nomes de `digitacao_janelas`, em `dados/config.json`.
- As correções vêm de `dados/correcoes_digitacao.json` e, com o LanguageTool instalado, também dele.
- Vírgula e concordância ficam no `Ctrl+Shift+1`, porque dependem da frase inteira.
- Ao apertar `Enter`, corrige a última palavra da lista e, em mensagens de 4 palavras ou mais, coloca o ponto final antes de enviar. `ponto_final_ao_enviar` desliga o ponto.
- O programa observa as teclas para funcionar e guarda só os últimos 120 caracteres da mensagem, na memória. Nada é gravado em disco ou enviado.

## Personalização

- `dados/config.json`: atalhos, portas e endereço de atualizações.
- `dados/regras.json`: regras do escritório.
- `dados/meu_dicionario.json`: lista de termos que a correção não deve alterar, por exemplo `["Fulano"]`.

## Componentes

Ficam em `componentes/`, que não vai para o repositório:

- `java/`: Java 17 ou superior, com `bin/java.exe`
- `languagetool/`: LanguageTool com `languagetool-server.jar`
- `llama/`: llama.cpp com `llama-server.exe`
- `modelo/`: um modelo `.gguf`

Sem o LanguageTool, a correção aplica só as regras do escritório. Sem o llama.cpp e o modelo, a reformulação fica indisponível.

## Atualização

**Verificar atualizações**, no ícone da bandeja, lê o manifesto em `url_manifesto`, mostra o que há de novo e só instala após a confirmação. O endereço precisa usar HTTPS, e cada arquivo é conferido pelo SHA-256:

```json
{
  "componentes": {
    "regras": {
      "versao": "0.2.0",
      "url": "https://exemplo/regras.zip",
      "sha256": "...",
      "notas": "Novos termos jurídicos"
    }
  }
}
```

Nomes aceitos: `programa`, `regras`, `java`, `languagetool`, `llama` e `modelo`.

## Limitações

- O conteúdo da área de transferência é restaurado apenas quando é texto. Uma imagem copiada antes do atalho é perdida.
- O histórico da área de transferência do Windows (`Win+V`), se estiver ativo, guarda o texto selecionado, como em qualquer cópia.

## Publicação

Enviar uma tag `publicar-*` executa `.github/workflows/publicar-componentes.yml`, que baixa os componentes das fontes oficiais e os publica na versão `componentes`. Nunca coloque neste repositório público dados de clientes ou de casos.

## Componentes de terceiros

- [Eclipse Temurin](https://adoptium.net) (GPLv2 com Classpath Exception)
- [LanguageTool](https://languagetool.org) (LGPL 2.1)
- [llama.cpp](https://github.com/ggml-org/llama.cpp) (MIT)
- Qwen3 1.7B, em GGUF da [Unsloth](https://huggingface.co/unsloth/Qwen3-1.7B-GGUF) (Apache 2.0)

## Testes

```bash
python -m unittest tests.test_corretor
```
