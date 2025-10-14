from pydantic import BaseModel


class LetterTemplateBase(BaseModel):
    header: str
    body: str


class LetterTemplateUpdate(LetterTemplateBase):
    """Schema for updating the letter template"""
    pass


class LetterTemplateResponse(LetterTemplateBase):
    """Schema for returning the letter template"""
    id: int

    class Config:
        from_attributes = True
