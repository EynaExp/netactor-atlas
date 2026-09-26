"""Risk taxonomy: map every vulnerability onto a parent category + child.

The taxonomy is a fixed Persian parent/child tree. Every finding produced by a
scan is classified into exactly one pair, so downstream consumers (the ATLAS
app, reports) can group and route vulnerabilities by risk category:

    title   = parent  (e.g. "افشا غیر مجاز")
    profile = child   (e.g. "افشا پسورد")

Classification is keyword-driven (Persian + English) and fully deterministic:
no LLM call, no network, same input always gives the same pair. The original
finding text is never modified — the classification is an overlay, and
``method`` records how it was reached so consumers can re-classify if they
have a better model.

Extend by adding a child to ``TAXONOMY`` and a matching rule to ``RULES``; the
validator in :func:`taxonomy_errors` reports inconsistencies between the two.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

# --- taxonomy (verbatim; parent -> children) -------------------------------

TAXONOMY: Dict[str, List[str]] = {
    "منابع": [
        "استفاده بیش از حد مجاز منابع",
    ],
    "انتقال": [
        "عدم رمزنگاری",
        "فیزیکی - عدم همراه",
        "فیزیکی - عدم رمزنگاری",
    ],
    "زیرساخت": [
        "DNS", "DHCP", "Vlan", "FW", "R/S", "Virtual Machine", "Other Server",
    ],
    "منابع انسانی": [
        "استعفای زود هنگام", "خرابکاری", "کمبود نیروی فنی/ اداری",
        "خطای انسانی و عدم آموزش", "سوء استفاده از دسترسی سطح بالا",
        "کاربر مهمان اتصال به شبکه داخلی",
    ],
    "ذخیره سازی غیر مطمئن": [],
    "افشا غیر مجاز": [
        "اطلاعات محرمانه", "اطلاعات رمز- رمز نگاری", "ارسال اطلاعات به محل اشتباه",
        "افشا پسورد", "تصادفی اطلاعات", "داده های مالی",
    ],
    "لاگ": [
        "عدم جمع آوری لاگ و شواهد", "عدم جمع آوری دنباله ممیزی / حذف لاگ",
    ],
    "امن سازی": [
        "امن سازی",
    ],
    "بروزرسانی": [
        "وجود آسیب پذیری/ عدم بروزرسانی سیستم عامل و تجهیزات",
        "عدم بروزرسانی آنتی ویروس، IPS، IDS",
        "وجود نقاط تهدید پذیر",
    ],
    "فیزیکی": [
        "سرقت (هارد، لپ تاپ، دیگر تجهیزات و افزاره سیار)",
        "از کار انداختن سیستم نظارتی", "از کار انداختن سیستم اطفا حریق",
        "دسترسی غیر مجاز به اطلاعات یا افراد", "عدم احراز هویت",
        "از کار افتادن دستگاه",
    ],
    "نسخه پشتیبان": [
        "عدم Back UP", "عدم تست Back UP", "عدم کارکرد صحیح Back UP",
    ],
    "برق": [
        "تأمین کننده اصلی", "تأمین کننده فرعی (دیزل، UPS، باطری)",
    ],
    "داده": [
        "کپی غیر مجاز داده و اطلاعات", "دستکاری داده", "از بین بردن داده",
    ],
    "دسترسی غیر مجاز": [
        "کنسول مدیریتی /دسترسی Admin",
        "لاگین غیرمجاز- غیر مدیریتی (No Admin)",
        "جعل هویت", "ایجاد سطح دسترسی جدید/دسترسی از راه دور",
    ],
    "انتشار آلودگی": [
        "ویروس - WORM", "USB", "عدم وجود AV", "دانلود برنامه کاربردی - Bot",
    ],
    "نشت اطلاعات": [
        "عدم وجود DLP", "بر روی پایگاه داده", "در حین انتقال", "Phishing انسانی",
    ],
}

# Parents that intentionally have no children: the child stays null.
CHILDLESS_PARENTS = {p for p, c in TAXONOMY.items() if not c}

# Used when no rule matches, so every vulnerability still carries a
# parent/child pair. Change here if you prefer a different catch-all.
FALLBACK: Tuple[str, Optional[str]] = ("زیرساخت", "Other Server")

# --- classifier rules -------------------------------------------------------
# (parent, child, [(keyword, weight), ...]) — higher weight for phrases.
# Rules are evaluated in order; the best total score wins, ties go to the
# earlier (more specific) rule.

RULES: List[Tuple[str, Optional[str], List[Tuple[str, int]]]] = [
    # --- patching / exposure of known CVEs --------------------------------
    ("بروزرسانی", "وجود آسیب پذیری/ عدم بروزرسانی سیستم عامل و تجهیزات", [
        ("cve-", 5), ("cve ", 4), ("known vulnerability", 4), ("known cve", 4),
        ("vulnerable", 3), ("vulnerability", 2), ("unpatched", 4), ("patch", 3),
        ("patch management", 4), ("end of life", 4), ("eol", 2), ("outdated", 3),
        ("out-of-date", 3), ("old version", 3), ("legacy version", 3),
        ("version disclosure", 2), ("backport", 2), ("security update", 3),
        ("آسیب پذیری", 4), ("آسیب‌پذیری", 4), ("بروزرسانی", 4), ("به روز رسانی", 4),
        ("وصله", 3), ("نسخه قدیمی", 3), ("قدیمی", 2), ("منقضی", 2), ("روز رسانی", 3),
    ]),
    ("بروزرسانی", "عدم بروزرسانی آنتی ویروس، IPS، IDS", [
        ("ips", 4), ("ids", 3), ("antivirus signature", 5), ("av signature", 5),
        ("signature database", 4), ("definition update", 3),
        ("آنتی ویروس", 4), ("آنتی‌ویروس", 4), ("ضد ویروس", 3), ("امضای", 2), ("سیگنچر", 3),
    ]),
    ("بروزرسانی", "وجود نقاط تهدید پذیر", [
        ("exposed threat", 4), ("threat surface", 4), ("نقطه تهدید", 4),
    ]),

    # --- malware / propagation --------------------------------------------
    ("انتشار آلودگی", "ویروس - WORM", [
        ("malware", 5), ("virus", 4), ("worm", 5), ("ransomware", 5), ("trojan", 5),
        ("backdoor", 4), ("rootkit", 5), ("spyware", 5), ("keylogger", 5),
        ("ویروس", 4), ("بدافزار", 5), ("باج افزار", 5), ("تروجان", 5),
        ("جاسوسی", 3), ("کی‌لاگر", 4),
    ]),
    ("انتشار آلودگی", "USB", [
        ("usb", 5), ("removable media", 5), ("flash drive", 5), ("thumb drive", 5),
        (" فلش", 5), ("یو اس بی", 5), ("حافظه جانبی", 4), ("درایو قابل", 4),
    ]),
    ("انتشار آلودگی", "عدم وجود AV", [
        ("no antivirus", 6), ("antivirus not installed", 6), ("av not detected", 5),
        ("missing av", 5), ("no endpoint protection", 6), ("edr", 3),
        ("بدون ضد ویروس", 6), ("فاقد آنتی ویروس", 6), ("آنتی ویروس نصب", 5),
    ]),
    ("انتشار آلودگی", "دانلود برنامه کاربردی - Bot", [
        ("botnet", 5), (" bot ", 3), ("download and execute", 5),
        ("insecure download", 4), ("auto download", 3), ("دانلود برنامه", 4), ("ربات", 3),
    ]),

    # --- unauthorized access ----------------------------------------------
    ("دسترسی غیر مجاز", "کنسول مدیریتی /دسترسی Admin", [
        ("admin panel", 5), ("management console", 5), ("admin console", 5),
        ("administrative interface", 5), ("web admin", 4), ("admin interface", 4),
        ("کنسول مدیریتی", 5), ("پنل مدیریت", 5), ("رابط مدیریت", 4),
    ]),
    ("دسترسی غیر مجاز", "لاگین غیرمجاز- غیر مدیریتی (No Admin)", [
        ("unauthenticated", 4), ("no authentication", 5), ("anonymous login", 5),
        ("default credentials", 4), ("weak password", 4), ("guessable password", 4),
        ("exposed service", 3), ("publicly accessible", 3), ("login bypass", 5),
        ("is exposed", 2), ("exposed on port", 3), ("accepts connections from the network", 4),
        ("ورود بدون احراز", 5), ("بدون احراز هویت", 5), ("رمز پیش فرض", 4),
        ("دسترسی بدون رمز", 5), ("لاگین", 3),
    ]),
    ("دسترسی غیر مجاز", "جعل هویت", [
        ("spoofing", 5), ("impersonation", 4), ("session hijack", 5),
        ("man in the middle", 5), ("man-in-the-middle", 5), ("identity spoof", 5),
        ("jwt", 2), ("جعل هویت", 5), ("جعل", 3),
    ]),
    ("دسترسی غیر مجاز", "ایجاد سطح دسترسی جدید/دسترسی از راه دور", [
        ("remote access", 5), ("remote desktop", 5), ("privilege escalation", 5),
        ("elevated privilege", 5), ("new privilege level", 5), ("rdp", 4),
        ("ssh exposed", 5), ("remote shell", 4), ("vpn", 2),
        ("دسترسی از راه دور", 5), ("سطح دسترسی", 4), ("ارتقاء سطح دسترسی", 5),
        ("دسترسی ریموت", 5),
    ]),

    # --- disclosure / leakage ---------------------------------------------
    ("افشا غیر مجاز", "افشا پسورد", [
        ("password leak", 6), ("leaked credential", 6), ("exposed password", 6),
        ("hardcoded password", 6), ("password in url", 5), ("plaintext password", 5),
        ("password in source", 5), ("credentials in code", 5),
        ("افشا پسورد", 6), ("رمز عبور هارد", 5), ("پسورد در کد", 5),
    ]),
    ("افشا غیر مجاز", "اطلاعات رمز- رمز نگاری", [
        ("private key exposure", 6), ("key file", 4), ("cryptographic key", 4),
        ("readable private key", 6), ("id_rsa", 5), ("کلید خصوصی", 5),
        ("کلید رمزنگاری", 4),
    ]),
    ("افشا غیر مجاز", "اطلاعات محرمانه", [
        ("confidential information", 5), ("sensitive data exposed", 5),
        ("personal data", 3), ("pii", 4), ("customer record", 4),
        ("path traversal", 7), ("directory traversal", 7), ("arbitrary file read", 7),
        ("read arbitrary file", 7), ("information disclosure", 5),
        ("sensitive file", 5), ("downloads arbitrary file", 7),
        ("اطلاعات محرمانه", 5), ("اطلاعات حساس", 4), ("داده شخصی", 3),
        ("افشا اطلاعات", 5), ("پیمایش مسیر", 6), ("خواندن فایل", 5),
    ]),
    ("افشا غیر مجاز", "ارسال اطلاعات به محل اشتباه", [
        ("wrong recipient", 6), ("misdirected", 6), ("sent to the wrong", 5),
        ("ارسال اطلاعات به محل اشتباه", 6), ("گیرنده اشتباه", 6),
    ]),
    ("افشا غیر مجاز", "تصادفی اطلاعات", [
        ("inadvertent disclosure", 6), ("accidental disclosure", 6),
        ("information disclosure through", 4), ("unintended disclosure", 5),
        ("تصادفی اطلاعات", 6), ("افشای تصادفی", 6), ("نشت تصادفی", 5),
    ]),
    ("افشا غیر مجاز", "داده های مالی", [
        ("financial data", 5), ("credit card", 5), ("payment card", 5),
        ("pci", 3), ("cardholder", 5), ("bank account", 4),
        ("داده های مالی", 5), ("اطلاعات کارت", 5), ("مالی", 2),
    ]),
    ("نشت اطلاعات", "عدم وجود DLP", [
        ("dlp", 6), ("data loss prevention", 6), ("exfiltration", 5),
        ("data exfiltration", 6), ("نشت داده", 5), ("خروج داده", 4),
    ]),
    ("نشت اطلاعات", "بر روی پایگاه داده", [
        ("sql injection", 6), ("sqli", 5), ("exposed database", 5),
        ("unauthenticated database", 6), ("mongodb", 3), ("database dump", 5),
        ("redis unauthenticated", 6), ("تزریق اس کیو ال", 6), ("تزریق sql", 6),
        ("پایگاه داده بدون احراز", 6), ("پایگاه داده", 2),
    ]),
    ("نشت اطلاعات", "در حین انتقال", [
        ("data leak in transit", 6), ("sensitive data in transit", 6),
        ("transmitted in cleartext", 5), ("cleartext credentials transmitted", 6),
        ("افشا در حین انتقال", 6), ("ارسال اطلاعات رمز", 5),
    ]),
    ("نشت اطلاعات", "Phishing انسانی", [
        ("phishing", 6), ("spear phishing", 6), ("social engineering", 5),
        ("credential harvesting", 6), ("فیشینگ", 6),
    ]),

    # --- transport / storage ----------------------------------------------
    ("انتقال", "عدم رمزنگاری", [
        ("unencrypted", 5), ("cleartext", 4), ("no tls", 5), ("no ssl", 5),
        ("plaintext transmission", 5), ("insecure transport", 5),
        ("snmpv1", 5), ("telnet", 5), ("ftp without", 5), ("ldap without", 5),
        ("رمزنگاری نشده", 5), ("بدون رمزنگاری", 5), ("ترافیک بدون رمز", 5),
    ]),
    ("ذخیره سازی غیر مطمئن", None, [
        ("unencrypted disk", 6), ("unencrypted storage", 6), ("unencrypted file", 5),
        ("plaintext file on disk", 6), ("weak storage encryption", 5),
        ("at rest not encrypted", 6), ("ذخیره سازی غیر رمز", 6),
        ("هارد بدون رمز", 6), ("بدون رمزگذاری", 5),
    ]),

    # --- data integrity / availability ------------------------------------
    ("داده", "دستکاری داده", [
        ("data tampering", 6), ("data manipulation", 5), ("integrity violation", 5),
        ("tampered data", 5), ("دستکاری داده", 6), ("تغییر داده", 5),
    ]),
    ("داده", "از بین بردن داده", [
        ("data destruction", 6), ("data deletion", 5), ("wiper", 5),
        ("data loss", 3), ("از بین بردن داده", 6), ("حذف داده", 5),
    ]),
    ("داده", "کپی غیر مجاز داده و اطلاعات", [
        ("unauthorized copy", 6), ("data copy", 4), ("cloning of data", 5),
        ("کپی غیر مجاز", 6), ("کپی داده", 5),
    ]),
    ("منابع", "استفاده بیش از حد مجاز منابع", [
        ("denial of service", 6), ("dos attack", 5), ("resource exhaustion", 6),
        ("excessive resource", 5), ("overuse of resources", 5), ("cpu exhaustion", 5),
        ("مصرف بیش از حد", 5), ("منابع", 2),
    ]),

    # --- logging -----------------------------------------------------------
    ("لاگ", "عدم جمع آوری دنباله ممیزی / حذف لاگ", [
        ("audit trail", 5), ("log deletion", 6), ("logs cleared", 6),
        ("deleted logs", 6), ("log wiping", 6), ("حذف لاگ", 6),
        ("پاک کردن لاگ", 6), ("دنباله ممیزی", 5),
    ]),
    ("لاگ", "عدم جمع آوری لاگ و شواهد", [
        ("no logging", 6), ("logging disabled", 6), ("logs not collected", 6),
        ("missing log", 5), ("audit logging disabled", 6), ("log retention", 4),
        ("عدم ثبت لاگ", 6), ("لاگ غیرفعال", 6), ("جمع آوری لاگ", 5), ("لاگ", 2),
    ]),

    # --- backup / power ----------------------------------------------------
    ("نسخه پشتیبان", "عدم تست Back UP", [
        ("backup not tested", 6), ("untested backup", 6), ("restore test", 5),
        ("تست بکاپ", 6), ("بازیابی تست", 4),
    ]),
    ("نسخه پشتیبان", "عدم کارکرد صحیح Back UP", [
        ("backup failed", 6), ("incomplete backup", 6), ("corrupt backup", 6),
        ("restore failure", 5), ("بکاپ ناموفق", 6), ("بازیابی ناموفق", 5),
    ]),
    ("نسخه پشتیبان", "عدم Back UP", [
        ("no backup", 6), ("backup missing", 6), ("backup not configured", 6),
        ("snapshots not taken", 4), ("عدم پشتیبان", 6), ("بکاپ", 3),
    ]),
    ("برق", "تأمین کننده فرعی (دیزل، UPS، باطری)", [
        ("ups", 5), ("diesel", 5), ("generator", 4), ("battery backup", 5),
        ("یو پی اس", 5), ("دیزل ژنراتور", 5), ("باتری", 4),
    ]),
    ("برق", "تأمین کننده اصلی", [
        ("power supply", 5), ("utility power", 5), ("mains", 4),
        ("power outage", 4), ("منبع تغذیه", 5), ("برق", 2),
    ]),

    # --- physical ----------------------------------------------------------
    ("فیزیکی", "سرقت (هارد، لپ تاپ، دیگر تجهیزات و افزاره سیار)", [
        ("theft", 5), ("stolen", 5), ("laptop", 3), ("notebook left", 4),
        ("سرقت", 5), ("سرقت تجهیزات", 6), ("لپ تاپ", 3),
    ]),
    ("فیزیکی", "از کار انداختن سیستم نظارتی", [
        ("cctv", 5), ("surveillance", 4), ("camera disabled", 5),
        ("دوربین", 4), ("سیستم نظارتی", 5),
    ]),
    ("فیزیکی", "از کار انداختن سیستم اطفا حریق", [
        ("fire suppression", 5), ("fire alarm", 5), ("sprinkler", 4),
        ("اطفا حریق", 5), ("هشدار حریق", 5),
    ]),
    ("فیزیکی", "دسترسی غیر مجاز به اطلاعات یا افراد", [
        ("unauthorized physical access", 6), ("physical access to data", 5),
        ("tailgating", 5), ("دسترسی فیزیکی", 5), ("دسترسی غیر مجاز به اطلاعات", 5),
    ]),
    ("فیزیکی", "عدم احراز هویت", [
        ("no badge", 5), ("badge reader", 4), ("physical authentication", 5),
        ("کارت دسترسی", 4), ("احراز هویت فیزیکی", 5),
    ]),
    ("فیزیکی", "از کار افتادن دستگاه", [
        ("device offline", 4), ("tamper switch", 4), ("hardware failure", 4),
        ("از کار افتادن دستگاه", 5), ("خرابی سخت افزار", 4),
    ]),

    # --- human factors -----------------------------------------------------
    ("منابع انسانی", "سوء استفاده از دسترسی سطح بالا", [
        ("abuse of privilege", 6), ("insider", 5), ("misuse of admin", 5),
        ("سوء استفاده از دسترسی", 6), ("دسترسی سطح بالا", 4),
    ]),
    ("منابع انسانی", "خطای انسانی و عدم آموزش", [
        ("human error", 5), ("user misconfiguration", 5), ("lack of training", 5),
        ("operator error", 5), ("خطای انسانی", 5), ("عدم آموزش", 5),
    ]),
    ("منابع انسانی", "کاربر مهمان اتصال به شبکه داخلی", [
        ("guest access", 5), ("guest wifi", 5), ("guest network", 5),
        ("کاربر مهمان", 5),
    ]),

    # --- hardening / infrastructure ---------------------------------------
    ("امن سازی", "امن سازی", [
        ("hardening", 4), ("insecure configuration", 5), ("insecure default", 5),
        ("misconfiguration", 4), ("default configuration", 3), ("banner", 2),
        ("سخت سازی", 4), ("پیکربندی ناامن", 5), ("تنظیمات ناامن", 5),
    ]),
    ("زیرساخت", "DNS", [("dns", 4), ("dnssec", 5), ("دی ان اس", 4)]),
    ("زیرساخت", "DHCP", [("dhcp", 4), ("دی اچ سی پی", 4)]),
    ("زیرساخت", "Vlan", [("vlan", 4), ("vlan hopping", 6), ("ولن", 3)]),
    ("زیرساخت", "FW", [("firewall", 4), ("fw rule", 4), ("فایروال", 4)]),
    ("زیرساخت", "R/S", [("router", 4), ("switch", 4), ("روتر", 4), ("سوئیچ", 4)]),
    ("زیرساخت", "Virtual Machine", [
        ("virtual machine", 4), ("hypervisor", 4), ("virtualization", 3),
        ("vm escape", 6), ("ماشین مجازی", 4), ("هایپرویژور", 4),
    ]),
    ("زیرساخت", "Other Server", [
        ("server", 2), ("service version", 3), ("banner", 2), ("openssh", 2),
        ("میکروت", 2), ("سرور", 2), ("سرویس", 2),
    ]),
]

# Pre-compiled matchers: (compiled regex, weight, parent, child)
_MATCHERS = [
    (re.compile(re.escape(kw), re.IGNORECASE), w, p, c)
    for p, c, kws in RULES for kw, w in kws
]

_WS = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Lowercase, collapse whitespace, pad with spaces so ' bot ' matches."""
    return " " + _WS.sub(" ", (text or "").lower()) + " "


