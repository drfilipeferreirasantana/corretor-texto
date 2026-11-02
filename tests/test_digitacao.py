import json
import unittest

from corretor import config, digitacao, janelas
from corretor.digitacao import Motor


class Tela:
    """Simula a caixa de texto do chat, aplicando o que o motor manda fazer."""

    def __init__(self, motor):
        self.motor, self.texto, self.consultas = motor, "", []

    def aplicar(self, acao):
        if acao:
            self.texto = self.texto[:len(self.texto) - acao.apagar] + acao.escrever

    def digitar(self, texto):
        for caractere in texto:
            self.texto += caractere
            acao, consulta = self.motor.digitar(caractere)
            self.aplicar(acao)
            if consulta:
                self.consultas.append(consulta)

    def apagar(self):
        self.texto = self.texto[:-1]
        self.aplicar(self.motor.apagar())


def tela(ignorar=None):
    return Tela(Motor({"altomaticamente": "automaticamente", "voce": "você", "concerteza": "com certeza"}, ignorar))


class MotorDigitacao(unittest.TestCase):
    def test_exemplo_do_pedido(self):
        t = tela()
        t.digitar("gostaria que corrija altomaticamente ")
        self.assertEqual(t.texto, "Gostaria que corrija automaticamente ")

    def test_maiuscula_depois_de_ponto(self):
        t = tela()
        t.digitar("Certo. amanhã eu ligo! depois vejo ")
        self.assertEqual(t.texto, "Certo. Amanhã eu ligo! Depois vejo ")

    def test_mantem_pontuacao_junto_da_palavra(self):
        t = tela()
        t.digitar("Olá, voce, tudo bem? ")
        self.assertEqual(t.texto, "Olá, você, tudo bem? ")

    def test_mantem_caixa(self):
        t = tela()
        t.digitar("Certo Voce VOCE ")
        self.assertEqual(t.texto, "Certo Você VOCÊ ")

    def test_nao_coloca_maiuscula_depois_de_abreviacao(self):
        t = tela()
        t.digitar("Fale com o dr. pedro hoje ")
        self.assertEqual(t.texto, "Fale com o dr. pedro hoje ")

    def test_nao_mexe_em_site_email_e_numero(self):
        for texto in ["www.exemplo.com.br ", "contato@exemplo.com ", "5001234-56.2026.8.08.0030 ", "R$1.500,00 "]:
            t = tela()
            t.digitar(texto)
            self.assertEqual(t.texto, texto)

    def test_emoji_nao_desalinha(self):
        t = tela()
        t.digitar("😀 ")
        self.assertEqual(t.texto, "😀 ")

    def test_backspace_desfaz_a_correcao_e_nao_repete(self):
        t = tela()
        t.digitar("Certo voce ")
        self.assertEqual(t.texto, "Certo você ")
        t.apagar()
        self.assertEqual(t.texto, "Certo voce")
        t.digitar(" e voce ")
        self.assertEqual(t.texto, "Certo voce e voce ")

    def test_backspace_desfaz_maiuscula_so_uma_vez(self):
        t = tela()
        t.digitar("gostaria ")
        t.apagar()
        self.assertEqual(t.texto, "gostaria")
        t.digitar(" muito. gostaria ")
        self.assertEqual(t.texto, "gostaria muito. Gostaria ")

    def test_palavra_corrigida_manualmente(self):
        t = tela()
        t.digitar("Certo vocx")
        t.apagar()
        t.digitar("e ")
        self.assertEqual(t.texto, "Certo você ")

    def test_enter_inicia_nova_frase(self):
        t = tela()
        t.digitar("Certo ")
        t.motor.nova_mensagem()
        t.texto = ""
        t.digitar("gostaria ")
        self.assertEqual(t.texto, "Gostaria ")

    def test_seta_nao_coloca_maiuscula(self):
        t = tela()
        t.motor.cursor_movido()
        t.digitar("gostaria ")
        self.assertEqual(t.texto, "gostaria ")

    def test_termo_ignorado(self):
        t = tela(["voce"])
        t.digitar("Certo voce ")
        self.assertEqual(t.texto, "Certo voce ")


