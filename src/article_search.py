"""Busca lexical local de artigos; não gera respostas nem chama uma IA."""
import argparse
import json
import math
import re
import unicodedata
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path


class TextoHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.partes = []
        self.ignorar = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.ignorar += 1
        elif tag in ('p', 'br', 'li', 'h1', 'h2', 'h3', 'div', 'tr'):
            self.partes.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style') and self.ignorar:
            self.ignorar -= 1
        elif tag in ('p', 'li', 'h1', 'h2', 'h3', 'div', 'tr'):
            self.partes.append('\n')

    def handle_data(self, data):
        if not self.ignorar:
            self.partes.append(data)


def texto_html(html):
    parser = TextoHTML()
    parser.feed(html)
    return '\n'.join(' '.join(linha.split()) for linha in ''.join(parser.partes).splitlines() if linha.strip())


STOP = set('a o as os de da do das dos e em no na nos nas um uma para por com que como qual quais eu meu minha meus minhas se ao aos pelo pela preciso quero fazer esta estou nao'.split())
# Verbos genéricos e plataforma ajudam a ordenar, mas não definem o assunto.
GENERICOS = set('configurar instalar acessar usar funciona funcionar windows macos favor ajuda gostaria saber posso pode consigo'.split())
SINONIMOS = {'lenta': 'lentidao', 'lento': 'lentidao', 'lentissima': 'lentidao',
             'lentissimo': 'lentidao', 'mac': 'macos', 'wi': 'wifi'}


def tokens(texto):
    texto = ''.join(c for c in unicodedata.normalize('NFKD', texto.lower()) if not unicodedata.combining(c))
    texto = texto.replace('wi-fi', 'wifi')
    return [SINONIMOS.get(t, t) for t in re.findall(r'[a-z0-9]+', texto) if t not in STOP and len(t) > 1]


class Busca:
    def __init__(self, artigos):
        self.docs = []
        self.frequencia = Counter()
        for artigo in artigos:
            titulo = artigo['name']
            conteudo = texto_html(artigo.get('content') or '')
            termos_titulo = set(tokens(titulo))
            termos = tokens(titulo) * 3 + tokens(conteudo)
            frequencias = Counter(termos)
            self.frequencia.update(frequencias.keys())
            self.docs.append({'id': artigo['id'], 'titulo': titulo, 'conteudo': conteudo,
                              'termos_titulo': termos_titulo, 'tf': frequencias, 'tamanho': len(termos)})
        self.media = sum(d['tamanho'] for d in self.docs) / max(1, len(self.docs)) or 1

    def pesquisar(self, pergunta, limite=3):
        consulta = set(tokens(pergunta))
        if limite < 1:
            raise ValueError('O limite deve ser positivo.')
        # Inclui palavras desconhecidas: Windows sozinho não sustenta uma
        # pergunta sobre um assunto ausente, como configurar um telescópio.
        assunto = consulta - GENERICOS
        if not assunto:
            return []
        resultados = []
        plataformas = consulta & {'windows', 'macos'}
        for doc in self.docs:
            plataforma_doc = doc['termos_titulo'] & {'windows', 'macos'}
            if plataformas and plataforma_doc and plataformas.isdisjoint(plataforma_doc):
                continue
            score = 0.0
            encontrados = consulta & doc['tf'].keys()
            cobertura = len(assunto & encontrados) / len(assunto)
            if cobertura < 0.6:
                continue
            for termo in encontrados:
                df = self.frequencia[termo]
                idf = math.log(1 + (len(self.docs) - df + 0.5) / (df + 0.5))
                tf = doc['tf'][termo]
                score += idf * tf * 2.5 / (tf + 1.5 * (0.25 + 0.75 * doc['tamanho'] / self.media))
            # Favorece o assunto no título sobre menções incidentais no corpo.
            cobertura_titulo = len(assunto & doc['termos_titulo']) / len(assunto)
            score *= cobertura * (1 + cobertura_titulo)
            if score > 0:
                resultados.append({'id': doc['id'], 'titulo': doc['titulo'],
                                   'pontuacao': round(score, 4), 'termos_encontrados': sorted(encontrados),
                                   'fonte_api': f'/api.php/v2/Knowledgebase/Article/{doc["id"]}',
                                   'conteudo': doc['conteudo']})
        ordenados = sorted(resultados, key=lambda r: (-r['pontuacao'], r['id']))
        if not ordenados:
            return []
        # Retém candidatos próximos do melhor, sem preencher vagas à força.
        corte = ordenados[0]['pontuacao'] * 0.65
        return [r for r in ordenados if r['pontuacao'] >= corte][:limite]

