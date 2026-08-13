import os
import re
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from deep_translator import GoogleTranslator
from dotenv import load_dotenv

load_dotenv()

chat_llm = ChatOpenAI(
    model="llama-3.1-8b-instant",
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
    max_tokens=300,
    temperature=0.1,
)

rec_prompt = PromptTemplate.from_template(
    "Suggest 3 short follow-up questions for this legal answer. "
    "One per line. No numbers. No bullet points. Keep each under 10 words.\n"
    "Answer: {english_answer}"
)


def generate_recommendations(eng_answer: str, language: str = "en") -> list:
    """
    FIX: Always generates questions in English (LLaMA is reliable in English),
    then translates to the user's language using Google Translate.
    Old code asked LLaMA to translate — gave inconsistent Tamil/Hindi output.
    """
    try:
        # Step 1: Generate questions in English
        raw = (rec_prompt | chat_llm | StrOutputParser()).invoke(
            {"english_answer": eng_answer}
        ).strip()

        # Clean up AI formatting artifacts (numbers, bullets, dashes)
        questions = [
            re.sub(r'^\d+[\.\)]\s*|^[\-\*\u2022]\s*', '', line).strip()
            for line in raw.split("\n")
            if len(line.strip()) > 5
        ]
        questions = questions[:3]

        # Step 2: Translate to user's language via Google Translate
        # FIX: Extended to all 6 languages (was missing ml, kn)
        if language != "en" and questions:
            translated = []
            for q in questions:
                try:
                    t = GoogleTranslator(source="en", target=language).translate(q)
                    translated.append(t if t else q)
                except Exception:
                    translated.append(q)  # keep English if one fails
            return translated

        return questions

    except Exception as e:
        print(f"Recommendation error: {e}")
        # Hardcoded fallbacks in all 6 languages — never returns an empty list
        fallbacks = {
            "en": ["What are the next steps?",    "Are there any penalties?",       "Explain this in detail."],
            "ta": ["அடுத்த படிகள் என்ன?",          "ஏதாவது அபராதம் உள்ளதா?",          "இதை விரிவாக விளக்குங்கள்."],
            "hi": ["अगले कदम क्या हैं?",            "क्या कोई दंड है?",                 "इसे विस्तार से समझाएं।"],
            "te": ["తదుపరి దశలు ఏమిటి?",            "ఏదైనా జరిమానా ఉందా?",              "దీన్ని వివరంగా వివరించండి."],
            "ml": ["അടുത്ത ഘട്ടങ്ങൾ എന്തൊക്കെ?",    "എന്തെങ്കിലും പിഴ ഉണ്ടോ?",          "ഇത് വിശദമായി വിശദീകരിക്കുക."],
            "kn": ["ಮುಂದಿನ ಹಂತಗಳು ಯಾವುವು?",         "ಯಾವುದಾದರೂ ದಂಡ ಇದೆಯೇ?",            "ಇದನ್ನು ವಿವರವಾಗಿ ವಿವರಿಸಿ."],
        }
        return fallbacks.get(language, fallbacks["en"])