def classify(*texts: Optional[str]) -> Dict[str, Any]:
    """Classify a vulnerability into ``(parent, child)`` of the taxonomy.

    ``texts`` are the finding's own words (title, description, remediation) and
    optionally the NVD description — more signal, better match. Returns::

        {"parent": str, "child": str | None, "method": "keyword" | "fallback",
         "score": int, "matched": [keyword, ...]}

    ``child`` is ``None`` only for parents that intentionally have no children
    (e.g. "ذخیره سازی غیر مطمئن").
    """
    blob = normalize(" \n ".join(t for t in texts if t))
    scores: Dict[Tuple[str, Optional[str]], int] = {}
    hits: Dict[Tuple[str, Optional[str]], List[str]] = {}

    for pattern, weight, parent, child in _MATCHERS:
        key = (parent, child)
        if pattern.search(blob):
            scores[key] = scores.get(key, 0) + weight
            hits.setdefault(key, []).append(pattern.pattern)

    if scores:
        best = max(
            scores.items(),
            key=lambda kv: (kv[1], -RULES.index(_rule_for(kv[0]))),
        )
        parent, child = best[0]
        return {
            "parent": parent,
            "child": child,
            "method": "keyword",
            "score": best[1],
            "matched": sorted(set(hits[best[0]]))[:8],
        }

    parent, child = FALLBACK
    return {"parent": parent, "child": child, "method": "fallback", "score": 0, "matched": []}


def _rule_for(key: Tuple[str, Optional[str]]) -> Tuple[str, Optional[str], list]:
    for rule in RULES:
        if (rule[0], rule[1]) == key:
            return rule
    return ("", None, [])


def is_valid(parent: str, child: Optional[str]) -> bool:
    """True when the pair exists in the taxonomy."""
    if parent not in TAXONOMY:
        return False
    if child is None:
        return parent in CHILDLESS_PARENTS
    return child in TAXONOMY[parent]


def taxonomy_errors() -> List[str]:
    """Report taxonomy/rules inconsistencies (used by tests and maintenance)."""
    problems: List[str] = []
    for parent, child, _ in RULES:
        if parent not in TAXONOMY:
            problems.append(f"rule references unknown parent: {parent!r}")
        elif child is not None and child not in TAXONOMY[parent]:
            problems.append(f"rule ({parent!r}, {child!r}): child not in taxonomy")
    if not is_valid(*FALLBACK):
        problems.append(f"fallback {FALLBACK!r} is not a valid taxonomy pair")
    return problems
