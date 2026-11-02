"""Chamadas ao Windows: área de transferência, teclado, atalhos globais e bandeja."""
import ctypes
import os
import threading
import time
import traceback
import unicodedata
from ctypes import wintypes

from . import config

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)

LRESULT = ctypes.c_ssize_t
ULONG_PTR = ctypes.c_size_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
WM_DESTROY, WM_CLOSE, WM_COMMAND, WM_HOTKEY = 0x0002, 0x0010, 0x0111, 0x0312
WM_RBUTTONUP, WM_LBUTTONUP, WM_BANDEJA = 0x0205, 0x0202, 0x0400 + 1
VK_SHIFT, VK_CONTROL, VK_MENU = 0x10, 0x11, 0x12
KEYEVENTF_KEYUP = 0x0002
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000
NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP, NIF_INFO = 0x1, 0x2, 0x4, 0x10
TPM_RETURNCMD, TPM_NONOTIFY = 0x0100, 0x0080
IDI_APPLICATION = 32512


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class _UNIAO(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _UNIAO)]


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HANDLE),
                ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HANDLE),
                ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND), ("uID", wintypes.UINT),
                ("uFlags", wintypes.UINT), ("uCallbackMessage", wintypes.UINT), ("hIcon", wintypes.HANDLE),
                ("szTip", wintypes.WCHAR * 128), ("dwState", wintypes.DWORD), ("dwStateMask", wintypes.DWORD),
                ("szInfo", wintypes.WCHAR * 256), ("uVersion", wintypes.UINT),
                ("szInfoTitle", wintypes.WCHAR * 64), ("dwInfoFlags", wintypes.DWORD),
                ("guidItem", ctypes.c_byte * 16), ("hBalloonIcon", wintypes.HANDLE)]


def _tipos(funcao, argumentos, retorno):
    funcao.argtypes, funcao.restype = argumentos, retorno


_tipos(user32.OpenClipboard, [wintypes.HWND], wintypes.BOOL)
_tipos(user32.CloseClipboard, [], wintypes.BOOL)
_tipos(user32.EmptyClipboard, [], wintypes.BOOL)
_tipos(user32.GetClipboardData, [wintypes.UINT], wintypes.HANDLE)
_tipos(user32.SetClipboardData, [wintypes.UINT, wintypes.HANDLE], wintypes.HANDLE)
_tipos(user32.GetClipboardSequenceNumber, [], wintypes.DWORD)
_tipos(kernel32.GlobalAlloc, [wintypes.UINT, ctypes.c_size_t], wintypes.HGLOBAL)
_tipos(kernel32.GlobalLock, [wintypes.HGLOBAL], wintypes.LPVOID)
_tipos(kernel32.GlobalUnlock, [wintypes.HGLOBAL], wintypes.BOOL)
_tipos(kernel32.GlobalFree, [wintypes.HGLOBAL], wintypes.HGLOBAL)
_tipos(kernel32.GetModuleHandleW, [wintypes.LPCWSTR], wintypes.HMODULE)
_tipos(kernel32.CreateMutexW, [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR], wintypes.HANDLE)
_tipos(user32.GetForegroundWindow, [], wintypes.HWND)
_tipos(user32.SetForegroundWindow, [wintypes.HWND], wintypes.BOOL)
_tipos(user32.GetAsyncKeyState, [ctypes.c_int], ctypes.c_short)
_tipos(user32.SendInput, [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int], wintypes.UINT)
_tipos(user32.GetCursorPos, [ctypes.POINTER(wintypes.POINT)], wintypes.BOOL)
_tipos(user32.RegisterHotKey, [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT], wintypes.BOOL)
_tipos(user32.UnregisterHotKey, [wintypes.HWND, ctypes.c_int], wintypes.BOOL)
_tipos(user32.DefWindowProcW, [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM], LRESULT)
_tipos(user32.RegisterClassW, [ctypes.POINTER(WNDCLASSW)], wintypes.ATOM)
_tipos(user32.CreateWindowExW, [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID], wintypes.HWND)
_tipos(user32.DestroyWindow, [wintypes.HWND], wintypes.BOOL)
_tipos(user32.PostMessageW, [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM], wintypes.BOOL)
_tipos(user32.PostQuitMessage, [ctypes.c_int], None)
_tipos(user32.GetMessageW, [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT], wintypes.BOOL)
_tipos(user32.TranslateMessage, [ctypes.POINTER(wintypes.MSG)], wintypes.BOOL)
_tipos(user32.DispatchMessageW, [ctypes.POINTER(wintypes.MSG)], LRESULT)
_tipos(user32.LoadIconW, [wintypes.HINSTANCE, wintypes.LPCWSTR], wintypes.HANDLE)
_tipos(user32.CreatePopupMenu, [], wintypes.HMENU)
_tipos(user32.AppendMenuW, [wintypes.HMENU, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR], wintypes.BOOL)
_tipos(user32.DestroyMenu, [wintypes.HMENU], wintypes.BOOL)
_tipos(user32.TrackPopupMenu, [wintypes.HMENU, wintypes.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                               wintypes.HWND, wintypes.LPVOID], ctypes.c_int)
_tipos(shell32.Shell_NotifyIconW, [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)], wintypes.BOOL)


