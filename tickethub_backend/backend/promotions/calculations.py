"""Integer-only discount arithmetic. No database or frontend prices are trusted."""
import re

MAX_MONEY = 9_000_000_000_000  # safely representable by the JSON/JavaScript clients


def normalize_code(value):
    if not isinstance(value, str):
        raise ValueError('PROMO_INVALID')
    code = value.strip().upper()
    if not re.fullmatch(r'[A-Z0-9][A-Z0-9_-]{2,39}', code):
        raise ValueError('PROMO_INVALID')
    return code


def calculate_discount(subtotal, kind, value, *, minimum=0, maximum=None):
    """Return discount in kopecks, rounding percent discounts down once per order.

    Free orders are intentionally not supported by the existing settlement flow.
    Fixed discounts that cover the entire order are rejected, not silently changed.
    """
    if type(subtotal) is not int or not 0 < subtotal <= MAX_MONEY:
        raise ValueError('INVALID_TOTAL')
    if type(value) is not int or value < 1 or value > MAX_MONEY:
        raise ValueError('PROMO_INVALID')
    if type(minimum) is not int or minimum < 0 or minimum > MAX_MONEY:
        raise ValueError('PROMO_INVALID')
    if maximum is not None and (type(maximum) is not int or not 0 < maximum <= MAX_MONEY):
        raise ValueError('PROMO_INVALID')
    if subtotal < minimum:
        raise ValueError('PROMO_MINIMUM')
    if kind == 'PERCENT' and value <= 99:
        discount = subtotal * value // 100
    elif kind == 'FIXED':
        discount = value
    else:
        raise ValueError('PROMO_INVALID')
    if maximum is not None:
        discount = min(discount, maximum)
    if discount <= 0 or discount >= subtotal:
        raise ValueError('PROMO_AMOUNT')
    return discount


def allocate_discount(prices, discount):
    """Largest remainder allocation, stable for the caller's ordered item list.

    Sum(net item prices) == subtotal - discount. This lets existing reporting,
    refunds and manual settlement operate on net amounts without special cases.
    """
    if not prices or any(type(p) is not int or p <= 0 for p in prices):
        raise ValueError('INVALID_TOTAL')
    total = sum(prices)
    if total > MAX_MONEY or type(discount) is not int or not 0 <= discount < total:
        raise ValueError('INVALID_TOTAL')
    parts = [p * discount // total for p in prices]
    remaining = discount - sum(parts)
    ranks = sorted(range(len(prices)), key=lambda i: (-(prices[i] * discount % total), i))
    for index in ranks[:remaining]:
        parts[index] += 1
    return parts
