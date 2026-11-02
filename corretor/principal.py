"""Programa principal: recebe os atalhos, mostra a comparação e substitui o texto."""
import ctypes
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

from . import __version__, atualizacao, config, correcao, janelas, reformulacao, verificacao
from .barra import Barra
from .digitacao import CorrecaoAoDigitar
from .servicos import ComponenteAusente, LanguageTool, Modelo


class Aplicativo:
    def __init__(self):
        self.cfg = config.carregar()
        self.fila = queue.Queue()
        self.raiz = tk.Tk()
        self.raiz.withdraw()
        self.janela = None
        self.linguagem = LanguageTool()
        self.modelo = Modelo()
        self.bandeja = janelas.Bandeja(
            [(acao, atalho) for acao, lista in self.cfg["atalhos"].items() for atalho in lista],
            self._itens_menu,
            lambda acao: self.fila.put((acao, None)),
        )
        self.digitacao = CorrecaoAoDigitar(self.linguagem)
        self.barra = None
        self.janela_externa = None
        self.cancelar = None

    def _itens_menu(self):
        estado = "ligada" if self.digitacao.gancho else "desligada"
        return [
            (f"Barra de botões: {'ligada' if self.barra else 'desligada'}", "alternar_barra"),
            (f"Correção ao digitar: {estado}", "alternar_digitacao"),
            ("Verificar atualizações", "atualizar"),
            (f"Sair (versão {__version__})", "sair"),
        ]

    def _mostrar_barra(self):
        self.barra = Barra(self.raiz, lambda acao: self.fila.put((acao, None)))
        self.barra.mostrar_digitacao(bool(self.digitacao.gancho))

    def _alternar_barra(self):
        if self.barra:
            self.barra.fechar()
            self.barra = None
        else:
            self._mostrar_barra()
        config.salvar("barra_ligada", bool(self.barra))

    def _definir_digitacao(self, ligada: bool):
        if ligada:
            self.digitacao.ligar()
        else:
            self.digitacao.desligar()
        config.salvar("digitacao_ligada", ligada)
        if self.barra:
            self.barra.mostrar_digitacao(ligada)
        mensagem = "Correção ao digitar desligada."
        if ligada:
            mensagem = "Correção ao digitar ligada em: " + ", ".join(self.cfg["digitacao_janelas"]) + "."
        self.bandeja.notificar("Corretor de texto", mensagem)

    def iniciar(self):
        self.bandeja.start()
        if self.cfg["barra_ligada"]:
            self._mostrar_barra()
        if self.cfg["digitacao_ligada"]:
            self.digitacao.ligar()
        self.bandeja.pronta.wait(5)
        if self.bandeja.falhas:
            messagebox.showwarning("Corretor de texto", "Atalhos em uso por outro programa: " + ", ".join(self.bandeja.falhas))
        threading.Thread(target=self._aquecer, daemon=True).start()
        self._lembrar_janela_externa()
        self.raiz.after(50, self._processar_fila)
        self.raiz.after(60_000, self._manutencao)
        self.raiz.mainloop()

    def _aquecer(self):
        try:
            self.linguagem.garantir()
        except (ComponenteAusente, RuntimeError):
            pass  # o aviso aparece quando a correção for usada

    def _manutencao(self):
        self.modelo.liberar_se_ocioso()
        self.raiz.after(60_000, self._manutencao)

    def _processar_fila(self):
        try:
            while True:
                acao, dados = self.fila.get_nowait()
                if acao in ("corrigir", "reformular"):
                    self._acionar(acao)
                elif acao == "parcial":
                    self._mostrar_parcial(*dados)
                elif acao == "resultado":
                    self._mostrar_resultado(*dados)
                elif acao == "alternar_barra":
                    self._alternar_barra()
                elif acao == "alternar_digitacao":
                    self._definir_digitacao(not self.digitacao.gancho)
                elif acao == "ligar_digitacao":
                    self._definir_digitacao(True)
                elif acao == "desligar_digitacao":
                    self._definir_digitacao(False)
                elif acao == "atualizar":
                    self._atualizar()
                elif acao == "aviso":
                    messagebox.showinfo("Corretor de texto", dados)
                elif acao == "sair":
                    self._sair()
                    return
        except queue.Empty:
            pass
        self.raiz.after(50, self._processar_fila)

    def _lembrar_janela_externa(self):
        """O clique na barra pode tirar o foco do chat, então é preciso saber para onde voltar."""
        ativa = janelas.janela_ativa()
        if ativa and not janelas.janela_nossa(ativa):
            self.janela_externa = ativa
        self.raiz.after(150, self._lembrar_janela_externa)

    def _acionar(self, acao):
        alvo = janelas.janela_ativa()
        if janelas.janela_nossa(alvo):
            if not self.janela_externa or not janelas.voltar_para(self.janela_externa):
                self.bandeja.notificar("Corretor de texto", "Clique no chat e selecione o texto novamente.")
                return
            alvo = self.janela_externa
        teclas = [janelas.interpretar_atalho(atalho)[1] for atalho in self.cfg["atalhos"][acao]]
        texto, anterior = janelas.capturar_selecao(teclas)
        if anterior is not None:
            janelas.gravar_area_transferencia(anterior)
        if not texto or not texto.strip():
            self.bandeja.notificar("Corretor de texto", "Clique na caixa de mensagem e tente novamente.")
            return
        self._abrir_janela(acao, texto, anterior, alvo)

    def _abrir_janela(self, acao, texto, anterior, alvo):
        self._cancelar_pedido()
        if self.janela:
            self.janela.destroy()
        self.janela = jan = tk.Toplevel(self.raiz)
        self.estado = {"acao": acao, "texto": texto, "anterior": anterior, "alvo": alvo, "sugestao": None, "pedido": object()}
        jan.title("Corrigir texto" if acao == "corrigir" else "Reformular texto")
        jan.attributes("-topmost", True)
        jan.bind("<Escape>", lambda _: self._fechar())
        jan.protocol("WM_DELETE_WINDOW", self._fechar)
        x, y = janelas.posicao_cursor()
        largura, altura = 620, 470
        x = max(0, min(x, jan.winfo_screenwidth() - largura))
        y = max(0, min(y, jan.winfo_screenheight() - altura - 60))
        jan.geometry(f"{largura}x{altura}+{x}+{y}")

        quadro = ttk.Frame(jan, padding=12)
        quadro.pack(fill="both", expand=True)
        if acao == "reformular":
            linha = ttk.Frame(quadro)
            linha.pack(fill="x", pady=(0, 8))
            ttk.Label(linha, text="Estilo:").pack(side="left")
            self.estilo = ttk.Combobox(linha, state="readonly", values=list(reformulacao.ESTILOS), width=38)
            self.estilo.current(0)
            self.estilo.pack(side="left", padx=6)
            self.estilo.bind("<<ComboboxSelected>>", lambda _: self._processar())

        ttk.Label(quadro, text="Original").pack(anchor="w")
        self.caixa_original = tk.Text(quadro, height=6, wrap="word", font=("Segoe UI", 10))
        self.caixa_original.pack(fill="both", expand=True)
        ttk.Label(quadro, text="Sugestão (pode ser editada)").pack(anchor="w", pady=(8, 0))
        self.caixa_sugestao = tk.Text(quadro, height=6, wrap="word", font=("Segoe UI", 10))
        self.caixa_sugestao.pack(fill="both", expand=True)
        self.caixa_original.tag_config("alterado", background="#f8d7da")
        self.caixa_sugestao.tag_config("alterado", background="#d1e7dd")
        self.rotulo_avisos = ttk.Label(quadro, foreground="#9a3412", wraplength=590, justify="left")
        self.rotulo_avisos.pack(anchor="w", pady=6)

        botoes = ttk.Frame(quadro)
        botoes.pack(fill="x")
        self.botao_substituir = ttk.Button(botoes, text="Substituir", command=self._substituir, state="disabled")
        self.botao_substituir.pack(side="right")
        ttk.Button(botoes, text="Cancelar", command=self._fechar).pack(side="right", padx=6)
        if acao == "corrigir":
            ttk.Button(botoes, text="Arrumar frases e pontuação",
                       command=lambda: self._abrir_janela("reformular", texto, anterior, alvo)).pack(side="left")
        self._processar()
        jan.lift()
        jan.focus_force()

    def _cancelar_pedido(self):
        if self.cancelar:
            self.cancelar.set()

    def _atualizar_tempo(self, pedido, inicio):
        if not self.janela or pedido is not self.estado["pedido"] or self.botao_substituir["state"] == "normal":
            return
        if self.rotulo_avisos.cget("text").startswith(("Processando", "Escrevendo")):
            etapa = "Escrevendo" if self.caixa_sugestao.get("1.0", "end-1c") else "Processando"
            self.rotulo_avisos.config(text=f"{etapa}... {int(time.monotonic() - inicio)} s")
        self.raiz.after(1000, lambda: self._atualizar_tempo(pedido, inicio))

    def _mostrar_parcial(self, pedido, texto):
        if self.janela and pedido is self.estado["pedido"]:
            self.caixa_sugestao.delete("1.0", "end")
            self.caixa_sugestao.insert("1.0", texto)
            self.caixa_sugestao.see("end")

    def _processar(self):
        self._cancelar_pedido()
        cancelar = self.cancelar = threading.Event()
        pedido = self.estado["pedido"] = object()
        acao, texto = self.estado["acao"], self.estado["texto"]
        estilo = self.estilo.get() if acao == "reformular" else None
        self.botao_substituir.config(state="disabled")
        self.rotulo_avisos.config(text="Processando...")
        self.caixa_original.config(state="normal")
        self.caixa_original.delete("1.0", "end")
        self.caixa_original.insert("1.0", texto)
        self.caixa_original.config(state="disabled")
        self.caixa_sugestao.delete("1.0", "end")

        def trabalhar():
            try:
                if acao == "corrigir":
                    resultado = correcao.corrigir(texto, self.linguagem)
                else:
                    resultado = reformulacao.reformular(
                        texto, estilo, self.modelo, self.linguagem,
                        lambda parcial: self.fila.put(("parcial", (pedido, parcial))), cancelar,
                    )
                    if resultado is None:
                        return
            except ComponenteAusente as erro:
                resultado = {"erro": f"{erro} Use \"Verificar atualizações\" no ícone da bandeja."}
            except Exception as erro:
                resultado = {"erro": f"Não foi possível processar: {erro}"}
            self.fila.put(("resultado", (pedido, resultado)))

        threading.Thread(target=trabalhar, daemon=True).start()
        self._atualizar_tempo(pedido, time.monotonic())

    def _mostrar_resultado(self, pedido, resultado):
        if not self.janela or pedido is not self.estado["pedido"]:
            return
        if "erro" in resultado:
            self.rotulo_avisos.config(text=resultado["erro"])
            return
        sugestao = resultado["texto"]
        self.caixa_original.config(state="normal")
        self.caixa_original.delete("1.0", "end")
        original, nova = verificacao.trechos(self.estado["texto"], sugestao)
        for trecho, alterado in original:
            self.caixa_original.insert("end", trecho, "alterado" if alterado else ())
        self.caixa_original.config(state="disabled")
        self.caixa_sugestao.delete("1.0", "end")
        for trecho, alterado in nova:
            self.caixa_sugestao.insert("end", trecho, "alterado" if alterado else ())
        linhas = [f"Atenção: {aviso}" for aviso in resultado["avisos"]]
        if sugestao == self.estado["texto"]:
            linhas.insert(0, "Nenhuma alteração sugerida.")
        linhas += resultado["motivos"][:4]
        if len(resultado["motivos"]) > 4:
            linhas.append(f"e mais {len(resultado['motivos']) - 4} correções.")
        self.rotulo_avisos.config(text="\n".join(linhas))
        self.botao_substituir.config(state="normal")
        self.botao_substituir.focus_set()

    def _substituir(self):
        texto = self.caixa_sugestao.get("1.0", "end-1c")
        alvo, anterior = self.estado["alvo"], self.estado["anterior"]
        self._fechar()
        self.raiz.update()
        janelas.colar_na_janela(alvo, texto, anterior)

    def _fechar(self):
        self._cancelar_pedido()
        if self.janela:
            self.janela.destroy()
            self.janela = None

    def _atualizar(self):
        url = self.cfg["url_manifesto"]
        if not url:
            messagebox.showinfo("Atualizações", "O endereço de atualizações ainda não foi configurado.")
            return

        def trabalhar():
            try:
                pendentes = atualizacao.verificar(url)
            except Exception as erro:
                self.fila.put(("aviso", f"Não foi possível verificar: {erro}"))
                return
            self.raiz.after(0, lambda: self._confirmar_atualizacao(pendentes))

        threading.Thread(target=trabalhar, daemon=True).start()

    def _confirmar_atualizacao(self, pendentes):
        if not pendentes:
            messagebox.showinfo("Atualizações", "Tudo atualizado.")
            return
        lista = "\n".join(f"• {nome} {info['versao']}: {info.get('notas', '')}" for nome, info in pendentes.items())
        if not messagebox.askyesno("Atualizações", f"Instalar estas atualizações?\n\n{lista}"):
            return

        def trabalhar():
            self.linguagem.parar()
            self.modelo.parar()
            try:
                for nome, info in pendentes.items():
                    atualizacao.instalar(nome, info)
                mensagem = "Atualização concluída."
                if "programa" in pendentes:
                    mensagem += " A nova versão do programa entra em uso ao reiniciá-lo."
            except Exception as erro:
                mensagem = f"A atualização falhou e o componente atual foi mantido: {erro}"
            self.fila.put(("aviso", mensagem))

        threading.Thread(target=trabalhar, daemon=True).start()

    def _sair(self):
        self.digitacao.desligar()
        self.linguagem.parar()
        self.modelo.parar()
        self.bandeja.encerrar()
        self.raiz.destroy()


def main():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except OSError:
        pass
    if not janelas.instancia_unica():
        return
    janelas.prioridade_alta()
    if "--diagnostico" in sys.argv:
        aplicativo = Aplicativo()
        aplicativo.bandeja.start()
        aplicativo.bandeja.pronta.wait(5)
        print("bandeja:", "ok" if aplicativo.bandeja.janela else "falhou")
        print("atalhos com conflito:", aplicativo.bandeja.falhas or "nenhum")
        gancho = janelas.GanchoEntrada(lambda *_: None, lambda: None)
        gancho.start()
        gancho.pronto.wait(5)
        print("gancho de teclado e mouse:", "ok" if gancho.instalado else "falhou")
        gancho.encerrar()
        gancho.join(3)
        print("gancho encerrado:", "ok" if not gancho.is_alive() else "falhou")
        aplicativo._abrir_janela("corrigir", "Teste vc concerteza.", None, None)
        aplicativo.raiz.update()
        aplicativo.bandeja.encerrar()
        aplicativo.bandeja.join(3)
        print("janela: ok")
        return
    Aplicativo().iniciar()