def _abrir_area_transferencia() -> bool:
    for _ in range(10):
        if user32.OpenClipboard(None):
            return True
        time.sleep(0.03)
    return False


def ler_area_transferencia() -> str | None:
    if not _abrir_area_transferencia():
        return None
    try:
        identificador = user32.GetClipboardData(CF_UNICODETEXT)
        if not identificador:
            return None
        ponteiro = kernel32.GlobalLock(identificador)
        try:
            return ctypes.wstring_at(ponteiro)
        finally:
            kernel32.GlobalUnlock(identificador)
    finally:
        user32.CloseClipboard()


def gravar_area_transferencia(texto: str) -> bool:
    dados = texto.encode("utf-16-le") + b"\x00\x00"
    memoria = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(dados))
    ponteiro = kernel32.GlobalLock(memoria)
    ctypes.memmove(ponteiro, dados, len(dados))
    kernel32.GlobalUnlock(memoria)
    if not _abrir_area_transferencia():
        kernel32.GlobalFree(memoria)
        return False
    try:
        user32.EmptyClipboard()
        if user32.SetClipboardData(CF_UNICODETEXT, memoria):
            return True
        kernel32.GlobalFree(memoria)
        return False
    finally:
        user32.CloseClipboard()


def _tecla(codigo: int, soltar: bool = False) -> INPUT:
    evento = INPUT(type=1)
    evento.u.ki = KEYBDINPUT(wVk=codigo, dwFlags=KEYEVENTF_KEYUP if soltar else 0)
    return evento


def aguardar_soltar_teclas(teclas: list[int], limite: float = 1.5) -> None:
    """Sem isso, Ctrl+C viraria Ctrl+Shift+C com o atalho ainda pressionado."""
    fim = time.monotonic() + limite
    while time.monotonic() < fim:
        if not any(user32.GetAsyncKeyState(t) & 0x8000 for t in teclas):
            return
        time.sleep(0.02)


def enviar_ctrl(letra: str) -> None:
    codigo = ord(letra.upper())
    eventos = (INPUT * 4)(_tecla(VK_CONTROL), _tecla(codigo), _tecla(codigo, True), _tecla(VK_CONTROL, True))
    user32.SendInput(4, eventos, ctypes.sizeof(INPUT))


def capturar_selecao(teclas_do_atalho: list[int]) -> tuple[str | None, str | None]:
    """Copia a seleção da janela ativa. Devolve (texto selecionado, conteúdo anterior)."""
    aguardar_soltar_teclas([VK_SHIFT, VK_CONTROL, VK_MENU, *teclas_do_atalho])
    anterior = ler_area_transferencia()

    def copiar() -> str | None:
        sequencia = user32.GetClipboardSequenceNumber()
        enviar_ctrl("c")
        fim = time.monotonic() + 0.4
        while time.monotonic() < fim:
            if user32.GetClipboardSequenceNumber() != sequencia:
                time.sleep(0.05)
                return ler_area_transferencia()
            time.sleep(0.02)
        return None

    texto = copiar()
    if texto is None:
        # Sem seleção, usa a mensagem inteira que está na caixa de texto.
        enviar_ctrl("a")
        time.sleep(0.05)
        texto = copiar()
    return texto, anterior


