"""故事织机 - 智能体角色实现

所有 Agent 都基于 LangChain（langchain-core 的消息/工具抽象）。其中：
- 规划类 Agent（缪斯/选角/织线/统筹/誊抄/审稿）走 LCEL 思路的 Chain（prompt -> llm），
  并在 system prompt 中显式要求"先思考再结论"以体现 CoT。
- ActorAgent（角色演绎体）走一个自实现的 ReAct 推理循环：
  显式产出 Thought(CoT) -> Action(工具路由) -> Observation -> ... -> Final Answer，
  工具用 LangChain 的 StructuredTool 定义并由 LLM 自主选择调用。
  （之所以手写循环而非用 langchain.agents.AgentExecutor，是为了不被 LangChain
   版本频繁变动的高阶 API 绑死，同时把完整推理链 trace 暴露给前端展示。）
"""
from __future__ import annotations

import json
from typing import AsyncGenerator, Callable, Dict, List, Optional

from langchain_core.messages import SystemMessage, HumanMessage

from model import get_chat
from model.llm_factory import astream_chat, acomplete
from .persona import compose_system_prompt
from .tools import build_actor_tools


# ============================================================
# 各 Agent 的角色指令（system prompt 核心段）
# ============================================================

MUSE_INSTRUCTION = """你是「灵感缪斯」。任务：把用户给的任意长度灵感（一句话或长随笔），
提炼为一组结构化的"故事基因"。请先在心里推演（即便只有一句话也要合理脑补），再输出。
严格只输出如下 JSON，不要任何多余文字：
{
  "genre": "题材类型，如 都市悬疑/东方玄幻/科幻末世",
  "mood": "整体基调，如 冷峻克制/热血爽快/温情治愈",
  "core_tension": "贯穿全书的核心矛盾，一句话",
  "world_premise": "世界观前提/底层规则，2-3句",
  "keywords": ["3-6个意象关键词"],
  "scale_hint": "建议篇幅，如 中篇8万字 / 长篇30万字"
}"""

CASTMAKER_INSTRUCTION = """你是「选角师」。根据给定的故事基因，设计一组互相咬合、能产生戏剧冲突的角色。
请先思考人物之间的关系网，再输出。严格只输出 JSON：
{
  "cast": [
    {
      "name": "角色名",
      "archetype": "定位，如 主角/反派/导师/搅局者",
      "look": "外形速写一句",
      "temper": "性格，三到四个关键词",
      "drive": "核心动机",
      "flaw": "致命弱点",
      "tagline": "口头禅或标志性台词",
      "secret": "不对外公开的隐藏目的（演绎时角色本人不自知）",
      "accent": "颜色十六进制，用于前端区分，如 #c0392b"
    }
  ]
}
角色数 3-6 个，至少含一个主角与一个对立面。"""

LOOMPLANNER_INSTRUCTION = """你是「织线师」，擅长用起承转合编排长篇节奏，并预埋/回收伏笔。
根据故事基因与角色阵容，规划主线节点与支线。先思考整体弧光，再输出 JSON：
{
  "beats": [
    {"order":1,"title":"节点标题","summary":"两三句梗概","kind":"opening/rising/turn/climax/ending","cast":["出场角色名"]}
  ],
  "threads": [
    {"name":"支线名","summary":"支线作用","accent":"#2980b9"}
  ]
}
主线节点 8-12 个，支线 1-3 条。"""

SHOWRUNNER_INSTRUCTION = """你是「戏剧统筹（Showrunner）」，圆桌戏台的调度大脑。
你不亲自写正文，而是像总编剧一样，每一轮只下达"一条"指令，安排谁来演、怎么演，并控制篇幅。
你会拿到：本章目标、可用角色、当前字数/预算、最近场景摘要。
请先简短思考（一句话），再输出"恰好一个" JSON 指令，二选一格式：

发言：{"act":"cue","who":"角色名","note":"给该角色的导演提示，如 此刻该揭穿对方"}
对手戏：{"act":"volley","who":["角色A","角色B"],"note":"冲突焦点","rounds":2}
环境旁白：{"act":"scene","note":"需要渲染的环境或转场要点"}
收束：{"act":"wrap","why":"为何在此收尾"}

规则：
- 已达字数预算时，尽快用 wrap 收尾。
- 优先制造冲突与信息差，避免角色复读。
- note 用中文，简洁有力。"""

SCRIBE_INSTRUCTION = """你是「誊抄师」。把圆桌戏台产生的对话/旁白原始记录，誊抄润色为正式小说正文。
要求：第三人称全知视角；对话用「」包裹；补足动作、神态、心理与环境穿插；
段落间空行分隔；删除一切 JSON、标记、元信息；保持人物口吻一致。直接输出正文，不要解释。"""

