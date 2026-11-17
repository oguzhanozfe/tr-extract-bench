"""Checksum-valid Turkish identifiers (VKN, TCKN, IBAN) for synthetic documents.

All generated values are random and fictional. Bank codes used by the generator
sit in the 9xxxx range so a generated IBAN never points at a real bank's code.
"""


def vkn_check_digit(first9: str) -> str:
    total = 0
    for i, ch in enumerate(first9):
        tmp = (int(ch) + 9 - i) % 10
        v = (tmp * 2 ** (9 - i)) % 9
        if tmp != 0 and v == 0:
            v = 9
        total += v
    return str((10 - total % 10) % 10)


def is_vkn(s: str) -> bool:
    return len(s) == 10 and s.isdigit() and vkn_check_digit(s[:9]) == s[9]


def make_vkn(rng) -> str:
    first9 = str(rng.randint(1, 9)) + "".join(str(rng.randint(0, 9)) for _ in range(8))
    return first9 + vkn_check_digit(first9)


def tckn_check_digits(first9: str) -> str:
    d = [int(c) for c in first9]
    d10 = ((d[0] + d[2] + d[4] + d[6] + d[8]) * 7 - (d[1] + d[3] + d[5] + d[7])) % 10
    d11 = (sum(d) + d10) % 10
    return f"{d10}{d11}"


def is_tckn(s: str) -> bool:
    return len(s) == 11 and s.isdigit() and s[0] != "0" and tckn_check_digits(s[:9]) == s[9:]


def make_tckn(rng) -> str:
    first9 = str(rng.randint(1, 9)) + "".join(str(rng.randint(0, 9)) for _ in range(8))
    return first9 + tckn_check_digits(first9)


def _iban_mod97(iban: str) -> int:
    moved = iban[4:] + iban[:4]
    digits = "".join(str(int(c, 36)) for c in moved)
    return int(digits) % 97


def is_iban(s: str) -> bool:
    s = s.replace(" ", "").upper()
    return len(s) >= 15 and s[:2].isalpha() and _iban_mod97(s) == 1


def make_iban(rng, bank_code: str) -> str:
    """TR IBAN: TR + 2 check + 5 bank code + 1 reserved '0' + 16 account digits."""
    bban = bank_code + "0" + "".join(str(rng.randint(0, 9)) for _ in range(16))
    check = 98 - _iban_mod97("TR00" + bban)
    return f"TR{check:02d}{bban}"


def group4(iban: str) -> str:
    return " ".join(iban[i:i + 4] for i in range(0, len(iban), 4))
