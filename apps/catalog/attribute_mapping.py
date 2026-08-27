"""
apps.catalog.attribute_mapping

Maps the raw `details` dict from an Amazon Reviews 2023 metadata record into
`ProductAttribute` rows.

Real-data notes (from direct inspection of `raw_meta_*` streaming records for
Amazon_Fashion, Electronics, Tools_and_Home_Improvement and Musical_Instruments):

- Keys are Title-Case, space-separated English phrases (e.g. "Color",
  "Item model number", "Age Range (Description)"). Casing is mostly
  consistent within a category but not guaranteed across the whole dataset,
  so matching is done case-insensitively.
- The vast majority of values are plain strings. One key ("Best Sellers
  Rank") carries a nested dict of {sub-category: rank}; this and any other
  unmapped key are intentionally dropped for this phase.
- Values for the attributes we do care about (Color, Size, Material, Brand,
  Department) are short strings well under 100 chars in every sample
  observed, but nothing in the dataset guarantees that, so values are still
  defensively truncated to fit `ProductAttribute.value` (max_length=100).
- No literal "Gender" key was observed; "Department" (values like "womens",
  "mens", "unisex-adult") is the closest real-world proxy and is mapped to
  the "gender" attribute category.
"""

KNOWN_ATTRIBUTE_KEYS = {
    "color": ["Color", "Colour", "Color Name"],
    "size": ["Size"],
    "material": ["Material", "Material Type"],
    "gender": ["Department", "Gender", "Target Gender"],
    "brand": ["Brand", "Brand Name"],
    "style": ["Style"],
}

# Build a case-insensitive lookup: normalized raw key -> attribute name.
_KEY_TO_ATTRIBUTE = {}
for _attr_name, _raw_keys in KNOWN_ATTRIBUTE_KEYS.items():
    for _raw_key in _raw_keys:
        _KEY_TO_ATTRIBUTE[_raw_key.strip().lower()] = _attr_name

MAX_VALUE_LENGTH = 100  # ProductAttribute.value max_length


def map_details_to_attributes(item, details):
    """Map a raw Amazon `details` dict to unsaved ProductAttribute instances for `item`.

    Returns a list of ProductAttribute(item=item, name=..., value=...) -- NOT saved;
    the caller is responsible for bulk_create. Keys not matching any entry in
    KNOWN_ATTRIBUTE_KEYS are intentionally dropped (out of scope for this phase --
    no raw-leftover storage field was added to Item).
    """
    from apps.catalog.models import ProductAttribute

    if not isinstance(details, dict) or not details:
        return []

    attrs = []
    seen_names = set()
    for raw_key, raw_value in details.items():
        if not isinstance(raw_key, str):
            continue
        attr_name = _KEY_TO_ATTRIBUTE.get(raw_key.strip().lower())
        if attr_name is None:
            continue

        # Coerce non-string values (e.g. a stray dict/number) to text rather
        # than crashing -- none of the known attribute keys were observed to
        # carry non-string values in real data, but nothing guarantees it.
        if isinstance(raw_value, str):
            value = raw_value.strip()
        elif raw_value is None:
            value = ""
        else:
            value = str(raw_value).strip()

        if not value:
            continue

        value = value[:MAX_VALUE_LENGTH]

        # Only keep the first value observed per attribute name for a given
        # item (e.g. "Brand" and "Brand Name" both mapping to "brand").
        if attr_name in seen_names:
            continue
        seen_names.add(attr_name)

        attrs.append(ProductAttribute(item=item, name=attr_name, value=value))

    return attrs
