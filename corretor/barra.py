"""Barra flutuante com os botões Corrigir e Reformular."""
import tkinter as tk

from . import config, janelas

_FUNDO, _DOURADO, _BRANCO = "#0b1f3a", "#c9a227", "#ffffff"


class Barra:
    def __init__(self, raiz, ao_acionar):
        self.janela = jan = tk.Toplevel(raiz)
        jan.overrideredirect(True)
        jan.attributes("-topmost", True)
        jan.configure(bg=_FUNDO)

        self.alca = tk.Label(jan, text="⠿", bg=_FUNDO, fg=_DOURADO, cursor="fleur", font=("Segoe UI", 12), padx=6)
        self.alca.pack(side="left", fill="y")
        self.alca.bind("<ButtonPress-1>", self._iniciar_arraste)
        self.alca.bind("<B1-Motion>", self._arrastar)
        self.alca.bind("<ButtonRelease-1>", self._salvar_posicao)

        self.botoes = {}
        for acao, rotulo in (("corrigir", "Corrigir"), ("reformular", "Reformular")):
            botao = tk.Label(jan, text=rotulo, bg=_FUNDO, fg=_BRANCO, cursor="hand2",
                             font=("Segoe UI", 10, "bold"), padx=10, pady=6)
            botao.pack(side="left")
            # Um Label, e não um Button, porque não pede foco ao ser clicado.
            botao.bind("<ButtonRelease-1>", lambda _, a=acao: ao_acionar(a))
            botao.bind("<Enter>", lambda _, b=botao: b.configure(fg=_DOURADO))
            botao.bind("<Leave>", lambda _, b=botao: b.configure(fg=_BRANCO))
            self.botoes[acao] = botao

        self.interruptor = tk.Label(jan, bg=_FUNDO, cursor="hand2", font=("Segoe UI", 10, "bold"), padx=10, pady=6)
        self.interruptor.pack(side="left")
        self.interruptor.bind("<ButtonRelease-1>", lambda _: ao_acionar("alternar_digitacao"))
        self.mostrar_digitacao(False)

        jan.update_idletasks()
        posicao = config.carregar()["barra_posicao"]
        if posicao:
            x, y = posicao
        else:
            x = jan.winfo_screenwidth() - jan.winfo_reqwidth() - 24
            y = jan.winfo_screenheight() - jan.winfo_reqheight() - 72
        jan.geometry(f"+{self._limitar(x, y)[0]}+{self._limitar(x, y)[1]}")
        jan.update()
        self.sem_foco = janelas.impedir_foco(int(jan.wm_frame(), 16))
        janelas.impedir_foco(jan.winfo_id())

    def mostrar_digitacao(self, ligada: bool) -> None:
        self.interruptor.configure(text=f"Ao digitar: {'ligado' if ligada else 'desligado'}",
                                   fg=_DOURADO if ligada else _BRANCO)

    def _limitar(self, x, y):
        """Um monitor externo desconectado não pode deixar a barra fora da tela."""
        jan = self.janela
        return (max(0, min(x, jan.winfo_screenwidth() - jan.winfo_reqwidth())),
                max(0, min(y, jan.winfo_screenheight() - jan.winfo_reqheight())))

    def _iniciar_arraste(self, evento):
        self._origem = evento.x_root - self.janela.winfo_x(), evento.y_root - self.janela.winfo_y()

    def _arrastar(self, evento):
        x, y = self._limitar(evento.x_root - self._origem[0], evento.y_root - self._origem[1])
        self.janela.geometry(f"+{x}+{y}")

    def _salvar_posicao(self, _):
        config.salvar("barra_posicao", [self.janela.winfo_x(), self.janela.winfo_y()])

    def fechar(self):
        self.janela.destroy()
