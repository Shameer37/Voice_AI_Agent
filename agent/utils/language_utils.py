# import re

# def detect_language(text: str) -> str:
#     hindi_chars = re.compile(r'[\u0900-\u097F]')
#     if hindi_chars.search(text):
#         return "hi"
#     return "en"

#----------------------

def detect_language(text: str) -> str:
    return "hindi"
