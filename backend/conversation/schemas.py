from dataclasses import dataclass

# =====================================================================
# Session Config
# =====================================================================

@dataclass
class SessionConfig:
    language: str = "English"
    company_name: str = "Our Company"
    debt_type: str = "credit_card"

    def validate(self) -> None:
        if self.language not in ("English", "Spanish"):
            raise ValueError(f"Unsupported language: {self.language}")
        if self.debt_type not in ("credit_card", "mortgage", "insurance_premium"):
            raise ValueError(f"Unsupported debt_type: {self.debt_type}")


def _lang_key(language: str) -> str:
    return "es" if language == "Spanish" else "en"