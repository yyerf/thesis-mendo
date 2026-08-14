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
    # Free-text intake tags (multilingual). "Strong" tags are diagnostic
    # (a hit is near-certain); "weak" tags only confirm/boost an already
    # strong match or are used alone only when unambiguous.
    tags_strong: List[str] = field(default_factory=list)
    tags_weak: List[str] = field(default_factory=list)
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
        tags_strong=[
            "tension headache", "tension", "stress headache", "tight band",
            "band like", "band around", "muscle tension", "squeezing",
            "pressing around head", "pagka tight sa ulo", "huot ang ulo",
        ],
        tags_weak=[
            "dull ache", "dull pain", "both sides of my head", "eye strain",
            "poor posture", "stress", "sikip ang ulo", "sikip ang noo",
            "around my head", "around the head", "kabug atan sa ulo",
        ],
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
        tags_strong=[
            "sinus", "sinusitis", "sinus infection", "sinus congestion",
            "sinus pressure", "sinus problem", "sinus headache", "sinus issues",
            "behind cheeks", "behind my cheeks", "behind the cheeks",
            "behind eyes", "behind my eyes", "forehead pressure",
            "pressure in my face", "face pressure",
            "cheek pain", "cheeks hurt", "pressure between eyes",
        ],
        tags_weak=[
            "cheeks", "aping", "pressure sa noo", "pressure sa agtang",
            "sakit sa aping", "presyon sa aping", "congestion",
            "runny nose with headache", "stuffy nose with headache",
            "sipon na may sakit sa ulo",
        ],
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
        tags_strong=[
            "menstrual", "menstruation", "regla", "period headache",
            "monthly period", "before my period", "during my period",
            "menstrual migraine", "hormonal", "hormone", "estrogen",
            "menopause",
        ],
        tags_weak=[
            "monthly headache", "sakit sa ulo pag regla", "sakit sa ulo kada regla",
            "bago ang regla", "atol sa regla", "pagka regla", "siklo",
        ],
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
        tags_strong=[
            "migraine", "migraine headache", "migraine with aura", "aura",
            "one sided", "one side of my head", "left side of my head",
            "right side of my head", "behind one eye", "sensitivity to light",
            "sensitive to light", "sensitive to sound", "photophobia",
            "phonophobia", "blurry vision", "blind spot", "flashing lights",
            "kumikislap ang pananaw", "kislap", "nausea with headache",
            "vomiting with headache", "pulsating on one side",
            "throbbing on one side",
        ],
        tags_weak=[
            "throbbing", "pulsing", "nahihilo", "nausea", "liwanag", "siga",
            "kasukaon", "sensitive sa kahayag", "sensitive sa tunog",
        ],
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
        tags_strong=[
            "cluster", "cluster headache", "around one eye", "around my eye",
            "behind the eye", "around the eye", "pain around the eye",
            "red tearing eye", "watery eye", "droopy eyelid",
            "stuffy nose on one side", "cyclical", "bursts of pain",
            "libot sa mata", "usa ka mata",
        ],
        tags_weak=[
            "tearing", "eye pain with headache", "sakit libot sa mata",
        ],
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
        tags_strong=[
            "rebound", "medication overuse", "painkiller overuse",
            "overuse of pain relievers", "overusing painkillers",
            "daily headache", "every day headache", "every day",
            "too much medicine", "sobra sa tambal", "sobra nga tambal",
            "palaging umiinom ng gamot", "taking pain relievers too often",
            "umiinom ng gamot araw araw", "painkiller everyday",
        ],
        tags_weak=[
            "every morning headache", "adlaw adlaw nga sakit sa ulo",
            "araw araw na sakit ng ulo",
        ],
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
        tags_strong=[
            "hemicrania", "hemicrania continua", "indomethacin", "never stops",
            "continuous one sided", "always present", "dili mohunong",
        ],
        tags_weak=[
            "continuous headache", "constant headache", "patuloy na sakit",
            "padayon nga sakit", "constant ache",
        ],
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
        tags_strong=[
            "ice pick", "icepick", "stabbing headache", "stabbing pain",
            "sharp headache", "sharp pain", "sharp jab",
            "sharp stabbing", "brief stabbing", "needle like",
            "lightning bolt", "short sharp", "sudden sharp pain",
            "matalim na kirot", "mahait nga kirot", "tusok tusok",
            "tusok tusok sa ulo", "nagtusok", "natusok", "tinutusok",
            "parang tinutusok", "tusok sa ulo", "susok susok",
        ],
        tags_weak=[
            "stabbing", "seconds long", "a few seconds", "seconds only",
            "tusok", "dunggab", "piercing",
        ],
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
        tags_strong=[
            "thunderclap", "worst headache of my life", "worst headache ever",
            "most severe headache", "instant severe", "reaches maximum instantly",
            "sudden severe headache", "peak in seconds",
            "grabe nga sakit sa ulo kalit", "kalit lang nga grabe",
            "pinakamasakit na ulo", "biglaang pinakamasakit",
        ],
        tags_weak=[
            "sudden onset", "kurat kaayo nga sakit", "biglaang sakit ng ulo",
        ],
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
        tags_strong=[
            "post traumatic", "post trauma", "after head injury", "head injury",
            "concussion", "hit my head", "bumped my head", "bangga", "accident",
            "car accident", "nahulog", "natamaan ang ulo", "nasapol",
            "human sa bangga", "banggaan", "whiplash", "pagka bangga",
            "nagbangga",
        ],
        tags_weak=[
            "after my accident", "mga adlaw human sa bangga",
        ],
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
        tags_strong=[
            "spinal", "spinal tap", "lumbar puncture", "epidural",
            "spinal fluid", "after spinal tap", "worse when sitting",
            "worse when standing", "worse upright", "better when lying",
            "better lying down", "worse when i stand", "sakit pagtindog",
            "mograbe paglingkod", "mograbe pagtindog",
        ],
        tags_weak=[
            "positional headache", "changes with position",
        ],
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
        tags_strong=[
            "caffeine", "coffee withdrawal", "no coffee", "missed my coffee",
            "skipped coffee", "skipped my coffee", "not had coffee",
            "withdrawal from coffee", "energy drink", "walay kape",
            "wala nainom og kape", "hindi uminom ng kape", "kape",
        ],
        tags_weak=[
            "too much coffee", "sobra nga kape",
            "sakit sa ulo kung walang kape",
        ],
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
        tags_strong=[
            "high blood", "high blood pressure", "hypertension", "hypertensive",
            "blood pressure", "altapresyon", "alta presyon", "high bp",
            "hypertensive crisis", "taas presyon",
        ],
        tags_weak=[
            "sakit sa ulo tungod sa presyon", "sakit ng ulo dahil sa presyon",
        ],
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
        tags_strong=[
            "exertion", "exertional", "after exercising", "after exercise",
            "after workout", "after a workout", "after running", "after the gym",
            "weightlifting", "lifting weights", "heavy lifting",
            "after heavy lifting", "after playing sports", "after intense exercise",
            "after gym", "after training", "human sa ehersisyo",
            "pagkatapos mag exercise", "pagkatapos mag ehersisyo",
            "human sa bug at nga ehersisyo",
        ],
        tags_weak=[
            "when i cough hard", "after coughing hard", "straining",
        ],
        red_flags_en=[], red_flags_tl=[], red_flags_ceb=[],
        otc_safe_if_isolated=True,
        prefer_categories=["pain & fever", "pain & inflammation"],
        safety_note_en="",
        safety_note_tl="",
        safety_note_ceb="",
    ),

    # ══════════════════════════════════════════════════════════════════════
    #  COMPOSITE RED-FLAG TYPES — free-text intake only (no head-map icon).
    #  These encode multi-feature red-flag presentations (meningeal,
    #  stroke-like, sudden visual loss, syncope, pregnancy+headache) that a
    #  single type tag cannot express. All are danger=RED by design: the
    #  kiosk must refer, never self-treat, when one of these combinations
    #  is present.
    # ══════════════════════════════════════════════════════════════════════

    HeadacheType(
        key="meningeal",
        label_en="Meningeal (Meningitis) Warning",
        label_tl="Babala ng Meningeal (Meningitis)",
        label_ceb="Pasidaan sa Meningeal (Meningitis)",
        desc_en="Headache with a stiff neck and fever — possible meningitis.",
        desc_tl="Sakit ng ulo na may matigas na leeg at lagnat — posibleng meningitis.",
        desc_ceb="Sakit sa ulo nga gahi ang liog ug hilanat — posible nga meningitis.",
        image="Thunderclap headache.png",
        zone="red", danger=RED,
        common_causes_en=["Meningitis", "Infectious inflammation of the meninges"],
        common_causes_tl=["Meningitis", "Impeksyon at pamamaga ng meninges"],
        common_causes_ceb=["Meningitis", "Impeksyon ug paghubag sa meninges"],
        tags_strong=[
            "stiff neck", "stiff neck with fever", "neck feels stiff",
            "cannot touch chin to chest", "cannot touch my chin to my chest",
            "cannot bend my neck",
            "matigas ang leeg", "tigas ang leeg", "sakit sa leeg at lagnat",
            "gahi ang liog", "gahi liog", "liog nga gahi ug hilanat",
            "hindi ko maibaba ang baba ko",
        ],
        tags_weak=["meningitis", "neck pain with fever"],
        red_flags_en=[
            "Seek immediate medical care — possible meningitis (headache + stiff neck + fever).",
            "Do NOT self-treat; meningitis requires urgent clinical evaluation.",
        ],
        red_flags_tl=[
            "Magpatingin agad — posibleng meningitis (sakit ng ulo + matigas na leeg + lagnat).",
            "Huwag mag-self-treat; kailangan ng agarang clinical evaluation.",
        ],
        red_flags_ceb=[
            "Pakigkita dayon sa doktor — posible nga meningitis (sakit sa ulo + gahi nga liog + hilanat).",
            "Ayaw pag-self-treat; gikinahanglan ang dinaliang clinical evaluation.",
        ],
        otc_safe_if_isolated=False,
        prefer_categories=[],
        avoid_categories=["pain & fever", "pain & inflammation", "cold", "cold & flu", "cold & cough"],
        safety_note_en="Seek immediate medical care — possible meningitis. Do not self-treat.",
        safety_note_tl="Magpatingin agad — posibleng meningitis. Huwag mag-self-treat.",
        safety_note_ceb="Pakigkita dayon — posible nga meningitis. Ayaw pag-self-treat.",
    ),

    HeadacheType(
        key="stroke_like",
        label_en="Stroke-Like Warning",
        label_tl="Babala ng Stroke-Like",
        label_ceb="Pasidaan sa Stroke-Like",
        desc_en="Headache with one-sided weakness, numbness, slurred speech, or confusion.",
        desc_tl="Sakit ng ulo na may panghihina sa isang side, pamamanhid, mahirap na pagsasalita, o pagkalito.",
        desc_ceb="Sakit sa ulo nga may kahuyang sa usa ka kilid, pamamanhod, lisod nga pagsulti, o kalibog.",
        image="Hypertension headache.png",
        zone="red", danger=RED,
        common_causes_en=["Stroke or TIA", "Neurological emergency"],
        common_causes_tl=["Stroke o TIA", "Neurological emergency"],
        common_causes_ceb=["Stroke o TIA", "Neurological emergency"],
        tags_strong=[
            "one sided weakness", "one side weakness", "numb on one side",
            "hindi ko maigalaw ang braso", "hindi maigalaw ang isang braso",
            "paralyzed", "paralysis", "slurred speech", "mahirap magsalita",
            "nalilito bigla", "confused suddenly", "facial droop",
            "nakalaylay ang bibig", "drooping face", "pamamanhid sa isang side",
            "manhid ang isang kamay", "numb arm and face",
        ],
        tags_weak=["pamamanhid", "mamanhid", "speech problem", "suddenly confused"],
        red_flags_en=[
            "Seek emergency care — possible stroke. Note the time symptoms started.",
            "Do NOT give aspirin or any OTC until a doctor evaluates.",
        ],
        red_flags_tl=[
            "Pumunta sa emergency — posibleng stroke. Tandaan kung kailan nagsimula ang sintomas.",
            "Huwag magbigay ng aspirin o OTC hanggang mag-assess ang doktor.",
        ],
        red_flags_ceb=[
            "Adto dayon sa emergency — posible nga stroke. Hinumdomi kanus-a nagsugod ang sintomas.",
            "Ayaw paghatag og aspirin o OTC hangtod mag-assess ang doktor.",
        ],
        otc_safe_if_isolated=False,
        prefer_categories=[],
        avoid_categories=["pain & fever", "pain & inflammation", "cold", "cold & flu", "cold & cough"],
        safety_note_en="Seek emergency care — possible stroke. Do not self-treat.",
        safety_note_tl="Pumunta sa emergency — posibleng stroke. Huwag mag-self-treat.",
        safety_note_ceb="Adto dayon sa emergency — posible nga stroke. Ayaw pag-self-treat.",
    ),

    HeadacheType(
        key="visual_loss",
        label_en="Sudden Visual Disturbance Warning",
        label_tl="Babala ng Biglang Pagkaabala sa Paningin",
        label_ceb="Pasidaan sa Kalit nga Kasamok sa Panan-aw",
        desc_en="Headache with sudden blurred/double vision or vision loss.",
        desc_tl="Sakit ng ulo na may biglang paglabo ng paningin, dobleng paningin, o pagkawala ng paningin.",
        desc_ceb="Sakit sa ulo nga kalit malabo ang panan-aw, doble ang tan-aw, o mawala ang panan-aw.",
        image="Migraine Headache.png",
        zone="red", danger=RED,
        common_causes_en=["Acute glaucoma", "Raised intracranial pressure", "Neuro-ophthalmic emergency"],
        common_causes_tl=["Acute glaucoma", "Mataas na intracranial pressure", "Neuro-ophthalmic emergency"],
        common_causes_ceb=["Acute glaucoma", "Taas nga intracranial pressure", "Neuro-ophthalmic emergency"],
        tags_strong=[
            "double vision", "doble ang nakikita", "doble ang tan-aw",
            "sudden blurred vision", "biglang malabo ang paningin",
            "sudden vision loss", "nawala ang paningin",
            "biglang nawala ang paningin", "malabo ang mata bigla",
            "nawala ang akong panan-aw", "blurred vision with headache",
        ],
        tags_weak=["malabo ang paningin", "blurred vision", "vision problem"],
        red_flags_en=[
            "Seek immediate eye/medical evaluation — possible acute glaucoma or raised brain pressure.",
            "Do NOT self-treat; delayed care can cause permanent vision loss.",
        ],
        red_flags_tl=[
            "Magpatingin agad sa mata/doktor — posibleng acute glaucoma o mataas na pressure sa utak.",
            "Huwag mag-self-treat; maaaring permanent ang pagkawala ng paningin kung maantala.",
        ],
        red_flags_ceb=[
            "Pakigkita dayon sa mata/doktor — posible nga acute glaucoma o taas nga pressure sa utok.",
            "Ayaw pag-self-treat; permanente ang pagkawala sa panan-aw kon maantala.",
        ],
        otc_safe_if_isolated=False,
        prefer_categories=[],
        avoid_categories=["pain & fever", "pain & inflammation", "cold", "cold & flu", "cold & cough"],
        safety_note_en="Seek immediate eye/medical evaluation — possible emergency. Do not self-treat.",
        safety_note_tl="Magpatingin agad — posibleng emergency. Huwag mag-self-treat.",
        safety_note_ceb="Pakigkita dayon — posible nga emergency. Ayaw pag-self-treat.",
    ),

    HeadacheType(
        key="syncope",
        label_en="Fainting / Loss of Consciousness Warning",
        label_tl="Babala ng Pagkahilo at Pagkawala ng Malay",
        label_ceb="Pasidaan sa Pagkahinanok ug Pagkawala sa Panimuot",
        desc_en="Headache with fainting, blackout, or loss of consciousness.",
        desc_tl="Sakit ng ulo na may pagkahilo, blackout, o pagkawala ng malay.",
        desc_ceb="Sakit sa ulo nga may pagkalipong, blackout, o pagkawala sa panimuot.",
        image="Tension headache.png",
        zone="red", danger=RED,
        common_causes_en=["Intracranial hemorrhage", "Syncope of unknown cause", "Neurological emergency"],
        common_causes_tl=["Intracranial hemorrhage", "Syncope na hindi alam ang sanhi", "Neurological emergency"],
        common_causes_ceb=["Intracranial hemorrhage", "Syncope nga wala mahibal-an ang hinungdan", "Neurological emergency"],
        tags_strong=[
            "nahimatay", "nawalan ng malay", "nawalan ng ulirat",
            "nawalan ko ug panimuot", "fainted", "blacked out",
            "passed out", "natumba at nahimatay", "nahilo at nahimatay",
            "woke up confused", "nagising na nalilito",
        ],
        tags_weak=["parang mahihimatay", "feeling like i will faint", "lightheaded and dizzy"],
        red_flags_en=[
            "Seek emergency care — fainting with a headache can signal serious bleeding or brain pressure.",
            "Do NOT self-treat; loss of consciousness needs urgent evaluation.",
        ],
        red_flags_tl=[
            "Pumunta sa emergency — ang pagkahilo/himatay na may sakit ng ulo ay maaaring senyales ng malubhang pagdurugo o pressure sa utak.",
            "Huwag mag-self-treat; kailangan ng agarang pagtingin ng doktor.",
        ],
        red_flags_ceb=[
            "Adto sa emergency — ang pagkalipong nga may sakit sa ulo mahimong timailhan sa grabe nga pagdugo o pressure sa utok.",
            "Ayaw pag-self-treat; gikinahanglan ang dinaliang pagtan-aw sa doktor.",
        ],
        otc_safe_if_isolated=False,
        prefer_categories=[],
        avoid_categories=["pain & fever", "pain & inflammation", "cold", "cold & flu", "cold & cough"],
        safety_note_en="Seek emergency care — fainting with headache needs urgent evaluation. Do not self-treat.",
        safety_note_tl="Pumunta sa emergency — kailangan ng agarang pagtingin. Huwag mag-self-treat.",
        safety_note_ceb="Adto sa emergency — gikinahanglan ang dinaliang pagtan-aw. Ayaw pag-self-treat.",
    ),

    HeadacheType(
        key="pregnancy",
        label_en="Headache During Pregnancy (Pre-Eclampsia Screen)",
        label_tl="Sakit ng Ulo Habang Buntis (Pre-Eclampsia Screen)",
        label_ceb="Sakit sa Ulo Samtang Buntis (Pre-Eclampsia Screen)",
        desc_en="Headache during pregnancy — requires pre-eclampsia screening.",
        desc_tl="Sakit ng ulo habang buntis — kailangan ng pre-eclampsia screening.",
        desc_ceb="Sakit sa ulo samtang buntis — gikinahanglan ang pre-eclampsia screening.",
        image="Hormone headache.png",
        zone="red", danger=RED,
        common_causes_en=["Pre-eclampsia", "Pregnancy-related hypertension"],
        common_causes_tl=["Pre-eclampsia", "Pregnancy-related hypertension"],
        common_causes_ceb=["Pre-eclampsia", "Pregnancy-related hypertension"],
        tags_strong=[
            "buntis", "buntis ako", "buntis po ako", "pregnant",
            "pregnant with headache", "buntis at masakit ang ulo",
            "buntis ug labad ang ulo",
        ],
        tags_weak=["buntis na ako", "im pregnant"],
        red_flags_en=[
            "Seek prenatal care promptly — headache in pregnancy can signal pre-eclampsia.",
            "Do NOT self-treat; blood pressure must be checked.",
        ],
        red_flags_tl=[
            "Magpatingin agad sa prenatal care — ang sakit ng ulo habang buntis ay maaaring senyales ng pre-eclampsia.",
            "Huwag mag-self-treat; dapat i-check ang blood pressure.",
        ],
        red_flags_ceb=[
            "Pakigkita dayon sa prenatal care — ang sakit sa ulo samtang buntis mahimong timailhan sa pre-eclampsia.",
            "Ayaw pag-self-treat; kinahanglan i-check ang blood pressure.",
        ],
        otc_safe_if_isolated=False,
        prefer_categories=[],
        avoid_categories=["pain & fever", "pain & inflammation", "cold", "cold & flu", "cold & cough"],
        safety_note_en="Seek prenatal care promptly — possible pre-eclampsia. Blood pressure must be checked.",
        safety_note_tl="Magpatingin agad sa prenatal care — posibleng pre-eclampsia. I-check ang blood pressure.",
        safety_note_ceb="Pakigkita dayon sa prenatal care — posible nga pre-eclampsia. I-check ang blood pressure.",
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