import re
from enum import StrEnum
from pydantic import BaseModel, EmailStr, HttpUrl, field_validator


class Plan(StrEnum):
    ENTERPRISE = 'Enterprise'
    GROWTH = 'Growth'


class Deal(BaseModel):
    customer_name: str
    contact_email: EmailStr
    ae_name: str | None = None
    ae_email: EmailStr | None = None
    ae_phone: str | None = None
    opportunity_url: HttpUrl

    @field_validator('customer_name', 'ae_name')
    @classmethod
    def nonempty(cls, value):
        if value is None:
            return value
        if not value.strip():
            raise ValueError('Must not be empty')
        return value.strip()

    @field_validator('ae_phone')
    @classmethod
    def phone(cls, value):
        if value is None:
            return value
        if not re.fullmatch(r'\+[1-9]\d{7,14}', value):
            raise ValueError('Use E.164 phone format')
        return value


def explicit_plan(answer):
    # A summary or model-generated classification is never sufficient evidence.
    value = str(answer).strip().rstrip('.!').casefold()
    return {'enterprise': Plan.ENTERPRISE, 'growth': Plan.GROWTH}.get(value)