def colar_na_janela(janela, texto: str, anterior: str | None) -> None:
    gravar_area_transferencia(texto)
    user32.SetForegroundWindow(janela)
    time.sleep(0.15)
    enviar_ctrl("v")
    time.sleep(0.4)
    if anterior is not None:
        gravar_area_transferencia(anterior)


def posicao_cursor() -> tuple[int, int]:
    ponto = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(ponto))
    return ponto.x, ponto.y


def janela_ativa():
    return user32.GetForegroundWindow()


def instancia_unica() -> bool:
    kernel32.CreateMutexW(None, False, "CorretorTextoFerreiraAdvogados")
    return ctypes.get_last_error() != 183


def interpretar_atalho(atalho: str) -> tuple[int, int]:
    modificadores = {"ctrl": MOD_CONTROL, "shift": MOD_SHIFT, "alt": MOD_ALT, "win": MOD_WIN}
    partes = atalho.lower().replace(" ", "").split("+")
    mods = MOD_NOREPEAT
    for parte in partes[:-1]:
        mods |= modificadores[parte]
    return mods, ord(partes[-1].upper())


WH_KEYBOARD_LL, WH_MOUSE_LL = 13, 14
WM_KEYDOWN, WM_SYSKEYDOWN, WM_QUIT, WM_TIMER = 0x0100, 0x0104, 0x0012, 0x0113
WM_LBUTTONDOWN, WM_RBUTTONDOWN = 0x0201, 0x0204
LLKHF_INJECTED = 0x10
KEYEVENTF_UNICODE = 0x0004
VK_BACK, VK_RETURN, VK_CAPITAL = 0x08, 0x0D, 0x14
_MODIFICADORES = {0x10, 0x11, 0x12, 0x14, 0x5B, 0x5C, 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5}
_COMBINANTES = {"´": "́", "`": "̀", "~": "̃", "^": "̂", "¨": "̈"}
_NAO_ALTERAR_TECLADO = 0x4
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", wintypes.DWORD), ("scanCode", wintypes.DWORD), ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


_tipos(user32.SetWindowsHookExW, [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD], wintypes.HHOOK)
_tipos(user32.UnhookWindowsHookEx, [wintypes.HHOOK], wintypes.BOOL)
_tipos(user32.CallNextHookEx, [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM], LRESULT)
_tipos(user32.PostThreadMessageW, [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM], wintypes.BOOL)
_tipos(user32.InternalGetWindowText, [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int], ctypes.c_int)
_tipos(user32.SetTimer, [wintypes.HWND, ctypes.c_size_t, wintypes.UINT, wintypes.LPVOID], ctypes.c_size_t)
_tipos(kernel32.GetCurrentProcess, [], wintypes.HANDLE)
_tipos(kernel32.SetPriorityClass, [wintypes.HANDLE, wintypes.DWORD], wintypes.BOOL)
_tipos(user32.GetWindowThreadProcessId, [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)], wintypes.DWORD)
_tipos(user32.GetKeyboardLayout, [wintypes.DWORD], wintypes.HKL)
_tipos(user32.GetKeyState, [ctypes.c_int], ctypes.c_short)
_tipos(user32.ToUnicodeEx, [wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_ubyte), wintypes.LPWSTR,
                            ctypes.c_int, wintypes.UINT, wintypes.HKL], ctypes.c_int)
_tipos(kernel32.GetCurrentThreadId, [], wintypes.DWORD)


