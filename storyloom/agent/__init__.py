"""故事织机 - 智能体层

角色阵容（与"片场/导演"无关的全新命名）：
- MuseAgent       灵感缪斯：把灵感提炼为四维故事基因
- CastmakerAgent  选角师：生成角色阵容
- LoomPlannerAgent 织线师：规划故事经纬（大纲 + 支线）
- ShowrunnerAgent 戏剧统筹：圆桌戏台的调度大脑，输出 JSON 指令
- ActorAgent      角色演绎体：走 ReAct（思考->检索/查设定->发言）
- ScribeAgent     誊抄师：把研讨原稿润色成正文
- AuditorAgent    审稿人：一致性复核

核心创新：ActorAgent 与部分环节使用 LangChain 的 ReAct 推理，
显式产出 Thought(CoT) -> Action(tool routing) -> Observation 链路。
"""
from .roles import (
    MuseAgent,
    CastmakerAgent,
    LoomPlannerAgent,
    ShowrunnerAgent,
    ScribeAgent,
    AuditorAgent,
    build_actor,
)

__all__ = [
    "MuseAgent",
    "CastmakerAgent",
    "LoomPlannerAgent",
    "ShowrunnerAgent",
    "ScribeAgent",
    "AuditorAgent",
    "build_actor",
]
