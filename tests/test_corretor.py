import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from corretor import atualizacao, config, correcao, janelas, reformulacao, regras, verificacao


class Regras(unittest.TestCase):
    def setUp(self):
        self.regras = regras.carregar()

    def corrigir(self, texto):
        return regras.aplicar(texto, self.regras)[0]

    def test_troca_mantendo_maiuscula(self):
        self.assertEqual(self.corrigir("Vc pode vir"), "Você pode vir")

    def test_concordancia_tempo(self):
        self.assertEqual(self.corrigir("Fazem 3 meses que protocolei"), "Faz 3 meses que protocolei")

    def test_nao_altera_parte_de_palavra(self):
        self.assertEqual(self.corrigir("o agente público"), "o agente público")

    def test_crase_e_acentos_que_o_languagetool_nao_pega(self):
        self.assertEqual(self.corrigir("Vou as 14h"), "Vou às 14h")
        self.assertEqual(self.corrigir("enviados ontem a noite"), "enviados ontem à noite")
        self.assertEqual(self.corrigir("o processo esta em andamento"), "o processo está em andamento")
        self.assertEqual(self.corrigir("esta procuração"), "esta procuração")
        self.assertEqual(self.corrigir("assinatura amanha"), "assinatura amanhã")

    def test_a_gente(self):
        self.assertEqual(self.corrigir("agente vai ao fórum"), "a gente vai ao fórum")


class AplicarAchados(unittest.TestCase):
    def test_posicoes_depois_de_emoji(self):
        # O emoji ocupa duas posições em UTF-16: "testo" começa na posição 3.
        achados = [{"offset": 3, "length": 5, "message": "Grafia", "replacements": [{"value": "texto"}]}]
        self.assertEqual(correcao.aplicar_achados("😀 testo final", achados, [])[0], "😀 texto final")

    def test_varias_correcoes(self):
        achados = [
            {"offset": 0, "length": 2, "message": "", "replacements": [{"value": "AA"}]},
            {"offset": 3, "length": 2, "message": "", "replacements": [{"value": "BBBB"}]},
        ]
        self.assertEqual(correcao.aplicar_achados("aa bb", achados, [])[0], "AA BBBB")

    def test_termo_ignorado(self):
        achados = [{"offset": 0, "length": 4, "message": "", "replacements": [{"value": "Ezra"}]}]
        self.assertEqual(correcao.aplicar_achados("Ezer disse", achados, ["ezer"])[0], "Ezer disse")


class Verificacao(unittest.TestCase):
    def test_valor_alterado(self):
        avisos = verificacao.comparar("Os honorários são R$ 1.500,00.", "Os honorários são R$ 1.800,00.")
        self.assertTrue(any("removido: 1.500,00" in a for a in avisos))
        self.assertTrue(any("acrescentado: 1.800,00" in a for a in avisos))

    def test_data_por_extenso(self):
        avisos = verificacao.comparar("A audiência é na segunda.", "A audiência é na terça.")
        self.assertTrue(any("data" in a for a in avisos))

    def test_negacao_removida(self):
        avisos = verificacao.comparar("O juiz não aceitou o pedido.", "O juiz aceitou o pedido.")
        self.assertTrue(any("negações" in a for a in avisos))

    def test_nao_sem_acento_conta_como_negacao(self):
        self.assertEqual(verificacao.comparar("Ele nao pagou.", "Ele não pagou."), [])

    def test_limpa_raciocinio_da_resposta(self):
        self.assertEqual(reformulacao.limpar_resposta("<think>\n\n</think>\n\nTexto final."), "Texto final.")

    def test_nome_removido(self):
        avisos = verificacao.comparar("Falei com a Dra. Mariana ontem e com Pedro.", "Falei com a advogada ontem.")
        self.assertTrue(any("Pedro" in a for a in avisos))

    def test_sem_mudanca_relevante(self):
        self.assertEqual(verificacao.comparar("Envie o documento até dia 10.", "Por favor, envie o documento até dia 10."), [])

    def test_destaque_recompoe_os_textos(self):
        a, b = verificacao.trechos("eu vai hoje", "eu vou hoje")
        self.assertEqual("".join(t for t, _ in a), "eu vai hoje")
        self.assertEqual("".join(t for t, _ in b), "eu vou hoje")
        self.assertIn(("vou", True), b)


class Atualizacao(unittest.TestCase):
    def test_pendentes(self):
        manifesto = {"componentes": {"a": {"versao": "1.10.0"}, "b": {"versao": "1.0.0"}, "c": {"versao": "2.0"}}}
        self.assertEqual(set(atualizacao.pendentes(manifesto, {"a": "1.9.0", "b": "1.0.0"})), {"a", "c"})

    def test_recusa_http(self):
        with self.assertRaises(ValueError):
            atualizacao.verificar("http://exemplo.com/manifesto.json")

    def test_recusa_zip_com_caminho_inseguro(self):
        with tempfile.TemporaryDirectory() as pasta:
            pasta = Path(pasta)
            pacote = pasta / "ruim.zip"
            with zipfile.ZipFile(pacote, "w") as z:
                z.writestr("../fora.txt", "x")
            with self.assertRaises(ValueError):
                atualizacao.extrair_com_seguranca(pacote, pasta / "destino")
            self.assertFalse((pasta / "fora.txt").exists())

    def _instalar(self, sha):
        with tempfile.TemporaryDirectory() as pasta:
            pasta = Path(pasta)
            pacote = pasta / "regras.zip"
            with zipfile.ZipFile(pacote, "w") as z:
                z.writestr("regras.json", "{}")
            componentes = pasta / "componentes"
            (componentes / "regras").mkdir(parents=True)
            (componentes / "regras" / "antigo.txt").write_text("antigo")

            def baixar(url, destino, progresso=None):
                destino.write_bytes(pacote.read_bytes())
                return hashlib.sha256(pacote.read_bytes()).hexdigest()

            info = {"versao": "1.0.0", "url": "https://x/regras.zip", "sha256": sha or hashlib.sha256(pacote.read_bytes()).hexdigest()}
            with mock.patch.object(config, "COMPONENTES", componentes), \
                 mock.patch.object(config, "VERSOES", componentes / "versoes.json"), \
                 mock.patch.object(atualizacao, "_baixar", baixar):
                try:
                    atualizacao.instalar("regras", info)
                    erro = None
                except ValueError as e:
                    erro = e
            return erro, sorted(p.name for p in (componentes / "regras").iterdir())

    def test_instala_e_troca(self):
        erro, arquivos = self._instalar(None)
        self.assertIsNone(erro)
        self.assertEqual(arquivos, ["regras.json"])

    def test_hash_errado_mantem_o_atual(self):
        erro, arquivos = self._instalar("0" * 64)
        self.assertIsNotNone(erro)
        self.assertEqual(arquivos, ["antigo.txt"])


class Janelas(unittest.TestCase):
    def test_atalho(self):
        mods, tecla = janelas.interpretar_atalho("ctrl+shift+1")
        self.assertEqual(tecla, ord("1"))
        self.assertTrue(mods & janelas.MOD_CONTROL and mods & janelas.MOD_SHIFT)


if __name__ == "__main__":
    unittest.main()
