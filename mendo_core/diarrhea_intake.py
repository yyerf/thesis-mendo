"""Deterministic, multilingual diarrhea intake; answers describe symptoms, not diagnoses."""

from __future__ import annotations

SCREEN_VERSION = "diarrhea-intake-v1-2026-10-14"

ADVICE = {
    "Blood or black, tarry stool needs urgent medical assessment. Do not take loperamide from the kiosk.": ("May dugo o maitim na parang alkitran na dumi: magpatingin agad. Huwag kumuha ng loperamide rito.", "Dugo o itom nga sama sa alkitran nga hugaw: magpatan-aw dayon. Ayaw pagkuha og loperamide dinhi."),
    "Inability to keep fluids down or fainting needs urgent medical attention.": ("Kung isinusuka ang inumin o hinihimatay, humingi agad ng medikal na tulong.", "Kung isuka ang imnon o makuyapan, pangayo dayon og medikal nga tabang."),
    "Severe ongoing pain or a swollen, hard abdomen needs urgent medical assessment.": ("Kung matindi at tuloy-tuloy ang sakit o namamaga at matigas ang tiyan, magpatingin agad.", "Kung grabe ug padayon ang sakit o hubag ug gahi ang tiyan, magpatan-aw dayon."),
    "Ask a doctor or pharmacist to assess the stool before using anti-diarrhea medicine.": ("Ipasuri sa doktor o pharmacist ang dumi bago gumamit ng gamot sa pagtatae.", "Ipasusi sa doktor o pharmacist ang hugaw sa dili pa mogamit og tambal sa kalibanga."),
    "Normal or hard stools do not match diarrhea. Describe the main symptom again, or ask a pharmacist.": ("Hindi pagtatae ang normal o matigas na dumi. Ilarawan muli ang pangunahing sintomas o magtanong sa pharmacist.", "Dili kalibanga ang normal o gahi nga hugaw. Isulti pag-usab ang pangunang sintomas o pangutana sa pharmacist."),
    "Diarrhea with fever, or uncertainty about fever, needs professional assessment before loperamide.": ("Kung may lagnat o hindi sigurado kung may lagnat, magpatingin bago gumamit ng loperamide.", "Kung adunay hilanat o dili sigurado, magpatan-aw sa dili pa mogamit og loperamide."),
    "Reduced urine, dizziness or marked thirst may mean dehydration. Seek medical assessment today.": ("Ang kaunting ihi, pagkahilo o matinding uhaw ay maaaring dehydration. Magpatingin ngayong araw.", "Ang gamay nga ihi, pagkalipong o grabeng kauhaw mahimong dehydration. Magpatan-aw karong adlawa."),
    "Diarrhea during or after antibiotics needs a doctor or pharmacist's assessment. Do not self-treat it with loperamide.": ("Ang pagtatae habang o matapos ang antibiotics ay kailangang ipasuri sa doktor o pharmacist. Huwag gamutin nang mag-isa gamit ang loperamide.", "Ang kalibanga samtang o human sa antibiotics kinahanglan ipasusi sa doktor o pharmacist. Ayaw pagtambal sa kaugalingon gamit ang loperamide."),
    "Ask a doctor or pharmacist before self-treatment during pregnancy, breastfeeding, immune suppression or bowel disease.": ("Magtanong sa doktor o pharmacist bago maggamot kung buntis, nagpapasuso, mahina ang immune system o may sakit sa bituka.", "Pangutana sa doktor o pharmacist sa dili pa magtambal kung mabdos, nagpasuso, huyang ang immune system o adunay sakit sa tinai."),
    "A food-related illness is possible; the kiosk cannot establish its cause. Ask a pharmacist or doctor and prioritize oral rehydration.": ("Posibleng may kaugnayan ito sa pagkain; hindi matitiyak ng kiosk ang sanhi. Magtanong sa pharmacist o doktor at unahin ang oral rehydration.", "Posibleng may kalabotan kini sa pagkaon; dili matino sa kiosk ang hinungdan. Pangutana sa pharmacist o doktor ug unaha ang oral rehydration."),
    "Frequent diarrhea increases dehydration risk. Seek medical assessment today and prioritize oral rehydration.": ("Tumataas ang panganib ng dehydration sa madalas na pagtatae. Magpatingin ngayong araw at unahin ang oral rehydration.", "Mas taas ang risgo sa dehydration kung kanunay ang kalibanga. Magpatan-aw karong adlawa ug unaha ang oral rehydration."),
    "The stocked loperamide product is for ages 12 and above. Ask a pharmacist about oral rehydration and suitable care for a child.": ("Para sa edad 12 pataas ang loperamide rito. Magtanong sa pharmacist tungkol sa oral rehydration at angkop na pangangalaga sa bata.", "Para sa edad 12 pataas ang loperamide dinhi. Pangutana sa pharmacist bahin sa oral rehydration ug angay nga pag-atiman sa bata."),
    "Replace lost fluids with oral rehydration solution (ORS), mixed exactly as the packet directs. ORS is not stocked in this machine; ask a pharmacist.": ("Palitan ang nawalang likido gamit ang ORS na tinimpla ayon sa pakete. Walang ORS sa makina; magtanong sa pharmacist.", "Ilisi ang nawalang likido gamit ang ORS nga gisagol sumala sa pakete. Walay ORS sa makina; pangutana sa pharmacist."),
    "Nutrabliss Daily Defense is a digestive-health food supplement, not a replacement for ORS or a proven treatment for this episode of diarrhea. Ask a pharmacist about suitability.": ("Food supplement ang Nutrabliss Daily Defense para sa digestive health. Hindi ito kapalit ng ORS o napatunayang gamot sa pagtatae na ito. Magtanong sa pharmacist.", "Food supplement ang Nutrabliss Daily Defense para sa digestive health. Dili kini puli sa ORS o napamatud-ang tambal niining kalibanga. Pangutana sa pharmacist."),
    "Screening does not establish the cause of diarrhea. Prioritize oral rehydration; ask a pharmacist for ORS, which is not stocked here.": ("Hindi matitiyak ng screening ang sanhi ng pagtatae. Unahin ang oral rehydration; humingi sa pharmacist ng ORS, na wala rito.", "Dili matino sa screening ang hinungdan sa kalibanga. Unaha ang oral rehydration; pangayo sa pharmacist og ORS, nga wala dinhi."),
    "Plain loperamide treats loose stools, not bloating or cramping. Do not add other medicines just for those answers; ask a pharmacist if they persist.": ("Para sa malabnaw na dumi ang loperamide, hindi sa kabag o pamumulikat. Huwag basta magdagdag ng gamot; magtanong sa pharmacist kung tumatagal ang mga ito.", "Para sa luag nga hugaw ang loperamide, dili sa kabuhi o paghilab. Ayaw basta pagdugang og tambal; pangutana sa pharmacist kung magpadayon kini."),
    "Nutrabliss Daily Defense supports digestive health; it is not a proven treatment for this diarrhea episode or a replacement for ORS.": ("Para sa digestive health ang Nutrabliss Daily Defense; hindi ito napatunayang gamot sa pagtatae na ito o kapalit ng ORS.", "Para sa digestive health ang Nutrabliss Daily Defense; dili kini napamatud-ang tambal niining kalibanga o puli sa ORS."),
}


