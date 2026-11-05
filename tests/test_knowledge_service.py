import unittest
from unittest.mock import Mock

from src.knowledge_service import ArticlesFetchError, fetch_articles, processar_pergunta


class KnowledgeServiceTests(unittest.TestCase):
    def test_invalid_question_never_calls_glpi(self):
        for question in (None, 1, '', '   ', 'x' * 4001):
            with self.subTest(question_type=type(question).__name__):
                client = Mock()
                with self.assertRaises(ValueError):
                    processar_pergunta(question, client)
                client.knowledgebase_articles.assert_not_called()

    def test_exact_page_size_requires_next_page(self):
        client = Mock()
        client.knowledgebase_articles.side_effect = [
            {'status_code': 200, 'data': [{'id': 1, 'name': 'VPN'}]},
            {'status_code': 200, 'data': []},
        ]
        self.assertEqual(len(fetch_articles(client, page_size=1)), 1)
        self.assertEqual(client.knowledgebase_articles.call_count, 2)
        client.knowledgebase_articles.assert_called_with(start=1, limit=1)

    def test_page_limit_fails_without_partial_result(self):
        client = Mock()
        client.knowledgebase_articles.side_effect = [
            {'status_code': 206, 'data': [{'id': 1, 'name': 'VPN'}]},
            {'status_code': 206, 'data': [{'id': 2, 'name': 'Email'}]},
        ]
        with self.assertRaisesRegex(ArticlesFetchError, 'limite de páginas'):
            fetch_articles(client, page_size=1, max_pages=2)
        self.assertEqual(client.knowledgebase_articles.call_count, 2)

    def test_second_page_failure_is_not_treated_as_success(self):
        client = Mock()
        client.knowledgebase_articles.side_effect = [
            {'status_code': 206, 'data': [{'id': 1, 'name': 'VPN'}]},
            {'status_code': 401, 'data': {'secret': 'not-for-the-caller'}},
        ]
        with self.assertRaises(ArticlesFetchError) as error:
            fetch_articles(client, page_size=1)
        self.assertEqual(error.exception.status_code, 401)
        self.assertNotIn('not-for-the-caller', str(error.exception))

    def test_invalid_response_envelopes(self):
        for response in (None, {}, {'status_code': True}, {'status_code': 200, 'data': {}},
                         {'status_code': 200, 'data': [{'id': True, 'name': 'VPN'}]}):
            with self.subTest(response=response):
                client = Mock()
                client.knowledgebase_articles.return_value = response
                with self.assertRaises(ArticlesFetchError):
                    fetch_articles(client)

    def test_pagination_arguments_checked_before_call(self):
        for arguments in ({'page_size': 0}, {'page_size': 201}, {'page_size': True},
                          {'max_pages': 0}, {'max_pages': True}):
            with self.subTest(arguments=arguments):
                client = Mock()
                with self.assertRaises(ValueError):
                    fetch_articles(client, **arguments)
                client.knowledgebase_articles.assert_not_called()


if __name__ == '__main__':
    unittest.main()
