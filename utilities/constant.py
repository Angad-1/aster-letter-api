REQUIRED_COLUMNS = [
    "S. No",
    "E Code",
    "Name",
    "Band",
    "Designation",
    "Vertical",
    "Currency",
    "Business Unit",
    "Department",
    "Performance year",
    "Rating Label",
    "Promotion",
    "New Designation",
    "New Role Band",
    "AED Per Month",
    "Organizational Allowance",
    "Next Review Date",
    "New salary effective date",
    "New salary effective Year",
    "Current Basic Salary",
    "Current HRA",
    "Current Other Allowances",
    "Current Individual Allowances",
    "Current Compulsory OT",
    "Current Fixed Salary (A)",
    "Current Vehicle Allowance",
    "Current Telephone Allowance",
    "Current Special Allowances",
    "Current Salik Allowance",
    "Current Travel & Mobile Allowance (B)",
    "Current Total Gross Salary (TGS) (A) + (B)",
    "New Basic Salary",
    "New HRA",
    "New Other Allowances",
    "New Individual Allowances",
    "New Compulsory OT",
    "New Fixed Salary (A,)",
    "New Vehicle Allowance",
    "New Telephone Allowance",
    "New Special Allowances",
    "New Salik Allowance",
    "New Travel & Mobile Allowance (B)",
    "New Total Gross Salary (TGS) (A) + (B)",
    "PIP Duration",
    "PIP Effective Date",
    "Letter type",
    "Signatory Designation",
    "Signatory Name"
]

LETTER_TEMPLATE_MAP = {
    "rating_increment_oa_less_than_10k": "rating_increment_oa_less_than_10k.html",
    "rating_increment_oa_more_than_10k": "rating_increment_oa_more_than_10k.html",
    "rating_increment_promotion_oa_less_than_10k": "rating_increment_promotion_oa_less_than_10k.html",
    "rating_increment_promotion_oa_more_than_10k": "rating_increment_promotion_oa_more_than_10k.html",
    "rating_increment_promotion": "rating_increment_promotion.html",
    "rating_increment": "rating_increment.html",
    "rating_oa_less_than_10K": "rating_oa_less_than_10K.html",
    "rating_oa_more_than_10K": "rating_oa_more_than_10K.html",
    "rating": "rating.html",
    "PIP": "PIP.html",
}


class ActivityType:
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    USER_LOGOUT = "USER_LOGOUT"
    USER_CREATED = "USER_CREATED"
    PROFILE_UPDATED = "PROFILE_UPDATED"
    USER_UPDATED = "USER_UPDATED"
    PASSWORD_CHANGED = "PASSWORD_CHANGED"
    USER_PASSWORD_CHANGED = "USER_PASSWORD_CHANGED"
    PROFILE_PICTURE_CHANGED = "PROFILE_PICTURE_CHANGED"
    USER_PROFILE_PICTURE_CHANGED = "USER_PROFILE_PICTURE_CHANGED"
    USER_DELETED = "USER_DELETED"
    USER_ACTIVATED = "USER_ACTIVATED"
    USER_DEACTIVATED = "USER_DEACTIVATED"
    LETTER_GENERATED = "LETTER_GENERATED"
    
class ActivityModule:
    AUTH = "auth"
    PROFILE = "profile"
    USER_MASTER = "user_master"
    LETTER = "letter_generation"
    FILE = "file_upload"
    
class ActivityMessage:
    LOGIN = "User logged in"
    LOGOUT = "Logged out"
    USER_LOGOUT = "Logged out user"
    USER_CREATED = "Created user"
    PROFILE_UPDATED = "Updated profile"
    USER_UPDATED = "Updated user details from user master"
    PASSWORD_CHANGED = "Password changed successfully"
    PROFILE_PICTURE_CHANGED = "Updated own profile picture"
    USER_PROFILE_PICTURE_CHANGED = "Updated profile picture for user"
    USER_DELETED = "Deleted user"
    USER_ACTIVATED = "Activated user"
    USER_DEACTIVATED = "Deactivated user"
    LETTER_GENERATED = "Letter generated successfully"
    
class ActivityStatus:
    SUCCESS= "success"
    FAILED="failed"
