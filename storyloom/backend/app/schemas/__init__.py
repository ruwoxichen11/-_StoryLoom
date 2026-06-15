"""请求/响应数据契约"""
from pydantic import BaseModel
from typing import List, Optional


class CreateWorkReq(BaseModel):
    title: str
    synopsis: str = ""


class InspirationReq(BaseModel):
    text: str


class GeneEditReq(BaseModel):
    gene: dict


class CharacterEditReq(BaseModel):
    characters: List[dict]


class OutlineEditReq(BaseModel):
    beats: Optional[List[dict]] = None
    threads: Optional[List[dict]] = None
    locked: Optional[bool] = None


class ChapterBriefReq(BaseModel):
    brief: str = ""


class SettingsPatchReq(BaseModel):
    patch: dict
