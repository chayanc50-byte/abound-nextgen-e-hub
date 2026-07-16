"""Sales hierarchy configuration - 10 levels, commission structure, promotion rules."""

# Level order and names (1-10)
LEVELS = [
    (1, "General Franchise"),
    (2, "Sub Franchise"),
    (3, "Franchise"),
    (4, "Super Franchise"),
    (5, "Merchant"),
    (6, "Super Merchant"),
    (7, "Core Merchant Team"),
    (8, "Business Development Director"),
    (9, "Senior Director"),
    (10, "Chief Business Development Director"),
]

# Commission % by level (1-10)
COMMISSION_BY_LEVEL = {
    1: 10.0,
    2: 4.0,
    3: 3.0,
    4: 2.0,
    5: 1.5,
    6: 1.0,
    7: 1.0,
    8: 1.0,
    9: 1.0,
    10: 0.5,
}

# Promotion: need 10 direct referrals at your level to reach next level
PROMOTION_DIRECT_COUNT = 10
