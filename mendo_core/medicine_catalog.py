"""Canonical medicine catalog for the ten-slot machine.

The source JSON keeps formulation-level reference records. Production selects
one approved physical formulation per occupied hardware slot and exposes the
short brand names printed on the machine. Historical inventory rows are migrated by
``pos.db`` without deleting transaction or stock-movement history.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


MEDICINE_CATALOG_VERSION = "mendo-hardware-catalog-v4-2026-10-15"


@dataclass(frozen=True)
class CatalogItem:
    slot: int
    brand: str
    category: str
    dosage_form: str
    minimum_age: str
    source_brands: Tuple[str, ...]
    default_price: float

    @property
    def inventory_names(self) -> Tuple[str, ...]:
        """Names that may identify this product in an older database."""
        return tuple(dict.fromkeys((self.brand, *self.source_brands)))


# Slot order follows the physical ten-product list supplied for the machine.
MEDICINE_CATALOG: Tuple[CatalogItem, ...] = (
    CatalogItem(1, "Kremil-S", "Antacid", "Chewable Tablet", "12", ("Kremil-S",), 8.00),
    CatalogItem(2, "Bioflu", "Cold & Flu", "Tablet", "12", ("Bioflu",), 12.00),
    CatalogItem(3, "Biogesic", "Pain & Fever", "Tablet", "12", ("Biogesic",), 5.00),
    CatalogItem(4, "Cetirizine", "Allergy", "Tablet", "6", ("Cetirizine",), 5.00),
    CatalogItem(
        5,
        "Solmux",
        "Cough with Phlegm / Productive Cough",
        "Capsule",
        "12",
        ("Solmux",),
        12.00,
    ),
    # The stocked 50 mg tablet is for adolescents OVER 12; syrup ages do not apply.
    CatalogItem(6, "Sinecod", "Cough Suppressant", "Tablet", "13", ("Sinecod Forte",), 10.00),
    CatalogItem(7, "Symdex", "Cold & Cough", "Tablet", "6", ("Symdex-D",), 10.00),
    CatalogItem(
        8,
        "Buscopan",
        "Antispasmodic",
        "Tablet",
        "6",
        ("Buscopan",),
        # Whole pesos only. The smallest currency the kiosk physically accepts
        # is PHP 1, so a .50 price can never be paid exactly and forces
        # overpayment on a machine that gives no change.
        10.00,
    ),
    CatalogItem(
        9,
        "Loperamide",
        "Anti-diarrhea",
        "Capsule",
        "12",
        ("Loperamide (Diatabs)",),
        6.00,
    ),
    # Slot 10 is a separate retail supplement, excluded from medicinal recommendations.
)

CATALOG_BY_BRAND: Dict[str, CatalogItem] = {
    item.brand: item for item in MEDICINE_CATALOG
}
CATALOG_BRANDS: Tuple[str, ...] = tuple(item.brand for item in MEDICINE_CATALOG)

NUTRABLISS_PRODUCT = {
    "slot": 10,
    "brand": "Nutrabliss Daily Defense Probiotic",
    "aliases": ("Nutrabliss Daily Defense Probiotic",),
    "generic_name": "L. rhamnosus + L. paracasei + L. reuteri + L. acidophilus + L. gasseri + L. johnsonii; prebiotics",
    "category": "Digestive-health food supplement",
    "dosage_form": "Capsule",
    "default_price": 35.0,
    "minimum_age": 12,
    "age_source": "https://www.watsons.com.hk/en/daily-defense-probiotic-prebiotics/p/BP_812267",
    "is_active": True,
}

NUTRABLISS_CATALOG_ITEM = CatalogItem(
    10, NUTRABLISS_PRODUCT["brand"], NUTRABLISS_PRODUCT["category"], "Capsule", "12",
    (NUTRABLISS_PRODUCT["brand"],), 35.0,
)


def _normalized(value: Any) -> str:
    return str(value or "").strip().casefold()


def catalog_item_for_name(name: str) -> Optional[CatalogItem]:
    normalized = _normalized(name)
    for item in (*MEDICINE_CATALOG, NUTRABLISS_CATALOG_ITEM):
        if normalized in {_normalized(candidate) for candidate in item.inventory_names}:
            return item
    return None


def is_catalog_brand(name: str) -> bool:
    return name in CATALOG_BY_BRAND


def select_runtime_entries(
    entries: Sequence[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    """Return one normalized source record for each approved physical slot."""
    selected: List[Dict[str, Any]] = []
    for item in MEDICINE_CATALOG:
        allowed_names = {_normalized(name) for name in item.inventory_names}
        candidates = [
            entry
            for entry in entries
            if _normalized(entry.get("Brand")) in allowed_names
        ]
        if not candidates:
            raise ValueError(f"Missing medicine source record for {item.brand}")

        desired_form = _normalized(item.dosage_form)
        candidates.sort(
            key=lambda entry: (
                _normalized(entry.get("Dosage Form")) != desired_form,
                _normalized(entry.get("Brand")) != _normalized(item.brand),
            )
        )
        row = dict(candidates[0])
        row["Brand"] = item.brand
        row["Drug Category"] = item.category
        row["Dosage Form"] = item.dosage_form
        row["Minimum Age"] = item.minimum_age
        row["Hardware Slot"] = item.slot
        row["Catalog Version"] = MEDICINE_CATALOG_VERSION
        if item.brand == "Loperamide":
            row["Warnings"] = [
                "For ages 12 and above; do not use for bloody stool, fever, a swollen abdomen or diarrhea after antibiotics without professional advice.",
                "Replace lost fluids with oral rehydration solution. Stop and seek medical advice if not improving within 48 hours.",
                "Do not exceed the package dose. Excess doses can cause serious heart problems.",
            ]
        selected.append(row)
    return selected


def inventory_catalog_records(
    entries: Sequence[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    """Build hardware inventory records plus the generic probiotic listing."""
    selected = select_runtime_entries(entries)
    records = [
        {
            "slot": item.slot,
            "brand": item.brand,
            "aliases": item.inventory_names,
            "generic_name": str(row.get("Generic/Main Use") or ""),
            "category": item.category,
            "dosage_form": item.dosage_form,
            "default_price": item.default_price,
        }
        for item, row in zip(MEDICINE_CATALOG, selected)
    ]
    return records + [dict(NUTRABLISS_PRODUCT)]
