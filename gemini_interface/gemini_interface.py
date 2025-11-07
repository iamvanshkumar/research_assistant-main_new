# gemini_interface/gemini_interface.py
import os
import google.generativeai as genai
from dotenv import load_dotenv
from research_paper_analyst import RESEARCH_PAPER, FOLLOWUP_CONTEXT

load_dotenv()


def get_model():
    """Return a ready-to-use Gemini 2.5 Flash model."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set in .env")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-2.5-flash")


def analyze_pdf_content(model, pdf_content: str):
    """Yield streaming chunks from the PDF + prompt."""
    try:
        response = model.generate_content(
            [{"mime_type": "application/pdf", "data": pdf_content}, RESEARCH_PAPER],
            stream=True,
        )
        for chunk in response:
            yield chunk
    except Exception as e:
        raise RuntimeError(f"Error analyzing PDF content: {str(e)}")


def process_query_stream(model, pdf_content: str, notes: str, query: str):
    """Yield streaming answer for a follow-up question."""
    try:
        context = f"{notes}\n\n{FOLLOWUP_CONTEXT}\n\n{query}"
        response = model.generate_content(
            [{"mime_type": "application/pdf", "data": pdf_content}, context],
            stream=True,
        )
        for chunk in response:
            yield chunk
    except Exception as e:
        yield f"Error processing query: {str(e)}"
