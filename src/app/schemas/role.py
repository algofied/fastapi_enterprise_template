from pydantic import BaseModel

class RoleRead(BaseModel):
    name: str

    class Config:
        orm_mode = True
