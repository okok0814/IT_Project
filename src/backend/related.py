"""Explicit MVP outfit rules over Dataset 2 articleType, not learned compatibility."""

TOPS = frozenset({
    "Shirts", "Tshirts", "Tops", "Sweatshirts", "Sweaters", "Jackets",
    "Blazers", "Waistcoat", "Tunics", "Rain Jacket", "Shrug", "Nehru Jackets",
})
BOTTOMS = frozenset({
    "Jeans", "Trousers", "Shorts", "Skirts", "Capris", "Leggings",
    "Jeggings", "Track Pants", "Tights", "Rain Trousers",
})
FOOTWEAR = frozenset({
    "Casual Shoes", "Formal Shoes", "Sports Shoes", "Flats", "Heels",
    "Sandals", "Sports Sandals", "Flip Flops",
})
ONE_PIECE = frozenset({"Dresses", "Jumpsuit", "Sarees", "Kurta Sets", "Suits", "Clothing Set"})
BAGS = frozenset({"Handbags", "Clutches"})
ETHNIC_TOPS = frozenset({"Kurtas", "Kurtis"})
ETHNIC_BOTTOMS = frozenset({"Churidar", "Salwar", "Patiala"})

# Deliberately no same-category or unrestricted fallback for unsupported items.
COMPLEMENTARY_CATEGORIES = {}
for sources, targets in [
    (TOPS, BOTTOMS | FOOTWEAR),
    (BOTTOMS, TOPS | FOOTWEAR),
    (FOOTWEAR, TOPS | BOTTOMS | ONE_PIECE | ETHNIC_TOPS),
    (ONE_PIECE, FOOTWEAR | BAGS),
    (BAGS, ONE_PIECE | TOPS | FOOTWEAR),
    (ETHNIC_TOPS, ETHNIC_BOTTOMS | {"Leggings", "Jeans", "Trousers"} | FOOTWEAR),
    (ETHNIC_BOTTOMS, ETHNIC_TOPS | FOOTWEAR),
]:
    for category in sources:
        COMPLEMENTARY_CATEGORIES[category.casefold()] = frozenset(c.casefold() for c in targets)

# Dataset labels: Unisex is treated as adult; children stay in their age group.
COMPATIBLE_GENDERS = {
    "men": frozenset({"men", "unisex"}),
    "women": frozenset({"women", "unisex"}),
    "unisex": frozenset({"men", "women", "unisex"}),
    "boys": frozenset({"boys"}),
    "girls": frozenset({"girls"}),
}