_tipos(user32.GetWindowLongPtrW, [wintypes.HWND, ctypes.c_int], ctypes.c_ssize_t)
_tipos(user32.SetWindowLongPtrW, [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t], ctypes.c_ssize_t)
GWL_EXSTYLE, WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE = -20, 0x00000080, 0x08000000


def janela_nossa(janela) -> bool:
    processo = wintypes.DWORD()
    user32.GetWindowThreadProcessId(janela, ctypes.byref(processo))
    return processo.value == os.getpid()


def voltar_para(janela) -> bool:
    """Devolve o foco ao chat. A seleção de texto continua lá."""
    user32.SetForegroundWindow(janela)
    fim = time.monotonic() + 0.5
    while time.monotonic() < fim:
        if user32.GetForegroundWindow() == janela:
            time.sleep(0.05)
            return True
        time.sleep(0.02)
    return False


def impedir_foco(janela) -> bool:
    """Clicar nesta janela não tira o foco do chat, então o texto continua selecionado."""
    estilo = user32.GetWindowLongPtrW(janela, GWL_EXSTYLE)
    user32.SetWindowLongPtrW(janela, GWL_EXSTYLE, estilo | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)
    return bool(user32.GetWindowLongPtrW(janela, GWL_EXSTYLE) & WS_EX_NOACTIVATE)


def titulo_janela(janela) -> str:
    # GetWindowText espera a janela responder. Com o chat ocupado, o Windows removeria o gancho por lentidão.
    buffer = ctypes.create_unicode_buffer(256)
    user32.InternalGetWindowText(janela, buffer, 256)
    return buffer.value


def registrar_erro() -> None:
    """Guarda só o erro e a linha do código, nunca o texto digitado."""
    with (config.DADOS / "registro.log").open("a", encoding="utf-8") as arquivo:
        arquivo.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}\n{traceback.format_exc()}\n")


def prioridade_alta() -> None:
    kernel32.SetPriorityClass(kernel32.GetCurrentProcess(), 0x00008000)


def _tecla_unicode(unidade: int, soltar: bool = False) -> INPUT:
    evento = INPUT(type=1)
    evento.u.ki = KEYBDINPUT(wScan=unidade, dwFlags=KEYEVENTF_UNICODE | (KEYEVENTF_KEYUP if soltar else 0))
    return evento


def substituir_digitado(apagar: int, escrever: str, enter: bool = False) -> int:
    """Apaga caracteres e escreve o texto na janela ativa, num único envio."""
    eventos = []
    for _ in range(apagar):
        eventos += [_tecla(VK_BACK), _tecla(VK_BACK, True)]
    dados = escrever.encode("utf-16-le")
    for indice in range(0, len(dados), 2):
        unidade = int.from_bytes(dados[indice:indice + 2], "little")
        eventos += [_tecla_unicode(unidade), _tecla_unicode(unidade, True)]
    if enter:
        eventos += [_tecla(VK_RETURN), _tecla(VK_RETURN, True)]
    if not eventos:
        return 0
    return user32.SendInput(len(eventos), (INPUT * len(eventos))(*eventos), ctypes.sizeof(INPUT))


def traduzir_tecla(vk: int, scan: int, janela) -> str:
    """Devolve o caractere da tecla, ou "´" e semelhantes para teclas de acento."""
    estado = (ctypes.c_ubyte * 256)()
    for tecla in (VK_SHIFT, VK_CONTROL, VK_MENU, 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5):
        if user32.GetAsyncKeyState(tecla) & 0x8000:
            estado[tecla] = 0x80
    if user32.GetKeyState(VK_CAPITAL) & 1:
        estado[VK_CAPITAL] = 1
    layout = user32.GetKeyboardLayout(user32.GetWindowThreadProcessId(janela, None))
    buffer = ctypes.create_unicode_buffer(8)
    # Com este sinalizador a consulta não consome o acento que o usuário acabou de digitar.
    total = user32.ToUnicodeEx(vk, scan, estado, buffer, 8, _NAO_ALTERAR_TECLADO, layout)
    return buffer.value[:abs(total)] if total else ""


