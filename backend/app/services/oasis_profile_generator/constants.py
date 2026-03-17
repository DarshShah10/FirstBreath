"""
Constants for the OASIS Agent Profile generator.
"""

# All 16 MBTI personality types
MBTI_TYPES = [
    "INTJ", "INTP", "ENTJ", "ENTP",
    "INFJ", "INFP", "ENFJ", "ENFP",
    "ISTJ", "ISFJ", "ESTJ", "ESFJ",
    "ISTP", "ISFP", "ESTP", "ESFP",
]

# Common countries for profile generation
COUNTRIES = [
    "China", "US", "UK", "Japan", "Germany", "France",
    "Canada", "Australia", "Brazil", "India", "South Korea",
]

# Individual entity types — require a concrete persona
INDIVIDUAL_ENTITY_TYPES = [
    "student", "alumni", "professor", "person", "publicfigure",
    "expert", "faculty", "official", "journalist", "activist",
]

# Group / institutional entity types — require a representative account persona
GROUP_ENTITY_TYPES = [
    "university", "governmentagency", "organization", "ngo",
    "mediaoutlet", "company", "institution", "group", "community",
]
