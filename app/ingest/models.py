from datetime import datetime

from pydantic import BaseModel


class Message(BaseModel):
    ts: datetime
    sender: str
    text: str