def compor_acento(acento: str, tecla: str) -> str:
    """Reproduz o que o Windows escreve: ´ + a = á, ´ + espaço = ´, ´ + x = ´x."""
    if tecla == " ":
        return acento
    # O Windows às vezes já devolve a letra pronta. Somar o acento de novo criaria um caractere a mais.
    if tecla.startswith(acento) or unicodedata.normalize("NFD", tecla) != tecla:
        return tecla
    composto = unicodedata.normalize("NFC", tecla + _COMBINANTES.get(acento, ""))
    return composto if len(composto) == 1 else acento + tecla


class GanchoEntrada(threading.Thread):
    """Observa teclado e mouse. Nada é gravado, e as teclas seguem normalmente para o programa ativo."""

    REINSTALAR_MS = 15000

    def __init__(self, ao_teclar, ao_clicar):
        super().__init__(daemon=True)
        self.ao_teclar, self.ao_clicar = ao_teclar, ao_clicar
        self.pronto = threading.Event()
        self.instalado = False
        self.acento = ""

    def _classificar(self, dados: KBDLLHOOKSTRUCT) -> bool:
        """Devolve True quando a tecla deve ser retida."""
        vk = dados.vkCode
        if vk in _MODIFICADORES:
            return False
        ctrl = user32.GetAsyncKeyState(VK_CONTROL) & 0x8000
        alt = user32.GetAsyncKeyState(VK_MENU) & 0x8000
        win = user32.GetAsyncKeyState(0x5B) & 0x8000 or user32.GetAsyncKeyState(0x5C) & 0x8000
        if win or (ctrl and not alt):
            self.acento = ""
            self.ao_teclar("mover", None)
        elif vk == VK_RETURN:
            self.acento = ""
            if user32.GetAsyncKeyState(VK_SHIFT) & 0x8000:
                self.ao_teclar("quebra", None)
            else:
                return bool(self.ao_teclar("enter", None))
        elif vk == VK_BACK:
            self.acento = ""
            self.ao_teclar("apagar", None)
        else:
            texto = traduzir_tecla(vk, dados.scanCode, user32.GetForegroundWindow())
            if not texto or not texto.isprintable():
                self.acento = ""
                self.ao_teclar("mover", None)
            elif texto in _COMBINANTES and not self.acento:
                self.acento = texto
            else:
                if self.acento:
                    texto, self.acento = compor_acento(self.acento, texto), ""
                for caractere in texto:
                    self.ao_teclar("caractere", caractere)
        return False

    def _teclado(self, codigo, wparam, lparam):
        if codigo == 0 and wparam in (WM_KEYDOWN, WM_SYSKEYDOWN):
            dados = ctypes.cast(lparam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            if not dados.flags & LLKHF_INJECTED:
                try:
                    if self._classificar(dados):
                        return 1
                except Exception:
                    registrar_erro()  # uma falha aqui não pode travar o teclado
        return user32.CallNextHookEx(None, codigo, wparam, lparam)

    def _mouse(self, codigo, wparam, lparam):
        if codigo == 0 and wparam in (WM_LBUTTONDOWN, WM_RBUTTONDOWN):
            self.acento = ""
            self.ao_clicar()
        return user32.CallNextHookEx(None, codigo, wparam, lparam)

    def _instalar(self):
        instancia = kernel32.GetModuleHandleW(None)
        self._gancho_teclado = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._proc_teclado, instancia, 0)
        self._gancho_mouse = user32.SetWindowsHookExW(WH_MOUSE_LL, self._proc_mouse, instancia, 0)
        self.instalado = bool(self._gancho_teclado and self._gancho_mouse)

    def _remover(self):
        if self._gancho_teclado:
            user32.UnhookWindowsHookEx(self._gancho_teclado)
        if self._gancho_mouse:
            user32.UnhookWindowsHookEx(self._gancho_mouse)

    def run(self):
        self._id_thread = kernel32.GetCurrentThreadId()
        self._proc_teclado, self._proc_mouse = HOOKPROC(self._teclado), HOOKPROC(self._mouse)
        self._instalar()
        self.pronto.set()
        user32.SetTimer(None, 0, self.REINSTALAR_MS, None)
        mensagem = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(mensagem), None, 0, 0) > 0:
            if mensagem.message == WM_TIMER:
                # O Windows remove sem aviso um gancho que demorou, o que é comum com o processador cheio.
                self._remover()
                self._instalar()
        self._remover()

    def encerrar(self) -> None:
        if self.pronto.wait(2):
            user32.PostThreadMessageW(self._id_thread, WM_QUIT, 0, 0)


