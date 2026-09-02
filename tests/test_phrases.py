from kidobot.securite import decouper_en_phrases


def test_decoupe_au_fil_du_flux():
    flux = ["Le ciel ", "est bleu par", "ce que la lumiere ", "se disperse. ", "Tu savais ", "ca ?"]
    assert list(decouper_en_phrases(flux)) == [
        "Le ciel est bleu parce que la lumiere se disperse.",
        "Tu savais ca ?",
    ]


def test_ne_coupe_pas_sur_un_point_trop_precoce():
    # "M. Soleil" ne doit pas produire une phrase de 2 mots.
    phrases = list(decouper_en_phrases(["M. Soleil chauffe la Terre tous les jours."]))
    assert phrases == ["M. Soleil chauffe la Terre tous les jours."]


def test_reste_du_tampon_rendu_en_fin_de_flux():
    assert list(decouper_en_phrases(["Une reponse sans ponctuation finale"])) == [
        "Une reponse sans ponctuation finale"
    ]
