import unittest
from src.article_search import Busca
from src.knowledge_cli import fetch_articles
from src.answer_context import preparar, validar_resposta
import json

class KnowledgeTests(unittest.TestCase):
    def test_platforms(self):
        busca = Busca([{'id':1,'name':'VPN Windows','content':'Configurar VPN Windows'}, {'id':2,'name':'VPN macOS','content':'Configurar VPN macOS'}])
        self.assertEqual(busca.pesquisar('VPN Windows')[0]['id'],1)
        self.assertEqual(busca.pesquisar('VPN macOS')[0]['id'],2)
        self.assertEqual(busca.pesquisar('bolo chocolate'),[])

    def test_pagination(self):
        class Client:
            def knowledgebase_articles(self, start, limit):
                return {'status_code':206 if start == 0 else 200, 'data':[{'id':i} for i in range(3)][start:start+limit]}
        self.assertEqual(len(fetch_articles(Client(),2)),3)

    def test_duplicate_page(self):
        class Client:
            def knowledgebase_articles(self, start, limit):
                return {'status_code':206,'data':[{'id':1}]}
        with self.assertRaises(ValueError):
            fetch_articles(Client(),1)

    def test_http_error(self):
        class Client:
            def knowledgebase_articles(self, start, limit):
                return {'status_code':403,'data':{}}
        with self.assertRaises(ValueError):
            fetch_articles(Client())

    def test_unknown_citation(self):
        with self.assertRaises(ValueError):
            validar_resposta(json.dumps({'status':'respondido','resposta':'[Artigo 999]','fontes':[999]}),[{'id':1}])

    def test_no_context_without_results(self):
        self.assertEqual(preparar(Busca([]),'VPN')['mensagens'],[])


class RelevanceTests(unittest.TestCase):
    def setUp(self):
        self.busca = Busca([
            {'id':1,'name':'Configurar VPN Windows','content':'Configurar VPN no Windows.'},
            {'id':2,'name':'Configurar VPN macOS','content':'Configurar VPN no macOS.'},
            {'id':5,'name':'Instalar impressora Windows','content':'Conecte a impressora. Requer VPN.'},
            {'id':22,'name':'Configurar assinatura de email','content':'Use configurações de assinatura.'},
        ])

    def test_vpn_excludes_incidental_mentions(self):
        self.assertEqual([r['id'] for r in self.busca.pesquisar('Como configurar VPN no Windows?')], [1])

    def test_broad_vpn_keeps_both_platforms(self):
        self.assertEqual({r['id'] for r in self.busca.pesquisar('VPN')}, {1,2})

    def test_unknown_topic_with_shared_words(self):
        self.assertEqual(self.busca.pesquisar('Como configurar telescópio no Windows?'), [])

    def test_generic_question(self):
        self.assertEqual(self.busca.pesquisar('Como configurar?'), [])

    def test_title_is_not_required(self):
        busca = Busca([{'id':1,'name':'Conexão remota','content':'Procedimento VPN.'}])
        self.assertEqual(busca.pesquisar('VPN')[0]['id'],1)

    def test_limit_is_enforced(self):
        self.assertEqual(len(self.busca.pesquisar('VPN', limite=1)),1)

if __name__ == '__main__':
    unittest.main()
