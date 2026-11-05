VOICE_LANGUAGES = {
    "as-IN": "Assamese",
    "bn-IN": "Bengali",
    "en-IN": "English",
    "gu-IN": "Gujarati",
    "hi-IN": "Hindi",
    "kn-IN": "Kannada",
    "ml-IN": "Malayalam",
    "mr-IN": "Marathi",
    "od-IN": "Odia",
    "pa-IN": "Punjabi",
    "ta-IN": "Tamil",
    "te-IN": "Telugu",
}

DEFAULT_LANGUAGE = "en-IN"

# Used by database check constraints, so stored languages are always valid provider codes.
LANGUAGE_CHECK = "language IN ({})".format(", ".join(f"'{code}'" for code in VOICE_LANGUAGES))


def supported_language(code: str | None) -> str:
    """A code the providers accept: the code itself, its regional form such as en -> en-IN, or the default."""
    if code in VOICE_LANGUAGES:
        return code
    regional = f"{(code or '').split('-')[0].lower()}-IN"
    return regional if regional in VOICE_LANGUAGES else DEFAULT_LANGUAGE
