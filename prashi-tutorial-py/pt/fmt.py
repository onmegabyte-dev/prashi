"""Number formatting."""


def locale(n):
    """Number with Indian digit grouping (1,45,000) - what JavaScript's toLocaleString('en-IN') gives."""
    try:
        x = float(n)
    except (TypeError, ValueError):
        return '0'
    neg = '-' if x < 0 else ''
    x = abs(x)
    whole, frac = divmod(round(x, 3), 1)
    s = str(int(whole))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ','.join(parts + [tail])
    f = f'{frac:.3f}'[1:].rstrip('0').rstrip('.') if frac else ''
    return neg + s + f


def money(n):
    return '₹' + locale(n or 0)