class Bandeja(threading.Thread):
    """Ícone da bandeja e atalhos globais, que precisam de uma fila de mensagens própria."""

    def __init__(self, atalhos: list[tuple[str, str]], menu, ao_acionar):
        super().__init__(daemon=True)
        self.atalhos, self.menu, self.ao_acionar = atalhos, menu, ao_acionar
        self.janela = None
        self.falhas: list[str] = []
        self.pronta = threading.Event()
        self._icone = None

    def _procedimento(self, janela, mensagem, wparam, lparam):
        if mensagem == WM_HOTKEY:
            self.ao_acionar(self.atalhos[wparam][0])
            return 0
        if mensagem == WM_BANDEJA and lparam in (WM_RBUTTONUP, WM_LBUTTONUP):
            self._abrir_menu()
            return 0
        if mensagem == WM_CLOSE:
            user32.DestroyWindow(janela)
            return 0
        if mensagem == WM_DESTROY:
            shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._icone))
            for indice in range(len(self.atalhos)):
                user32.UnregisterHotKey(janela, indice)
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(janela, mensagem, wparam, lparam)

    def _abrir_menu(self):
        itens = self.menu()
        menu = user32.CreatePopupMenu()
        for indice, (rotulo, _) in enumerate(itens, start=1):
            user32.AppendMenuW(menu, 0, indice, rotulo)
        x, y = posicao_cursor()
        user32.SetForegroundWindow(self.janela)
        escolha = user32.TrackPopupMenu(menu, TPM_RETURNCMD | TPM_NONOTIFY, x, y, 0, self.janela, None)
        user32.DestroyMenu(menu)
        if escolha:
            self.ao_acionar(itens[escolha - 1][1])

    def run(self):
        instancia = kernel32.GetModuleHandleW(None)
        self._wndproc = WNDPROC(self._procedimento)
        classe = WNDCLASSW(lpfnWndProc=self._wndproc, hInstance=instancia, lpszClassName="CorretorTextoBandeja")
        user32.RegisterClassW(ctypes.byref(classe))
        self.janela = user32.CreateWindowExW(0, "CorretorTextoBandeja", "Corretor", 0, 0, 0, 0, 0,
                                             None, None, instancia, None)
        for indice, (_, atalho) in enumerate(self.atalhos):
            mods, tecla = interpretar_atalho(atalho)
            if not user32.RegisterHotKey(self.janela, indice, mods, tecla):
                self.falhas.append(atalho)
        self._icone = NOTIFYICONDATAW(cbSize=ctypes.sizeof(NOTIFYICONDATAW), hWnd=self.janela, uID=1,
                                      uFlags=NIF_MESSAGE | NIF_ICON | NIF_TIP, uCallbackMessage=WM_BANDEJA,
                                      hIcon=user32.LoadIconW(None, ctypes.cast(IDI_APPLICATION, wintypes.LPCWSTR)),
                                      szTip="Corretor de texto")
        shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(self._icone))
        self.pronta.set()
        mensagem = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(mensagem), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(mensagem))
            user32.DispatchMessageW(ctypes.byref(mensagem))

    def notificar(self, titulo: str, texto: str) -> None:
        self._icone.uFlags = NIF_INFO
        self._icone.szInfoTitle = titulo[:63]
        self._icone.szInfo = texto[:255]
        shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(self._icone))

    def encerrar(self) -> None:
        if self.janela:
            user32.PostMessageW(self.janela, WM_CLOSE, 0, 0)