class Contexto(unittest.TestCase):
    def tela(self):
        # Lê as regras do projeto, e não as de uma versão já instalada em componentes/.
        regras = json.loads((config.DADOS / "regras.json").read_text(encoding="utf-8"))
        return Tela(Motor({"voce": "você", "mae": "mãe", "nao": "não", "amem": "amém"}, regras.get("ignorar", []), regras, True))

    def test_e_verbo_com_contexto(self):
        t = self.tela()
        t.digitar("voce e uma bênção ")
        self.assertEqual(t.texto, "Você é uma bênção ")

    def test_e_conjuncao_nao_muda(self):
        t = self.tela()
        t.digitar("Você e a sua filha e eu ")
        self.assertEqual(t.texto, "Você e a sua filha e eu ")

    def test_isso_e_aquilo_nao_muda(self):
        t = self.tela()
        t.digitar("Isso e aquilo ")
        self.assertEqual(t.texto, "Isso e aquilo ")

    def test_isso_e_muito_importante(self):
        t = self.tela()
        t.digitar("Certo isso e muito importante ")
        self.assertEqual(t.texto, "Certo isso é muito importante ")

    def test_nao_e(self):
        t = self.tela()
        t.digitar("Certo nao e simples ")
        self.assertEqual(t.texto, "Certo não é simples ")

    def test_valor_e(self):
        t = self.tela()
        t.digitar("O valor e R$ 100 ")
        self.assertEqual(t.texto, "O valor é R$ 100 ")

    def test_e_verdade_depois_de_ponto(self):
        t = self.tela()
        t.digitar("Colocar vírgula. e verdade viu ")
        self.assertEqual(t.texto, "Colocar vírgula. É verdade viu ")

    def test_crase_de_hora_ao_digitar(self):
        t = self.tela()
        t.digitar("Vou as 14h ")
        self.assertEqual(t.texto, "Vou às 14h ")

    def test_desfazer_contexto(self):
        t = self.tela()
        t.digitar("Certo isso e muito ")
        self.assertEqual(t.texto, "Certo isso é muito ")
        t.apagar()
        self.assertEqual(t.texto, "Certo isso e muito")
        t.digitar(" bom ")
        self.assertEqual(t.texto, "Certo isso e muito bom ")

    def enter(self, t):
        acao = t.motor.finalizar()
        if acao:
            self.assertTrue(acao.enter)
            t.aplicar(acao)
        return acao

    def test_ultima_palavra_ao_enviar(self):
        t = self.tela()
        t.digitar("Amem minha mae")
        self.assertIsNotNone(self.enter(t))
        self.assertEqual(t.texto, "Amém minha mãe")

    def test_ponto_final_ao_enviar(self):
        t = self.tela()
        t.digitar("Vou enviar o contrato amanhã")
        self.enter(t)
        self.assertEqual(t.texto, "Vou enviar o contrato amanhã.")

    def test_ponto_final_com_espaco_no_fim(self):
        t = self.tela()
        t.digitar("Vou enviar o contrato amanhã ")
        self.enter(t)
        self.assertEqual(t.texto, "Vou enviar o contrato amanhã.")

    def test_mensagem_curta_sem_ponto(self):
        t = self.tela()
        t.digitar("Bom dia")
        self.assertIsNone(self.enter(t))
        self.assertEqual(t.texto, "Bom dia")

    def test_nao_pontua_pergunta_link_ou_numero(self):
        for texto in ["Você vai ao fórum hoje?", "Veja o site www.exemplo.com.br", "O valor total é 100", "Pode vir amanhã 😀"]:
            t = self.tela()
            t.digitar(texto)
            self.enter(t)
            self.assertEqual(t.texto, texto)

    def test_inicio_de_frase_na_ultima_palavra(self):
        t = self.tela()
        t.digitar("gostaria")
        self.enter(t)
        self.assertEqual(t.texto, "Gostaria")

    def test_nova_mensagem_depois_de_enviar(self):
        t = self.tela()
        t.digitar("Bom dia")
        self.enter(t)
        t.texto = ""
        t.digitar("gostaria ")
        self.assertEqual(t.texto, "Gostaria ")


class RespostaOrtografia(unittest.TestCase):
    def test_palavra_desconhecida_corrigida_depois(self):
        t = tela()
        t.digitar("Certo testo ")
        consulta = t.consultas[-1]
        self.assertEqual(consulta.nucleo, "testo")
        t.aplicar(t.motor.resposta_consulta(consulta.numero, "texto"))
        self.assertEqual(t.texto, "Certo texto ")

    def test_resposta_tardia_preserva_o_que_veio_depois(self):
        t = tela()
        t.digitar("Certo testo fin")
        t.aplicar(t.motor.resposta_consulta(t.consultas[-1].numero, "texto"))
        self.assertEqual(t.texto, "Certo texto fin")
        t.digitar("al ")
        self.assertEqual(t.texto, "Certo texto final ")

    def test_resposta_com_maiuscula_de_inicio(self):
        t = tela()
        t.digitar("testo ")
        self.assertEqual(t.texto, "Testo ")
        t.aplicar(t.motor.resposta_consulta(t.consultas[-1].numero, "texto"))
        self.assertEqual(t.texto, "Texto ")

    def test_descarta_resposta_apos_apagar(self):
        t = tela()
        t.digitar("Certo testo ")
        numero = t.consultas[-1].numero
        t.apagar()
        self.assertIsNone(t.motor.resposta_consulta(numero, "texto"))

    def test_descarta_resposta_apos_clique(self):
        t = tela()
        t.digitar("Certo testo ")
        numero = t.consultas[-1].numero
        t.motor.nova_mensagem()
        self.assertIsNone(t.motor.resposta_consulta(numero, "texto"))

    def test_descarta_resposta_se_outra_correcao_mudou_a_tela(self):
        t = tela()
        t.digitar("Certo testo concerteza ")
        self.assertEqual(t.texto, "Certo testo com certeza ")
        self.assertIsNone(t.motor.resposta_consulta(t.consultas[0].numero, "texto"))

    def test_nome_proprio_nao_consulta(self):
        t = tela()
        t.digitar("Falei com Mariana ")
        self.assertNotIn("Mariana", [c.nucleo for c in t.consultas])


class Janela(unittest.TestCase):
    def test_so_atua_em_chats(self):
        permitidos = ["WhatsApp"]
        self.assertTrue(digitacao.janela_permitida("(3) WhatsApp - Google Chrome", permitidos))
        self.assertFalse(digitacao.janela_permitida("Banco - Login - Google Chrome", permitidos))

    def test_acentos(self):
        self.assertEqual(janelas.compor_acento("´", "a"), "á")
        self.assertEqual(janelas.compor_acento("~", "o"), "õ")
        self.assertEqual(janelas.compor_acento("^", "E"), "Ê")
        self.assertEqual(janelas.compor_acento("´", " "), "´")
        self.assertEqual(janelas.compor_acento("´", "x"), "´x")

    def test_acento_que_o_windows_ja_compos(self):
        self.assertEqual(janelas.compor_acento("´", "é"), "é")
        self.assertEqual(janelas.compor_acento("´", "´e"), "´e")


if __name__ == "__main__":
    unittest.main()
