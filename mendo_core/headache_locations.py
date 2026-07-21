"""Headache Type Classification & Clinical Decision Support.

Provides structured knowledge about 14 clinical headache types, their
underlying causes, red-flag indicators, and recommendation adjustments
for the OTC recommendation pipeline.

Each entry includes:
  - Multilingual labels (EN, TL, CEB)
  - A clinical description
  - Zone (green = OTC safe, yellow = caution, red = seek care)
  - OTC recommendation adjustments (drug categories to prefer / avoid)
  - The image filename for UI rendering
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

# ── Severity / danger level ────────────────────────────────────────────────
GREEN = "safe"          # OTC-safe — self-treatable
YELLOW = "caution"      # Monitor; may need professional advice
RED = "red_flag"        # Seek medical attention


@dataclass(frozen=True)
class HeadacheType:
    """Single headache type with clinical decision-support data."""

    key: str
    label_en: str
    label_tl: str
    label_ceb: str
    desc_en: str
    desc_tl: str
    desc_ceb: str
    image: str                                # filename in static/images/headache/
    zone: str = GREEN                         # "green" | "yellow" | "red"
    danger: str = GREEN                       # "safe" | "caution" | "red_flag"
    common_causes_en: List[str] = field(default_factory=list)
    common_causes_tl: List[str] = field(default_factory=list)
    common_causes_ceb: List[str] = field(default_factory=list)
    red_flags_en: List[str] = field(default_factory=list)
    red_flags_tl: List[str] = field(default_factory=list)
    red_flags_ceb: List[str] = field(default_factory=list)
    prefer_categories: List[str] = field(default_factory=list)
    avoid_categories: List[str] = field(default_factory=list)
    otc_safe_if_isolated: bool = True
    safety_note_en: str = ""
    safety_note_tl: str = ""
    safety_note_ceb: str = ""


# ── All headache types ─────────────────────────────────────────────────────

HEADACHE_TYPES: List[HeadacheType] = [

    # ══════════════════════════════════════════════════════════════════════
    #  GREEN ZONE — OTC-safe, self-treatable
    # ══════════════════════════════════════════════════════════════════════

    HeadacheType(
        key="tension",
        label_en="Tension Headache",
        label_tl="Sakit ng Ulo dahil sa Tensyon",
        label_ceb="Sakit sa Ulo tungod sa Tension",
        desc_en="Squeezing, dull ache around the head caused by stress or muscle tension.",
        desc_tl="Mahapdi at makirot na sakit sa paligid ng ulo dahil sa stress o tensyon ng muscles.",
        desc_ceb="Nagpitik nga dull nga sakit sa palibot sa ulo tungod sa stress o tension sa kaunoran.",
        image="Tension headache.png",
        zone="green", danger=GREEN,
        common_causes_en=["Stress", "Muscle tension", "Poor posture", "Eye strain"],
        common_causes_tl=["Stress", "Pag-igting ng kalamnan", "Maling postura", "Pagod na mata"],
        common_causes_ceb=["Stress", "Tension sa kaunoran", "Sayop nga postura", "Kapoy nga mata"],
        otc_safe_if_isolated=True,
        prefer_categories=["pain & fever", "pain & inflammation"],
        safety_note_en="OTC pain relievers: Acetaminophen, Ibuprofen, Naproxen, or Aspirin.",
        safety_note_tl="OTC pain relievers: Acetaminophen, Ibuprofen, Naproxen, o Aspirin.",
        safety_note_ceb="OTC pain relievers: Acetaminophen, Ibuprofen, Naproxen, o Aspirin.",
    ),

    HeadacheType(
        key="sinus",
        label_en="Sinus / Allergy Headache",
        label_tl="Sakit ng Ulo dahil sa Sinus / Allergy",
        label_ceb="Sakit sa Ulo tungod sa Sinus / Allergy",
        desc_en="Deep, constant pressure and throbbing behind cheeks and forehead due to sinus congestion.",
        desc_tl="Matinding pressure at pumipintig na sakit sa pisngi at noo dahil sa sinus congestion.",
        desc_ceb="Kanunay nga presyur ug nagkutoy nga sakit sa aping ug agtang tungod sa sinus congestion.",
        image="Sinus headache.png",
        zone="green", danger=GREEN,
        common_causes_en=["Sinus congestion", "Allergies", "Cold", "Hay fever"],
        common_causes_tl=["Sinus congestion", "Allergy", "Sipon", "Hay fever"],
        common_causes_ceb=["Sinus congestion", "Allergy", "Sip-on", "Hay fever"],
        otc_safe_if_isolated=True,
        prefer_categories=["pain & fever", "pain & inflammation", "cold", "cold & flu"],
        safety_note_en="Decongestants + Pain Relievers: Pseudoephedrine or Phenylephrine combined with Ibuprofen or Acetaminophen.",
        safety_note_tl="Decongestants + Pain Relievers: Pseudoephedrine or Phenylephrine na may Ibuprofen o Acetaminophen.",
        safety_note_ceb="Decongestants + Pain Relievers: Pseudoephedrine or Phenylephrine nga may Ibuprofen o Acetaminophen.",
    ),

    HeadacheType(
        key="hormone",
        label_en="Hormone Headache (Menstrual Migraine)",
        label_tl="Sakit ng Ulo dahil sa Hormone (Menstrual Migraine)",
        label_ceb="Sakit sa Ulo tungod sa Hormone (Menstrual Migraine)",
        desc_en="Throbbing pain linked to estrogen drops prior to or during menstruation.",
        desc_tl="Pumipintig na sakit na may kaugnayan sa pagbaba ng estrogen bago o habang may regla.",
        desc_ceb="Nagkutoy nga sakit nga nalangkit sa pag-ubos sa estrogen sa wala pa o atol sa regla.",
        image="Hormone headache.png",
        zone="green", danger=GREEN,
        common_causes_en=["Menstruation", "Hormonal fluctuation", "Estrogen drop"],
        common_causes_tl=["Menstruation", "Pagbabago ng hormone", "Pagbaba ng estrogen"],
        common_causes_ceb=["Regla", "Pag-usab sa hormone", "Pag-ubos sa estrogen"],
        otc_safe_if_isolated=True,
        prefer_categories=["pain & inflammation", "pain & fever"],
        safety_note_en="OTC NSAIDs: Naproxen sodium or Ibuprofen taken right at symptom onset.",
        safety_note_tl="OTC NSAIDs: Naproxen sodium o Ibuprofen na inumin agad sa simula ng sintomas.",
        safety_note_ceb="OTC NSAIDs: Naproxen sodium o Ibuprofen nga imnon dayon sa pagsugod sa sintomas.",
    ),

    # ══════════════════════════════════════════════════════════════════════
    #  YELLOW ZONE — Caution, consult if frequent / severe
    # ══════════════════════════════════════════════════════════════════════

    HeadacheType(
        key="migraine",
        label_en="Migraine Headache",
        label_tl="Migraine",
        label_ceb="Migraine",
        desc_en="Moderate-to-severe throbbing pain, often with sensitivity to light/sound or nausea.",
        desc_tl="Katamtaman hanggang matinding pumipintig na sakit, madalas may sensitivity sa liwanag/tunog o pagduduwal.",
        desc_ceb="Tunga-tunga hangtod grabe nga nagkutoy nga sakit, sagad nga may sensitibo sa kahayag/tunog o kasukaon.",
        image="Migraine Headache.png",
        zone="yellow", danger=YELLOW,
        common_causes_en=["Genetics", "Hormonal changes", "Stress", "Certain foods", "Sensory triggers"],
        common_causes_tl=["Genetics", "Pagbabago ng hormone", "Stress", "Ilang pagkain", "Sensory triggers"],
        common_causes_ceb=["Genetics", "Pag-usab sa hormone", "Stress", "Pipila ka pagkaon", "Sensory triggers"],
        red_flags_en=[
            "If frequent or severe: Consult a Doctor for prescription Triptans.",
            "OTC may help mild cases only.",
        ],
        red_flags_tl=[
            "Kung madalas o malala: Kumonsulta sa Doktor para sa prescription Triptans.",
            "OTC ay para lamang sa banayad na kaso.",
        ],
        red_flags_ceb=[
            "Kon kanunay o grabe: Pakigkita sa Doktor para sa prescription Triptans.",
            "OTC alang lamang sa malumo nga kaso.",
        ],
        otc_safe_if_isolated=True,
        prefer_categories=["pain & inflammation", "pain & fever"],
        avoid_categories=["cold", "cold & flu", "cold & cough"],
        safety_note_en="OTC Combination: Acetaminophen + Aspirin + Caffeine (e.g., Excedrin) for mild cases.",
        safety_note_tl="OTC Combination: Acetaminophen + Aspirin + Caffeine para sa banayad na kaso.",
        safety_note_ceb="OTC Combination: Acetaminophen + Aspirin + Caffeine para sa malumo nga kaso.",
    ),

    HeadacheType(
        key="cluster",
        label_en="Cluster Headache",
        label_tl="Cluster Headache",
        label_ceb="Cluster Headache",
        desc_en="Piercing, intense, burning pain strictly around one eye. Comes in cyclical bursts.",
        desc_tl="Matinding paso at kirot sa palibot ng isang mata. Dumarating sa cyclical bursts.",
        desc_ceb="Grabe nga paso ug kirot sa palibot sa usa ka mata. Moabot sa cyclical bursts.",
        image="Cluster headache.png",
        zone="yellow", danger=YELLOW,
        common_causes_en=["Unknown (triggers: alcohol, smoking, strong smells)"],
        common_causes_tl=["Hindi alam (triggers: alcohol, paninigarilyo, matatapang na amoy)"],
        common_causes_ceb=["Wala mahibal-i (triggers: alcohol, pagpanigarilyo, kusog nga baho)"],
        red_flags_en=[
            "Do Not Rely on OTC — fast-onset pain makes OTCs ineffective.",
            "Consult a Doctor: Requires prescription oxygen therapy or Triptans.",
        ],
        red_flags_tl=[
            "Huwg umasa sa OTC — hindi epektibo ang OTC sa ganitong sakit.",
            "Kumonsulta sa Doktor: Nangangailangan ng prescription oxygen therapy o Triptans.",
        ],
        red_flags_ceb=[
            "Ayaw pagsalig sa OTC — dili epektibo ang OTC alang niini nga sakit.",
            "Pakigkita sa Doktor: Nagkinahanglan og prescription oxygen therapy o Triptans.",
        ],
        otc_safe_if_isolated=False,
        prefer_categories=[],
        avoid_categories=["cold", "cold & flu", "cold & cough", "pain & fever", "pain & inflammation"],
        safety_note_en="OTC ineffective. Requires prescription treatment.",
        safety_note_tl="Hindi epektibo ang OTC. Kailangan ng prescription treatment.",
        safety_note_ceb="Dili epektibo ang OTC. Nagkinahanglan og prescription treatment.",
    ),

    HeadacheType(
        key="rebound",
        label_en="Rebound Headache (Medication Overuse)",
        label_tl="Rebound Headache (Pag-overuse ng Gamot)",
        label_ceb="Rebound Headache (Pag-overuse sa Tambal)",
        desc_en="Daily, persistent dull headache caused by overuse of OTC pain relievers.",
        desc_tl="Araw-araw na pananakit ng ulo dahil sa labis na paggamit ng OTC pain relievers.",
        desc_ceb="Adlaw-adlaw nga sakit sa ulo tungod sa sobra nga paggamit sa OTC pain relievers.",
        image="Rebound headache.png",
        zone="yellow", danger=YELLOW,
        common_causes_en=["Overuse of OTC pain relievers (more than 10-15 days per month)"],
        common_causes_tl=["Labis na paggamit ng OTC pain relievers (higit 10-15 araw bawat buwan)"],
        common_causes_ceb=["Sobra nga paggamit sa OTC pain relievers (kapin 10-15 ka adlaw kada bulan)"],
        red_flags_en=[
            "Stop OTC Usage — continued OTC meds will worsen it.",
            "Consult a Doctor: Requires guided tapering off pain medication.",
        ],
        red_flags_tl=[
            "Itigil ang OTC — lalala ito kung magpatuloy sa OTC.",
            "Kumonsulta sa Doktor: Kailangan ng guided tapering off pain medication.",
        ],
        red_flags_ceb=[
            "Hunonga ang OTC — mograbe kini kon magpadayon sa OTC.",
            "Pakigkita sa Doktor: Nagkinahanglan og guided tapering off pain medication.",
        ],
        otc_safe_if_isolated=False,
        prefer_categories=[],
        avoid_categories=["pain & fever", "pain & inflammation", "cold", "cold & flu", "cold & cough"],
        safety_note_en="Stop OTC usage. Consult a doctor for guided tapering.",
        safety_note_tl="Itigil ang OTC. Kumonsulta sa doktor para sa guided tapering.",
        safety_note_ceb="Hunonga ang OTC. Pakigkita sa doktor para sa guided tapering.",
    ),

    HeadacheType(
        key="hemicrania",
        label_en="Hemicrania Continua",
        label_tl="Hemicrania Continua",
        label_ceb="Hemicrania Continua",
        desc_en="Rare, continuous, moderately severe ache on one side of face/head that never stops.",
        desc_tl="Bihira, tuloy-tuloy na katamtamang sakit sa isang bahagi ng mukha/ulo na hindi tumitigil.",
        desc_ceb="Talagsa, padayon nga tunga-tunga nga sakit sa usa ka bahin sa nawong/ulo nga dili mohunong.",
        image="Hemicrania.png",
        zone="yellow", danger=YELLOW,
        common_causes_en=["Unknown (responds specifically to Indomethacin)"],
        common_causes_tl=["Hindi alam (tumutugon lamang sa Indomethacin)"],
        common_causes_ceb=["Wala mahibal-i (motubag lamang sa Indomethacin)"],
        red_flags_en=[
            "OTC Ineffective — strictly responds to prescription Indomethacin.",
            "Consult a Doctor for proper diagnosis and treatment.",
        ],
        red_flags_tl=[
            "Hindi epektibo ang OTC — tumutugon lamang sa prescription Indomethacin.",
            "Kumonsulta sa Doktor para sa tamang diagnosis at treatment.",
        ],
        red_flags_ceb=[
            "Dili epektibo ang OTC — motubag lamang sa prescription Indomethacin.",
            "Pakigkita sa Doktor para sa husto nga diagnosis ug treatment.",
        ],
        otc_safe_if_isolated=False,
        prefer_categories=[],
        avoid_categories=["pain & fever", "pain & inflammation", "cold", "cold & flu", "cold & cough"],
        safety_note_en="Requires prescription Indomethacin. OTC will not help.",
        safety_note_tl="Kailangan ng prescription Indomethacin. Hindi makakatulong ang OTC.",
        safety_note_ceb="Nagkinahanglan og prescription Indomethacin. Dili makatabang ang OTC.",
    ),

    HeadacheType(
        key="ice_pick",
        label_en="Ice Pick Headache",
        label_tl="Ice Pick Headache",
        label_ceb="Ice Pick Headache",
        desc_en="Sudden, sharp, stabbing pain lasting only a few seconds in random spots.",
        desc_tl="Biglaan, matalim na kirot na tumatagal lang ng ilang segundo sa random spots.",
        desc_ceb="Kalit, mahait nga kirot nga molungtad lang og pila ka segundo sa random nga mga dapit.",
        image="Ice pick headache.png",
        zone="yellow", danger=YELLOW,
        common_causes_en=["Unknown (benign, short duration)"],
        common_causes_tl=["Hindi alam (benign, maikling tagal)"],
        common_causes_ceb=["Wala mahibal-i (benign, mubo nga gidugayon)"],
        red_flags_en=[
            "Attacks too short (<5 seconds) for OTC meds to act.",
            "Consult a Doctor if frequent episodes occur.",
        ],
        red_flags_tl=[
            "Masyadong maikli ang atake (<5 segundo) para kumilos ang OTC.",
            "Kumonsulta sa Doktor kung madalas mangyari.",
        ],
        red_flags_ceb=[
            "Mubo kaayo ang atake (<5 segundo) para molihok ang OTC.",
            "Pakigkita sa Doktor kon kanunay mahitabo.",
        ],
        otc_safe_if_isolated=True,
        prefer_categories=[],
        safety_note_en="Attacks too short (<5 sec) for OTC. Observation & rest. Consult if frequent.",
        safety_note_tl="Masyadong maikli ang atake (<5 seg) para sa OTC. Pagmasid at pahinga. Kumonsulta kung madalas.",
        safety_note_ceb="Mubo kaayo ang atake (<5 seg) para sa OTC. Pag-obserba ug pahulay. Pakigkita kon kanunay.",
    ),

    # ══════════════════════════════════════════════════════════════════════
    #  RED ZONE — Seek medical attention immediately
    # ══════════════════════════════════════════════════════════════════════

    HeadacheType(
        key="thunderclap",
        label_en="Thunderclap Headache",
        label_tl="Thunderclap Headache",
        label_ceb="Thunderclap Headache",
        desc_en="Extremely severe pain that reaches maximum intensity in under 60 seconds ('worst headache ever').",
        desc_tl="Matinding sakit na umaabot sa pinakamataas na intensity sa ilalim ng 60 segundo.",
        desc_ceb="Grabe kaayo nga sakit nga moabot sa pinakataas nga intensity ubos sa 60 ka segundo.",
        image="Thunderclap headache.png",
        zone="red", danger=RED,
        common_causes_en=["Brain hemorrhage", "Aneurysm", "Stroke"],
        common_causes_tl=["Brain hemorrhage", "Aneurysm", "Stroke"],
        common_causes_ceb=["Brain hemorrhage", "Aneurysm", "Stroke"],
        red_flags_en=[
            "EMERGENCY — Call 911 / Go to ER immediately.",
            "Potential brain hemorrhage, aneurysm, or stroke.",
        ],
        red_flags_tl=[
            "EMERGENCY — Tumawag ng 911 / Pumunta sa ER agad.",
            "Posibleng brain hemorrhage, aneurysm, o stroke.",
        ],
        red_flags_ceb=[
            "EMERGENCY — Tawag 911 / Adto sa ER dayon.",
            "Posibleng brain hemorrhage, aneurysm, o stroke.",
        ],
        otc_safe_if_isolated=False,
        prefer_categories=[],
        avoid_categories=["pain & fever", "pain & inflammation", "cold", "cold & flu", "cold & cough"],
        safety_note_en="EMERGENCY — Call 911 or go to the ER immediately.",
        safety_note_tl="EMERGENCY — Tumawag ng 911 o pumunta sa ER agad.",
        safety_note_ceb="EMERGENCY — Tawag 911 o adto sa ER dayon.",
    ),

    HeadacheType(
        key="post_traumatic",
        label_en="Post-Traumatic Headache",
        label_tl="Sakit ng Ulo pagkatapos ng Trauma",
        label_ceb="Sakit sa Ulo human sa Trauma",
        desc_en="Headache starting within days after a head injury or concussion.",
        desc_tl="Sakit ng ulo na nagsisimula ilang araw pagkatapos ng head injury o concussion.",
        desc_ceb="Sakit sa ulo nga magsugod sulod sa mga adlaw human sa head injury o concussion.",
        image="Post traumatic.png",
        zone="red", danger=RED,
        common_causes_en=["Head injury", "Concussion", "Whiplash"],
        common_causes_tl=["Head injury", "Concussion", "Whiplash"],
        common_causes_ceb=["Head injury", "Concussion", "Whiplash"],
        red_flags_en=[
            "Seek medical evaluation — rule out brain trauma or internal bleeding.",
            "Avoid blood-thinning OTCs (Aspirin, Ibuprofen) until cleared by a doctor.",
        ],
        red_flags_tl=[
            "Magpatingin sa doktor — alamin kung may brain trauma o internal bleeding.",
            "Iwasan ang blood-thinning OTCs hanggang cleared ng doktor.",
        ],
        red_flags_ceb=[
            "Pakigkita sa doktor — hibal-i kung naay brain trauma o internal bleeding.",
            "Likayi ang blood-thinning OTCs hangtod cleared sa doktor.",
        ],
        otc_safe_if_isolated=False,
        prefer_categories=["pain & fever"],  # paracetamol only (no blood thinning)
        avoid_categories=["pain & inflammation", "cold", "cold & flu", "cold & cough"],
        safety_note_en="Seek medical evaluation. Avoid blood-thinning OTCs (Aspirin, Ibuprofen) until cleared.",
        safety_note_tl="Magpatingin sa doktor. Iwasan ang blood-thinning OTCs hanggang cleared.",
        safety_note_ceb="Pakigkita sa doktor. Likayi ang blood-thinning OTCs hangtod cleared.",
    ),

    HeadacheType(
        key="spinal",
        label_en="Spinal Headache",
        label_tl="Spinal Headache",
        label_ceb="Spinal Headache",
        desc_en="Severe pain that worsens when sitting/standing and improves when lying flat.",
        desc_tl="Matinding sakit na lumalala kapag nakaupo/nakatayo at gumagaan kapag nakahiga.",
        desc_ceb="Grabe nga sakit nga mograbe kon naglingkod/nagtindog ug mouswag kon naghigda.",
        image="Spinal headache.png",
        zone="red", danger=RED,
        common_causes_en=["Spinal fluid leak after lumbar puncture or epidural"],
        common_causes_tl=["Spinal fluid leak pagkatapos ng lumbar puncture o epidural"],
        common_causes_ceb=["Spinal fluid leak human sa lumbar puncture o epidural"],
        red_flags_en=[
            "Seek medical care — results from spinal fluid leak.",
            "Requires clinical fluid replacement or a blood patch procedure.",
        ],
        red_flags_tl=[
            "Magpatingin sa doktor — dulot ng spinal fluid leak.",
            "Kailangan ng clinical fluid replacement o blood patch procedure.",
        ],
        red_flags_ceb=[
            "Pakigkita sa doktor — tungod sa spinal fluid leak.",
            "Nagkinahanglan og clinical fluid replacement o blood patch procedure.",
        ],
        otc_safe_if_isolated=False,
        prefer_categories=[],
        avoid_categories=["pain & fever", "pain & inflammation", "cold", "cold & flu", "cold & cough"],
        safety_note_en="Seek medical care. Requires clinical procedure, not OTC medication.",
        safety_note_tl="Magpatingin sa doktor. Kailangan ng clinical procedure, hindi OTC.",
        safety_note_ceb="Pakigkita sa doktor. Nagkinahanglan og clinical procedure, dili OTC.",
    ),

    # ═══ Grouped: Caffeine · Hypertension · Exertion ═══

    HeadacheType(
        key="caffeine",
        label_en="Caffeine Headache",
        label_tl="Sakit ng Ulo dahil sa Caffeine",
        label_ceb="Sakit sa Ulo tungod sa Caffeine",
        desc_en="Pulsing ache triggered by caffeine withdrawal or sudden overuse.",
        desc_tl="Pumipintig na sakit dahil sa pag-withdraw ng caffeine o biglaang pag-overuse.",
        desc_ceb="Nagkutoy nga sakit tungod sa pag-withdraw sa caffeine o kalit nga pag-overuse.",
        image="Caffeine headache.png",
        zone="green", danger=GREEN,
        common_causes_en=["Caffeine withdrawal", "Caffeine overuse", "Skipping morning coffee"],
        common_causes_tl=["Caffeine withdrawal", "Labis na caffeine", "Hindi pag-inom ng kape"],
        common_causes_ceb=["Caffeine withdrawal", "Sobra nga caffeine", "Walay kape sa buntag"],
        otc_safe_if_isolated=True,
        prefer_categories=["pain & fever", "pain & inflammation"],
        safety_note_en="Hydration + Mild OTC Pain Relievers: Ibuprofen or Acetaminophen. Advise gradual caffeine reduction.",
        safety_note_tl="Hydration + Mild OTC Pain Relievers: Ibuprofen o Acetaminophen. Payo: gradual na pagbawas ng caffeine.",
        safety_note_ceb="Hydration + Mild OTC Pain Relievers: Ibuprofen o Acetaminophen. Tambag: hinay-hinay nga pagkunhod sa caffeine.",
    ),

    HeadacheType(
        key="hypertension",
        label_en="Hypertension Headache",
        label_tl="Sakit ng Ulo dahil sa Altapresyon",
        label_ceb="Sakit sa Ulo tungod sa Alta Presyon",
        desc_en="Pulsating ache caused by dangerously high blood pressure.",
        desc_tl="Pumipintig na sakit dulot ng delikadong mataas na blood pressure.",
        desc_ceb="Nagkutoy nga sakit tungod sa delikado nga taas nga blood pressure.",
        image="Hypertension headache.png",
        zone="red", danger=RED,
        common_causes_en=["Uncontrolled hypertension", "Hypertensive crisis"],
        common_causes_tl=["Hindi kontroladong altapresyon", "Hypertensive crisis"],
        common_causes_ceb=["Dili kontrolado nga alta presyon", "Hypertensive crisis"],
        red_flags_en=[], red_flags_tl=[], red_flags_ceb=[],
        otc_safe_if_isolated=False,
        prefer_categories=[],
        avoid_categories=["pain & fever", "pain & inflammation", "cold", "cold & flu", "cold & cough"],
        safety_note_en="",
        safety_note_tl="",
        safety_note_ceb="",
    ),

    HeadacheType(
        key="exertion",
        label_en="Exertion Headache",
        label_tl="Sakit ng Ulo dahil sa Pagod",
        label_ceb="Sakit sa Ulo tungod sa Kapoy",
        desc_en="Throbbing pain triggered immediately after physical overexertion or straining.",
        desc_tl="Pumipintig na sakit na lumalabas agad pagkatapos ng matinding physical activity.",
        desc_ceb="Nagkutoy nga sakit nga mogawas dayon human sa grabeng physical activity.",
        image="Exertion headache.png",
        zone="red", danger=RED,
        common_causes_en=["Heavy exercise", "Weightlifting", "Coughing fits", "Straining"],
        common_causes_tl=["Matinding ehersisyo", "Weightlifting", "Matinding ubo", "Pagpupuwersa"],
        common_causes_ceb=["Bug-at nga ehersisyo", "Weightlifting", "Kusog nga ubo", "Pagpugos"],
        red_flags_en=[], red_flags_tl=[], red_flags_ceb=[],
        otc_safe_if_isolated=True,
        prefer_categories=["pain & fever", "pain & inflammation"],
        safety_note_en="",
        safety_note_tl="",
        safety_note_ceb="",
    ),
]

# ── Lookup helpers ──────────────────────────────────────────────────────────

_LOC_BY_KEY: Dict[str, HeadacheType] = {
    ht.key: ht for ht in HEADACHE_TYPES
}


def get_location(key: str) -> Optional[HeadacheType]:
    return _LOC_BY_KEY.get(key)


def all_keys() -> List[str]:
    return [ht.key for ht in HEADACHE_TYPES]


def classify_danger(key: str, user_age: int = 0, **kwargs) -> str:
    """Return the danger level for a headache type."""
    ht = get_location(key)
    return ht.danger if ht else GREEN


def build_red_flag_response(key: str) -> Dict:
    """Build a triage-style response for red-zone headache types."""
    ht = get_location(key)
    if not ht or ht.danger != RED:
        return {}
    return {
        "flag": "headache_red_flag",
        "message": ht.safety_note_en,
        "matched": key,
    }


# ── Backwards compat: expose as HEADACHE_LOCATIONS ──
HEADACHE_LOCATIONS = HEADACHE_TYPES