def annotate_advice(result: dict) -> dict:
    def copy(text):
        tl, ceb = ADVICE.get(text, (text, text))
        return {"en": text, "tl": tl, "ceb": ceb}
    if result.get("message"):
        result["message_i18n"] = copy(result["message"])
    result["safety_warnings_i18n"] = [copy(text) for text in result.get("safety_warnings", [])]
    for flag in result.get("triage_flags", []):
        flag.update({"message_" + language: text for language, text in copy(flag["message"]).items()})
    return result

# Each question carries the same stable option values in all languages.
QUESTIONS = (
    ("stool", ("What are your stools like?", "Ano ang hitsura ng iyong dumi?", "Unsa ang hitsura sa imong hugaw?"), (
        ("watery", ("Watery", "Matubig", "Tubigon")),
        ("loose", ("Loose or soft", "Malambot o malabnaw", "Humok o luag")),
        ("formed", ("Normal or hard stools", "Normal o matigas", "Normal o gahi")),
    )),
    ("blood", ("Any blood or black, tarry stool?", "May dugo o maitim na parang alkitran na dumi?", "Adunay dugo o itom nga sama sa alkitran nga hugaw?"), (
        ("yes", ("Yes", "Oo", "Oo")), ("no", ("No", "Wala", "Wala")),
        ("unsure", ("Not sure", "Hindi sigurado", "Dili sigurado")),
    )),
    ("fever", ("Do you have a fever with the diarrhea?", "May lagnat ka kasabay ng pagtatae?", "Aduna kay hilanat uban sa kalibanga?"), (
        ("yes", ("Yes", "Oo", "Oo")), ("no", ("No", "Wala", "Wala")),
        ("unsure", ("Not sure", "Hindi sigurado", "Dili sigurado")),
    )),
    ("hydration", ("Can you drink and urinate normally?", "Nakakainom at nakakaihi ka ba nang normal?", "Makainom ug makaihi ka ba sama sa naandan?"), (
        ("normal", ("Yes, I can drink and urinate", "Oo, nakakainom at nakakaihi", "Oo, makainom ug makaihi")),
        ("reduced", ("Very little urine, dizzy or very thirsty", "Kaunti ang ihi, nahihilo o uhaw na uhaw", "Gamay ang ihi, nalipong o uhaw kaayo")),
        ("cannot", ("Cannot keep drinks down / fainting", "Isinusuka ang inumin / hinihimatay", "Isuka ang imnon / makuyapan")),
    )),
    ("pain", ("How does your abdomen feel?", "Ano ang nararamdaman sa iyong tiyan?", "Unsa imong gibati sa tiyan?"), (
        ("none", ("No abdominal pain", "Walang sakit sa tiyan", "Walay sakit sa tiyan")),
        ("mild", ("Mild cramps that come and go", "Banayad na pamumulikat na pabalik-balik", "Hinay nga paghilab nga mobalik-balik")),
        ("severe", ("Severe, constant pain or a swollen, hard abdomen", "Matindi, tuloy-tuloy na sakit o namamaga at matigas na tiyan", "Grabe, padayon nga sakit o hubag ug gahi nga tiyan")),
    )),
    ("antibiotics", ("Did this start during or after taking antibiotics?", "Nagsimula ba ito habang o matapos uminom ng antibiotics?", "Nagsugod ba kini samtang o human sa antibiotics?"), (
        ("yes", ("Yes", "Oo", "Oo")), ("no", ("No", "Hindi", "Dili")),
        ("unsure", ("Not sure", "Hindi sigurado", "Dili sigurado")),
    )),
    ("risk", ("Do any of these apply: pregnancy, breastfeeding, weak immune system, or bowel disease?", "Buntis, nagpapasuso, mahina ang immune system, o may sakit sa bituka?", "Mabdos, nagpasuso, huyang ang immune system, o adunay sakit sa tinai?"), (
        ("yes", ("Yes / not sure", "Oo / hindi sigurado", "Oo / dili sigurado")),
        ("no", ("None of these", "Wala sa mga ito", "Wala niini")),
    )),
    ("trigger", ("Did it follow suspicious food or are others sick after the same meal?", "Pagkatapos ba ng kahina-hinalang pagkain o may ibang nagkasakit sa parehong pagkain?", "Human ba sa kadudahang pagkaon o adunay uban nga nasakit sa samang pagkaon?"), (
        ("yes", ("Yes", "Oo", "Oo")), ("no", ("No known food link", "Walang alam na kaugnayan sa pagkain", "Walay nahibaloang kalabotan sa pagkaon")),
        ("unsure", ("Not sure", "Hindi sigurado", "Dili sigurado")),
    )),
    ("frequency", ("How many loose stools in the last 24 hours?", "Ilang beses dumumi nang malabnaw sa nakaraang 24 oras?", "Pila ka luag nga hugaw sulod sa miaging 24 oras?"), (
        ("one_two", ("1–2 times", "1–2 beses", "1–2 ka beses")),
        ("three_five", ("3–5 times", "3–5 beses", "3–5 ka beses")),
        ("six_plus", ("6 or more times", "6 o higit pa", "6 o labaw pa")),
    )),
    ("comfort", ("Any bloating or cramping with the loose stools?", "May kabag o pamumulikat kasabay ng malabnaw na dumi?", "Adunay kabuhi o paghilab uban sa luag nga hugaw?"), (
        ("neither", ("Neither", "Wala", "Wala")),
        ("bloating", ("Bloating / gas", "Kabag / hangin", "Kabuhi / hangin")),
        ("cramps", ("Mild cramping", "Banayad na pamumulikat", "Hinay nga paghilab")),
        ("both", ("Both", "Pareho", "Pareho")),
    )),
)