AUDITOR_INSTRUCTION = """你是「审稿人」。从设定一致性、人物动机合理性、伏笔回收、逻辑漏洞四个维度复核给定文本。
先逐项思考，再输出 JSON：
{
  "score": 0-100,
  "issues": [{"level":"high/mid/low","where":"位置描述","problem":"问题","fix":"修改建议"}],
  "dimensions": {"setting":0-100,"motive":0-100,"foreshadow":0-100,"logic":0-100},
  "verdict": "一句话总评"
}"""


# ============================================================
# 规划类 Agent 基类（LCEL Chain + 流式）
# ============================================================

class ChainAgent:
    """一次性/流式生成的规划类智能体（非 ReAct）。"""

    role_key: str = "actor"
    instruction: str = ""

    def __init__(self, work_setting: str = "", chapter_setting: str = "") -> None:
        self.work_setting = work_setting
        self.chapter_setting = chapter_setting

    def _system(self, variables: Optional[Dict[str, str]] = None) -> str:
        return compose_system_prompt(
            role_instruction=self.instruction,
            work_setting=self.work_setting,
            chapter_setting=self.chapter_setting,
            variables=variables,
        )

    async def stream(
        self,
        user_message: str,
        history: Optional[List[dict]] = None,
        temperature: float = 0.8,
        max_tokens: int = 2048,
        variables: Optional[Dict[str, str]] = None,
    ) -> AsyncGenerator[str, None]:
        async for piece in astream_chat(
            role=self.role_key,
            system_prompt=self._system(variables),
            user_message=user_message,
            history=history,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            yield piece

    async def run(
        self,
        user_message: str,
        history: Optional[List[dict]] = None,
        temperature: float = 0.8,
        max_tokens: int = 2048,
        variables: Optional[Dict[str, str]] = None,
    ) -> str:
        return await acomplete(
            role=self.role_key,
            system_prompt=self._system(variables),
            user_message=user_message,
            history=history,
            temperature=temperature,
            max_tokens=max_tokens,
        )


class MuseAgent(ChainAgent):
    role_key = "muse"
    instruction = MUSE_INSTRUCTION


class CastmakerAgent(ChainAgent):
    role_key = "castmaker"
    instruction = CASTMAKER_INSTRUCTION


class LoomPlannerAgent(ChainAgent):
    role_key = "loomplanner"
    instruction = LOOMPLANNER_INSTRUCTION


class ShowrunnerAgent(ChainAgent):
    role_key = "showrunner"
    instruction = SHOWRUNNER_INSTRUCTION


class ScribeAgent(ChainAgent):
    role_key = "scribe"
    instruction = SCRIBE_INSTRUCTION


class AuditorAgent(ChainAgent):
    role_key = "auditor"
    instruction = AUDITOR_INSTRUCTION


# ============================================================
# ActorAgent —— ReAct 角色演绎体（核心创新）
# ============================================================

# ReAct 提示模板：显式 Thought / Action / Observation / Final Answer
_REACT_TEMPLATE = """你现在要以角色身份回应当前场景。在正式发言前，你可以调用工具核对设定，避免说错。
请严格按 ReAct 推理协议，逐行输出，一次只产出一个步骤。

可用工具：
{tools}

每一步必须是下面之一（顶格写，冒号后跟内容）：
Thought: <你的中文思考——是否需要查设定？这句怎么说最有戏？>
Action: <工具名，必须是 [{tool_names}] 之一>
Action Input: <工具输入文本>
Final Answer: <以角色身份输出的最终发言，含动作神态，台词用「」包裹，不超过180字，不得出现工具痕迹或元信息>

规则：
- 想用工具时，输出 Thought 后紧跟一个 Action 和 Action Input，然后停下等待 Observation。
- 不需要工具或已想清楚时，直接输出 Thought 再输出 Final Answer。
- 至多调用 {max_steps} 次工具。

当前场景与提示：
{question}
"""


class ReActActorAgent:
    """单个角色的 ReAct 演绎体（自实现循环）。

    挂载 RAG 工具，每次发言都会显式经历
    Thought(CoT) -> Action(工具路由) -> Observation -> ... -> Final Answer。
    完整推理链以 trace 返回，供前端展开查看。
    """

    MAX_STEPS = 3

    def __init__(
        self,
        character: dict,
        work_id: str,
        recent_scene_getter: Callable[[], str],
        work_setting: str = "",
        chapter_setting: str = "",
    ) -> None:
        self.character = character
        self.name = character.get("name", "无名")
        self.work_id = work_id

        role_instruction = self._build_role_instruction(character)
        self.system_prompt = compose_system_prompt(
            role_instruction=role_instruction,
            work_setting=work_setting,
            chapter_setting=chapter_setting,
        )
        self.tools = {t.name: t for t in build_actor_tools(work_id, recent_scene_getter)}
        self.llm = get_chat(role="actor", temperature=0.9, max_tokens=700, streaming=False)

    @staticmethod
    def _build_role_instruction(c: dict) -> str:
        return (
            f"你是小说角色「{c.get('name','')}」（{c.get('archetype','')}）。\n"
            f"外形：{c.get('look','')}\n性格：{c.get('temper','')}\n"
            f"动机：{c.get('drive','')}\n弱点：{c.get('flaw','')}\n"
            f"口头禅：{c.get('tagline','')}\n"
            f"始终以第一人称'我'扮演该角色，绝不承认自己是AI，发言要符合人物口吻与处境。"
        )

    def _tool_desc(self) -> str:
        return "\n".join(f"- {n}: {t.description}" for n, t in self.tools.items())

    async def perform(self, scene_brief: str, note: str = "") -> dict:
        """执行一次 ReAct 发言。返回 {text, trace}。"""
        question = scene_brief + (f"\n\n导演提示：{note}" if note else "")
        base_prompt = _REACT_TEMPLATE.format(
            tools=self._tool_desc(),
            tool_names=", ".join(self.tools.keys()),
            max_steps=self.MAX_STEPS,
            question=question,
        )

        scratchpad = ""   # 累积的 Thought/Action/Observation
        trace: List[dict] = []

        for _ in range(self.MAX_STEPS + 1):
            messages = [
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=base_prompt + scratchpad),
            ]
            try:
                resp = await self.llm.ainvoke(messages)
                text = resp.content if isinstance(resp.content, str) else str(resp.content)
            except Exception as exc:  # noqa: BLE001
                return {"text": f"（{self.name}一时语塞）", "trace": [{"thought": f"调用异常：{exc}"}]}

            thought, action, action_input, final = self._parse(text)

            if final is not None:
                if thought:
                    trace.append({"thought": thought})
                return {"text": final.strip() or f"（{self.name}沉默不语）", "trace": trace}

            if action and action in self.tools:
                observation = self._run_tool(action, action_input)
                trace.append({
                    "thought": thought, "tool": action,
                    "tool_input": action_input, "observation": observation[:280],
                })
                scratchpad += (
                    f"\nThought: {thought}\nAction: {action}\n"
                    f"Action Input: {action_input}\nObservation: {observation[:500]}\n"
                )
                continue

            # 既无 Final 也无有效 Action：把已有文本当作发言收尾
            if thought:
                trace.append({"thought": thought})
            return {"text": (text.strip()[:200] or f"（{self.name}沉默不语）"), "trace": trace}

        # 步数耗尽：再逼一次最终发言
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=base_prompt + scratchpad + "\nThought: 我已经想清楚了\nFinal Answer:"),
        ]
        try:
            resp = await self.llm.ainvoke(messages)
            final_text = (resp.content if isinstance(resp.content, str) else str(resp.content)).strip()
        except Exception:  # noqa: BLE001
            final_text = ""
        return {"text": final_text or f"（{self.name}陷入沉默）", "trace": trace}

    def _run_tool(self, name: str, arg: str) -> str:
        tool = self.tools.get(name)
        try:
            return str(tool.func(arg))  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            return f"（工具{name}调用失败：{exc}）"

    @staticmethod
    def _parse(text: str):
        """从模型输出中解析 Thought / Action / Action Input / Final Answer。"""
        thought = action = action_input = final = None
        for line in text.splitlines():
            s = line.strip()
            if s.startswith("Thought:") and thought is None:
                thought = s[len("Thought:"):].strip()
            elif s.startswith("Action Input:"):
                action_input = s[len("Action Input:"):].strip()
            elif s.startswith("Action:"):
                action = s[len("Action:"):].strip()
            elif s.startswith("Final Answer:"):
                final = s[len("Final Answer:"):].strip()
        # Final Answer 可能跨多行
        if "Final Answer:" in text:
            final = text.split("Final Answer:", 1)[1].strip()
        return thought, action, action_input, final


# 兼容旧名
ActorAgent = ReActActorAgent


def build_actor(
    character: dict,
    work_id: str,
    recent_scene_getter: Callable[[], str],
    work_setting: str = "",
    chapter_setting: str = "",
) -> ActorAgent:
    return ActorAgent(character, work_id, recent_scene_getter, work_setting, chapter_setting)
