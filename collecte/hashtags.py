"""Adaptateur compatible avec le moteur historique."""
def collecter_hashtag(navigateur, arguments, rapport, **options):
    from scraptiktok import collect_links
    return collect_links(navigateur, arguments, rapport, **options)
