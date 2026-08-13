from deep_translator import GoogleTranslator

INDIC_LANGUAGES = ["hi", "ta", "te", "ml", "kn"]


def detect_language(text: str) -> str:
    """
    Detect language from Unicode character ranges.
    Faster and more reliable than langdetect for Indic scripts.
    Returns ISO 639-1 code.
    """
    if not text:
        return "en"
    sample = text[:300]

    checks = [
        ("ta", 0x0B80, 0x0BFF),   
        ("hi", 0x0900, 0x097F),   
        ("te", 0x0C00, 0x0C7F),   
        ("ml", 0x0D00, 0x0D7F),   
        ("kn", 0x0C80, 0x0CFF),   
    ]
    for lang_code, start, end in checks:
        if any(start <= ord(c) <= end for c in sample):
            return lang_code

    return "en"


def translate_to_english(text: str, lang: str) -> str:
    """Translate Indic language input to English before sending to the AI."""
    if not text or lang == "en" or lang not in INDIC_LANGUAGES:
        return text
    try:
        return GoogleTranslator(source=lang, target="en").translate(text) or text
    except Exception as e:
        print(f"Translation Error ({lang}→en): {e}")
        return text


def translate_from_english(text: str, lang: str) -> str:
    """Translate the AI's English answer back to the user's preferred language."""
    if not text or lang == "en" or lang not in INDIC_LANGUAGES:
        return text
    try:
        # Split long text to stay within Google Translate's ~5000 char limit
        if len(text) > 4500:
            split_point = text[:4500].rfind(". ")
            split_point = split_point if split_point != -1 else 4500
            part1 = translate_from_english(text[:split_point + 1], lang)
            part2 = translate_from_english(text[split_point + 1:], lang)
            return part1 + " " + part2
        return GoogleTranslator(source="en", target=lang).translate(text) or text
    except Exception as e:
        print(f"Translation Error (en→{lang}): {e}")
        return text   # always fall back to English — never crash