import unittest

from src.article_search import Busca, extrair_palavras_chave


class KeywordTests(unittest.TestCase):
    def test_normalizes_and_deduplicates_in_original_order(self):
        self.assertEqual(
            extrair_palavras_chave('VPN, conexão VPN: instalar WI-FI, Wi Fi e wifi!'),
            ['vpn', 'conexao', 'instalar', 'wifi'],
        )

    def test_email_spellings_match(self):
        for word in ('email', 'e-mail', 'E-MAIL', 'e mail'):
            with self.subTest(word=word):
                self.assertEqual(extrair_palavras_chave(f'Assinatura de {word}'),
                                 ['assinatura', 'email'])

    def test_removes_greeting_but_preserves_useful_terms(self):
        self.assertEqual(
            extrair_palavras_chave('Olá, bom dia! Estou tentando configurar VPN no Windows.'),
            ['configurar', 'vpn', 'windows'],
        )
        self.assertEqual(extrair_palavras_chave('Backup por dia'), ['backup', 'dia'])

    def test_validates_text_before_processing(self):
        for value in (None, 42, [], {}, True, '', ' \n\t '):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    extrair_palavras_chave(value)

    def test_length_boundary(self):
        self.assertEqual(extrair_palavras_chave('vpn ' * 1000), ['vpn'])
        with self.assertRaises(ValueError):
            extrair_palavras_chave('vpn ' * 1000 + 'a')


class KeywordSearchTests(unittest.TestCase):
    def setUp(self):
        self.busca = Busca([
            {'id': 1, 'name': 'Configurar VPN Windows', 'content': 'Configurar VPN no Windows.'},
            {'id': 2, 'name': 'Configurar VPN macOS', 'content': 'Configurar VPN no macOS.'},
            {'id': 3, 'name': 'Assinatura de email', 'content': 'Configurar a assinatura.'},
            {'id': 4, 'name': 'Problemas de Wi-Fi', 'content': 'Conexao wifi.'},
        ])

    def test_natural_question_finds_platform_article(self):
        question = 'Oi, bom dia, estou tentando configurar a VPN no Windows e preciso de ajuda'
        self.assertEqual([item['id'] for item in self.busca.pesquisar(question)], [1])

    def test_polite_request_preserves_topic(self):
        question = 'Você poderia me ajudar a configurar VPN no Windows, por favor?'
        self.assertEqual([item['id'] for item in self.busca.pesquisar(question)], [1])

    def test_spelling_variants_find_articles(self):
        for question, article_id in (
            ('Como configurar assinatura de e-mail?', 3),
            ('Wi Fi', 4),
            ('WI-FI', 4),
        ):
            with self.subTest(question=question):
                self.assertEqual([item['id'] for item in self.busca.pesquisar(question)],
                                 [article_id])

    def test_unknown_topic_is_preserved_and_returns_no_articles(self):
        question = 'Olá, bom dia! Estou tentando configurar telescópio no Windows.'
        self.assertIn('telescopio', extrair_palavras_chave(question))
        self.assertEqual(self.busca.pesquisar(question), [])

    def test_greeting_and_generic_question_return_no_articles(self):
        for question in ('Olá, bom dia!', 'Como configurar?'):
            with self.subTest(question=question):
                self.assertEqual(self.busca.pesquisar(question), [])


if __name__ == '__main__':
    unittest.main()
