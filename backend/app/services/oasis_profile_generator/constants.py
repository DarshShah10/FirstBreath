"""
Constants for the VahanAI Emergency Response Unit Profile generator.
"""

# Emergency response unit type codes (maps to the mbti field in OASIS profiles)
UNIT_TYPES = [
    "ALS_Ambulance",
    "BLS_Ambulance",
    "Doctor_Surgeon",
    "Trauma_Nurse",
    "Dispatcher",
    "BloodBank",
    "OperatingTheater",
    "Hospital",
]

# Base locations for fallback profile generation
BASE_LOCATIONS = [
    "Apollo Hospital",
    "City General Hospital",
    "North District Control",
    "South Sector Base",
    "Central Dispatch Hub",
    "Regional Blood Bank",
    "St. Mary Medical Center",
    "Emergency Response Command",
]

# Individual unit types — mobile responders that require a concrete operational dossier
INDIVIDUAL_ENTITY_TYPES = [
    "ambulance",
    "paramedic",
    "doctor",
    "surgeon",
    "nurse",
    "dispatcher",
    "responder",
    "medic",
    "person",
    "driver",
]

# Group / facility entity types — stationary resources requiring a capacity-based profile
GROUP_ENTITY_TYPES = [
    "hospital",
    "bloodbank",
    "operatingtheater",
    "dispatchcenter",
    "clinic",
    "organization",
    "institution",
    "facility",
    "group",
    "community",
]
