"""Recognize reported complaints outside the machine's catalog without diagnosing them."""

import re

# Labels remain reported complaints; these are not additional clinical diagnoses.
COMPLAINTS = (
    ("dental", ("Tooth or gum discomfort", "Sakit sa ngipin o gilagid", "Sakit sa ngipon o lagos"), ("toothache", "tootache", "tooth ache", "tooth pain", "teeth", "gum pain", "ngipin", "ngipon", "gilagid", "lagos")),
    ("wound", ("Cuts, scrapes or wounds", "Hiwa, gasgas o sugat", "Hiwa, garas o samad"), ("cut", "cuts", "scrape", "scrapes", "wound", "sugat", "samad", "hiwa", "gasgas", "garas")),
    ("burn", ("Burn or sunburn", "Paso o sunburn", "Paso o sunburn"), ("burn", "burns", "sunburn", "napaso", "nasunog")),
    ("fungal", ("Possible skin or fungal complaint", "Problema sa balat o posibleng fungal infection", "Problema sa panit o posibleng fungal infection"), ("ringworm", "athlete's foot", "fungal", "buni", "an-an", "alipunga", "had-had", "jock itch")),
    ("acne", ("Acne or pimples", "Taghiyawat", "Bugason"), ("acne", "pimple", "pimples", "taghiyawat", "tigyawat", "bugas", "bugason")),
    ("skin", ("Skin-care complaint", "Problema sa balat", "Problema sa panit"), ("eczema", "dermatitis", "dry skin", "skin treatment", "balat", "panit")),
    ("insect", ("Insect bite or sting", "Kagat o tusok ng insekto", "Paak o tusok sa insekto"), ("insect bite", "insect sting", "mosquito bite", "kagat", "paak")),
    ("constipation", ("Constipation", "Pagtitibi", "Lisod paglibang"), ("constipation", "constipated", "pagtitibi", "tibi", "lisod paglibang", "dili kalibang")),
    ("mouth", ("Mouth ulcer", "Singaw", "Luas sa baba"), ("mouth ulcer", "canker sore", "singaw", "luas")),
    ("hemorrhoids", ("Hemorrhoid complaint", "Almoranas", "Almoranas"), ("hemorrhoid", "hemorrhoids", "piles", "almoranas")),
    ("scalp", ("Dandruff or head lice", "Balakubak o kuto", "Kaspa o kuto"), ("dandruff", "head lice", "balakubak", "kaspa", "kuto")),
    ("eye", ("Eye discomfort", "Problema sa mata", "Problema sa mata"), ("eye pain", "eye problem", "eyesight", "red eye", "eye irritation", "sore eyes", "mata")),
    ("ear", ("Ear discomfort", "Problema sa tenga", "Problema sa dalunggan"), ("ear pain", "earache", "tenga", "dalunggan")),
    ("urinary", ("Urinary discomfort", "Problema sa pag-ihi", "Problema sa pag-ihi"), ("painful urination", "burning urination", "uti", "pag-ihi", "urine")),
)


def reported_complaints(text: str) -> list[dict]:
    results = []
    for clause in re.split(r"[.!?;,]|\b(?:but|pero|apan)\b", (text or "").lower()):
        if re.search(r"\b(?:no|not|without|wala|walang|walay|hindi|dili)\b", clause):
            continue
        for key, labels, terms in COMPLAINTS:
            if any(re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", clause) for term in terms):
                if not any(row["key"] == key for row in results):
                    results.append({"key": key, "label_i18n": dict(zip(("en", "tl", "ceb"), labels)), "machine_available": False})
    return results


def complaint_red_flags(text: str) -> list[dict]:
    """Keep serious wound/eye complaints out of the ordinary pharmacy fallback."""
    low = (text or "").lower()
    keys = {row["key"] for row in reported_complaints(text)}
    urgent = (
        (bool(keys & {"wound", "burn", "insect"}) and any(term in low for term in ("deep cut", "deep wound", "heavy bleeding", "cannot stop bleeding", "won't stop bleeding", "malalim", "lawom", "hindi tumitigil", "dili mohunong", "dog bite", "cat bite", "human bite", "kagat ng aso", "paak sa iro", "kagat ng pusa")))
        or ("eye" in keys and any(term in low for term in ("lost vision", "loss of vision", "cannot see", "can't see", "sudden vision", "chemical", "hindi makakita", "dili makakita")))
    )
    if not urgent:
        return []
    return [{
        "flag": "unstocked_urgent",
        "message": "This reported wound, bite or eye problem needs urgent medical assessment. Do not rely on an OTC purchase.",
        "message_tl": "Kailangang ipasuri agad ang sugat, kagat o problema sa mata na ito. Huwag umasa sa pagbili lamang ng OTC na gamot.",
        "message_ceb": "Kinahanglan ipasusi dayon kining samad, paak o problema sa mata. Ayaw pagsalig sa pagpalit lang og OTC nga tambal.",
    }]
