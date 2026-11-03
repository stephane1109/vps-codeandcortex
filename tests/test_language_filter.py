import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from language_filter import classify_description

FR = "Les manifestants demandent une augmentation des salaires et de meilleures conditions de travail."
EN = "Today we are visiting the city and sharing our favorite places with friends."


class LanguageTests(unittest.TestCase):
    def test_french_descriptions_with_and_without_accents(self):
        for text in (FR, "Nous sommes reunis pour defendre nos droits et demander de meilleures conditions de travail."):
            self.assertEqual(classify_description(text), "fr")

    def test_other_languages_are_not_french(self):
        for text in (EN, "Los trabajadores reclaman mejores salarios y condiciones de trabajo dignas.",
                     "Die Menschen demonstrieren heute für bessere Arbeitsbedingungen und höhere Löhne.",
                     "I lavoratori chiedono salari migliori e condizioni di lavoro dignitose."):
            self.assertEqual(classify_description(text), "other")

    def test_hashtags_mentions_and_urls_do_not_determine_language(self):
        self.assertEqual(classify_description(EN + " #bonjour #français @bonjour https://example.fr/bonjour"), "other")
        self.assertEqual(classify_description(FR + " #love #happy @english https://example.com/hello"), "fr")

    def test_short_or_hashtag_only_descriptions_are_unknown(self):
        for text in ("", "Oui !", "😀 123", "#bonjour #greve #français @paris https://example.fr"):
            self.assertEqual(classify_description(text), "unknown")

    def test_courte_legende_francaise_non_exclue_sur_faux_positif(self):
        """Une prédiction étrangère sur quelques mots reste indéterminée."""
        faux_detecteur = Mock()
        faux_detecteur.get_probabilities.return_value = [
            SimpleNamespace(lang="nl", prob=0.999999)]
        fausse_fabrique = Mock()
        fausse_fabrique.create.return_value = faux_detecteur
        with patch("language_filter.detector_factory",
                   return_value=fausse_fabrique):
            self.assertEqual(classify_description(
                "Les lycéens manifestent à Paris aujourd'hui"), "unknown")

    def test_longue_legende_francaise_ambigue_non_exclue(self):
        """Deux indices grammaticaux français empêchent une exclusion abusive."""
        faux_detecteur = Mock()
        faux_detecteur.get_probabilities.return_value = [
            SimpleNamespace(lang="en", prob=0.999999)]
        fausse_fabrique = Mock()
        fausse_fabrique.create.return_value = faux_detecteur
        with patch("language_filter.detector_factory",
                   return_value=fausse_fabrique):
            self.assertEqual(classify_description(
                "Les lycéens sont dans les rues de Paris pour défendre "
                "leurs droits et demander une autre politique scolaire."), "unknown")

    def test_langue_etrangere_longue_et_certaine_reste_exclue(self):
        """Le filtre conserve sa capacité à exclure une langue clairement étrangère."""
        faux_detecteur = Mock()
        faux_detecteur.get_probabilities.return_value = [
            SimpleNamespace(lang="en", prob=0.999999)]
        fausse_fabrique = Mock()
        fausse_fabrique.create.return_value = faux_detecteur
        with patch("language_filter.detector_factory",
                   return_value=fausse_fabrique):
            self.assertEqual(classify_description(
                "Students are marching in the city because they want "
                "better conditions at school and more public investment."), "other")

    def test_results_are_repeatable(self):
        self.assertEqual([classify_description(FR) for _ in range(3)], ["fr"] * 3)