def translated(copy: tuple[str, str, str]) -> dict[str, str]:
    return dict(zip(("en", "tl", "ceb"), copy))


def intake_result(symptoms: list[str], answers: dict, age: int | None = None) -> dict | None:
    """Return the next question or referral; None means screening is complete."""
    warnings = [
        "Replace lost fluids with oral rehydration solution (ORS), mixed exactly as the packet directs. ORS is not stocked in this machine; ask a pharmacist.",
        "Nutrabliss Daily Defense is a digestive-health food supplement, not a replacement for ORS or a proven treatment for this episode of diarrhea. Ask a pharmacist about suitability.",
    ]
    message = None
    urgent = False
    if answers.get("blood") == "yes":
        message, urgent = "Blood or black, tarry stool needs urgent medical assessment. Do not take loperamide from the kiosk.", True
    elif answers.get("hydration") == "cannot":
        message, urgent = "Inability to keep fluids down or fainting needs urgent medical attention.", True
    elif answers.get("pain") == "severe":
        message, urgent = "Severe ongoing pain or a swollen, hard abdomen needs urgent medical assessment.", True
    elif answers.get("blood") == "unsure":
        message = "Ask a doctor or pharmacist to assess the stool before using anti-diarrhea medicine."
    elif answers.get("stool") == "formed":
        message = "Normal or hard stools do not match diarrhea. Describe the main symptom again, or ask a pharmacist."
    elif answers.get("fever") in {"yes", "unsure"}:
        message = "Diarrhea with fever, or uncertainty about fever, needs professional assessment before loperamide."
    elif answers.get("hydration") == "reduced":
        message = "Reduced urine, dizziness or marked thirst may mean dehydration. Seek medical assessment today."
    elif answers.get("antibiotics") in {"yes", "unsure"}:
        message = "Diarrhea during or after antibiotics needs a doctor or pharmacist's assessment. Do not self-treat it with loperamide."
    elif answers.get("risk") == "yes":
        message = "Ask a doctor or pharmacist before self-treatment during pregnancy, breastfeeding, immune suppression or bowel disease."
    elif answers.get("trigger") in {"yes", "unsure"}:
        message = "A food-related illness is possible; the kiosk cannot establish its cause. Ask a pharmacist or doctor and prioritize oral rehydration."
    elif answers.get("frequency") == "six_plus":
        message = "Frequent diarrhea increases dehydration risk. Seek medical assessment today and prioritize oral rehydration."
    elif age is not None and age < 12:
        message = "The stocked loperamide product is for ages 12 and above. Ask a pharmacist about oral rehydration and suitable care for a child."
    snapshot = {"version": SCREEN_VERSION, "answers": dict(answers)}
    if message:
        return annotate_advice({
            "action": "triage" if urgent else "no_match", "message": message,
            "triage_flags": [{"flag": "diarrhea_intake", "message": message}] if urgent else [],
            "recommendations": [], "safety_warnings": warnings,
            "diarrhea_screen": snapshot,
        })
    for index, (key, question, options) in enumerate(QUESTIONS):
        if key not in answers:
            return {
                "action": "ask_clarify", "clarify_type": "DIARRHEA_SCREEN",
                "question": question[0], "question_i18n": translated(question),
                "question_key": key, "question_number": index + 1, "question_total": len(QUESTIONS),
                "options": [{"value": f"DS_{key}_{value}", "label": copy[0], "label_i18n": translated(copy)} for value, copy in options],
                "original_symptoms": list(symptoms), "diarrhea_screen": snapshot,
            }
    return None


def accept_answer(symptoms: list[str], answers: dict, value: str, age: int | None) -> dict:
    pending = intake_result(symptoms, answers, age)
    if not pending or pending.get("action") != "ask_clarify":
        raise ValueError("No diarrhea question is awaiting an answer")
    if value not in {row["value"] for row in pending["options"]}:
        raise ValueError("Answer does not match the current diarrhea question")
    key = pending["question_key"]
    updated = dict(answers)
    updated[key] = value[len(f"DS_{key}_"):]
    return updated
