"""Price utility functions for IDX stock market."""


def round_to_tick(price):
    """Round price to nearest IDX tick size.
    
    IDX Tick Size Rules:
    - Price < 200: tick = 1
    - 200 <= Price < 500: tick = 2
    - 500 <= Price < 2000: tick = 5
    - 2000 <= Price < 5000: tick = 10
    - Price >= 5000: tick = 25
    """
    if price is None:
        return None
    
    try:
        price = float(price)
    except (ValueError, TypeError):
        return price
    
    if price < 200:
        tick = 1
    elif price < 500:
        tick = 2
    elif price < 2000:
        tick = 5
    elif price < 5000:
        tick = 10
    else:
        tick = 25
    
    return round(price / tick) * tick
