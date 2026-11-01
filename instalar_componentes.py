"""Primeira instalação: baixa do GitHub tudo o que estiver faltando ou desatualizado."""
from corretor import atualizacao, config


def main():
    pendentes = atualizacao.verificar(config.carregar()["url_manifesto"])
    if not pendentes:
        print("Tudo atualizado.")
    for nome, info in pendentes.items():
        print(f"Instalando {nome} {info['versao']}...", flush=True)
        atualizacao.instalar(nome, info)
    print("Concluído.")


if __name__ == "__main__":
    main()
