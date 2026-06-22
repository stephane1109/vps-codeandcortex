import hashlib
import re

LONGUEUR_MINIMALE_PAR_DEFAUT = 300


def compter_mots(texte):
    return len(re.findall(r"\b\w+\b", texte))


def detecter_doublons_articles(articles, longueur_minimale=LONGUEUR_MINIMALE_PAR_DEFAUT):
    articles_uniques = {}
    articles_doublons = []
    articles_courts = []
    ordre_hashes = []

    for article in articles:
        corps_article = article["corps"]
        hash_article = hashlib.sha256(corps_article.encode("utf-8")).hexdigest()

        if hash_article in articles_uniques:
            article_existant = articles_uniques[hash_article]
            if len(corps_article) > len(article_existant["corps"]):
                articles_doublons.append(article_existant)
                articles_uniques[hash_article] = article
            else:
                articles_doublons.append(article)
        else:
            articles_uniques[hash_article] = article
            ordre_hashes.append(hash_article)

        if compter_mots(corps_article) < longueur_minimale:
            articles_courts.append(article)

    return articles_uniques, articles_doublons, articles_courts, ordre_hashes


def reconstruire_texte(articles):
    texte_final = ""
    for article in articles:
        texte_final += f"{article['entete']}\n{article['corps']}\n\n"
    return texte_final


def extraire_apercu(article, longueur=200):
    texte_article = f"{article['entete']}\n{article['corps']}"
    lignes = texte_article.split("\n")
    if len(lignes) > 1:
        extrait = lignes[1]
    else:
        extrait = texte_article
    return f"{extrait[:longueur]}..." if len(extrait) > longueur else extrait
