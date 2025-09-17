from pydantic import BaseModel
from typing import Optional, List

class IngestStats(BaseModel):
    lines: int
    raw_new: int
    raw_dup: int
    runs_new: int
    runs_dups_or_replaced: int
