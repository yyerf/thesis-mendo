"""Canonical ten-slot medicine catalog used by production and evaluation.

The source JSON keeps formulation-level reference records. Production selects
exactly one physical formulation per hardware slot and exposes the short brand
names printed on the machine. Historical inventory rows are migrated by
``pos.db`` without deleting transaction or stock-movement history.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


MEDICINE_CATALOG_VERSION = "mendo-hardware-catalog-v1-2026-07"


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
    CatalogItem(1, "Advil", "Pain & Inflammation", "Tablet", "12", ("Advil",), 15.00),
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
    CatalogItem(6, "Tuseran", "Dry Cough", "Tablet", "12", ("Tuseran Forte",), 10.00),
    CatalogItem(7, "Symdex", "Cold & Cough", "Tablet", "6", ("Symdex-D",), 10.00),
    CatalogItem(
        8,
        "Neozep",
        "Cold",
        "Tablet",
        "6",
        ("Neozep / Neozep Z+",),
        # Whole pesos only. The smallest currency the kiosk physically accepts
        # is PHP 1, so a .50 price can never be paid exactly and forces
        # overpayment on a machine that gives no change.
        10.00,
    ),
    CatalogItem(
        9,
        "Loperamide",
        "Anti-diarrhea",
        "Tablet",
        "6",
        ("Loperamide (Diatabs)",),
        6.00,
    ),
    CatalogItem(
        10,
        "Erceflora",
        "Probiotic (Adjunct for Diarrhea)",
        "Oral Suspension",
        "All ages",
        ("Erceflora",),
        28.00,
    ),
)

CATALOG_BY_BRAND: Dict[str, CatalogItem] = {
    item.brand: item for item in MEDICINE_CATALOG
}
CATALOG_BRANDS: Tuple[str, ...] = tuple(item.brand for item in MEDICINE_CATALOG)


def _normalized(value: Any) -> str:
    return str(value or "").strip().casefold()


def catalog_item_for_name(name: str) -> Optional[CatalogItem]:
    normalized = _normalized(name)
    for item in MEDICINE_CATALOG:
        if normalized in {_normalized(candidate) for candidate in item.inventory_names}:
            return item
    return None


def is_catalog_brand(name: str) -> bool:
    return name in CATALOG_BY_BRAND


def select_runtime_entries(
    entries: Sequence[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    """Return exactly one normalized source record for each physical slot."""
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
        selected.append(row)
    return selected


def inventory_catalog_records(
    entries: Sequence[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    """Build database-ready records from the same ten runtime entries."""
    selected = select_runtime_entries(entries)
    return [
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
