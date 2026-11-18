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


class ConjugatedVerbTests(unittest.TestCase):
    """Perguntas reais usam verbos conjugados; os títulos dos artigos usam o infinitivo."""

    def setUp(self):
        self.busca = Busca([
            {'id': 1, 'name': 'Configurar a VPN corporativa no Windows', 'content': 'Instale o cliente VPN.'},
            {'id': 3, 'name': 'Redefinir a senha de rede pelo autoatendimento', 'content': 'Acesse o portal.'},
            {'id': 5, 'name': 'Instalar impressora de rede no Windows', 'content': 'Adicione a impressora.'},
            {'id': 22, 'name': 'Configurar assinatura padrão de e-mail', 'content': 'Abra o Outlook.'},
            {'id': 39, 'name': 'Mouse ou teclado com defeito', 'content': 'Troque as pilhas.'},
        ])

    def ids(self, pergunta):
        return [item['id'] for item in self.busca.pesquisar(pergunta)]

    def test_conjugations_match_infinitive_titles(self):
        for pergunta, esperado in (
            ('Como configuro a VPN?', [1]),
            ('Configurei a VPN no Windows', [1]),
            ('Como reseto minha senha?', [3]),
            ('Como resetar minha senha?', [3]),
            ('Como redefino minha senha?', [3]),
            ('Como instalo a impressora de rede?', [5]),
        ):
            with self.subTest(pergunta=pergunta):
                self.assertEqual(self.ids(pergunta), esperado)

    def test_change_verbs_do_not_hide_the_subject(self):
        for pergunta in ('Quero alterar minha senha', 'Como mudo minha senha?', 'Como troco minha senha?'):
            with self.subTest(pergunta=pergunta):
                self.assertEqual(self.ids(pergunta), [3])

    def test_keywords_use_canonical_verb(self):
        self.assertEqual(extrair_palavras_chave('Como reseto minha senha?'), ['redefinir', 'senha'])
        self.assertEqual(extrair_palavras_chave('Configurei a VPN mas não conecta'),
                         ['configurar', 'vpn', 'conectar'])

    def test_generic_verbs_alone_still_return_nothing(self):
        for pergunta in ('Como configuro?', 'Quero trocar', 'Como configuro o telescópio?'):
            with self.subTest(pergunta=pergunta):
                self.assertEqual(self.ids(pergunta), [])


if __name__ == '__main__':
    unittest.main()
