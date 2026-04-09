import copy
import json
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from groq import Groq
from config import GROQ_API_KEY
from brain.tool_schemas import TOOL_SCHEMAS

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = Groq(api_key=GROQ_API_KEY)
    return _client


def _is_arabic(text: str) -> bool:
    return any('\u0600' <= c <= '\u06FF' for c in text)


_MODEL_ARABIC  = "llama-3.3-70b-versatile"
_MODEL_DEFAULT = "llama-3.3-70b-versatile"

MAX_STEPS = 5


SYSTEM_PROMPT = """أنت أريا — مساعد صوتي لمصطفى، مهندس برمجيات ومصمم.

━━ قاعدة اللغة (مهمة جداً) ━━
جاوب بنفس اللغة ديال المستخدم:
• إنجليزية → إنجليزية
• دارجة مغربية → دارجة مغربية بالعربية فقط (بدون حروف لاتينية أبداً)
• عربية فصحى → عربية فصحى
• فرنسية → فرنسية

━━ كيفاش تكتب الدارجة المغربية ━━
خاصك تكتب الدارجة بشكل طبيعي كما يتكلمها المغاربة. هاك أمثلة:

سؤال: "أش قادر تدير؟"
جواب صح: "قادر نعاونك تفتح البرامج، تبحث فالنت، تاخد صورة ديال الشاشة، تحكم في الصوت، أو تفتح مشروع ديالك. قول لي أش بغيتي!"

سؤال: "واش سمعتني؟"
جواب صح: "إيه، سمعتك مزيان! أش بغيتي؟"

━━ مفردات دارجة مغربية ━━
كمبيوتر / باسي = computer | برنامج / أبليكاسيون = app | فتح = open | سد / قفل = close
بحث = search | صورة ديال الشاشة = screenshot | الكليبوورد = clipboard | الصوت = volume
مشروع = project | فولدر = folder | سيت / موقع = website | لينك = URL
قادر / قادرة = can | بغيتي = do you want | دير لي = do for me | واش = question marker
مزيان = good | واخا = okay | ماكاينش = not found/doesn't exist | بزاف = a lot
غادي = going to | كيفاش = how | أشنو / أش = what | علاش = why | فين = where
ولاش / ماشي = no/not | إيه / آه = yes | هاو = here it is | عاود = repeat/again

━━ قدراتك ━━
عندك أدوات تقدر تفتح/تسد برامج، تبحث فالنت، تفتح مواقع، تشغل يوتيوب وسبوتيفاي،
تقرأ الشاشة وتاخد صورة، تدير تذكيرات وتايمر تركيز، تحكم في الصوت، تبدل الصوت.
إذا كان المستخدم طلب شي معقد — خطوات متعددة — استخدم الأدوات بالترتيب لتحقيق الهدف.
بعد ما تخلص من كل الخطوات، جاوب بجملة قصيرة تلخص اللي دارتي.

إذا ما كاين شي أداة مناسبة: جاوب بدارجة طبيعية قصيرة (جملة أو جملتين فقط)."""


conversation_history = []


def reset_conversation() -> None:
    global conversation_history
    conversation_history = []


def _spotify_context() -> str:
    try:
        from user_config import get_config
        entries = get_config().spotify_playlists
        if not entries:
            return ""
        names = ", ".join(f'"{p["name"]}"' for p in entries)
        return f"\n━━ Spotify المحفوظة ━━\nاستخدم play_spotify دائماً لهاد الأسماء: {names}\n"
    except Exception:
        return ""


def _build_schemas() -> list:
    """Return tool schemas, dynamically annotating play_spotify with saved playlist names."""
    try:
        from user_config import get_config
        entries = get_config().spotify_playlists
        if not entries:
            return TOOL_SCHEMAS
        names = ", ".join(f'"{p["name"]}"' for p in entries)
        patched = []
        for schema in TOOL_SCHEMAS:
            if schema["function"]["name"] == "play_spotify":
                s = copy.deepcopy(schema)
                s["function"]["description"] += f" Saved playlists: {names}."
                patched.append(s)
            else:
                patched.append(schema)
        return patched
    except Exception:
        return TOOL_SCHEMAS


def _safe_window(history: list, n: int) -> list:
    """Slice last n messages, trimming orphaned tool messages at the start."""
    window = history[-n:]
    while window and window[0]["role"] == "tool":
        window = window[1:]
    return window


def _call_llm(messages: list, model: str) -> object:
    for attempt in range(3):
        try:
            return _get_client().chat.completions.create(
                model=model,
                messages=messages,
                tools=_build_schemas(),
                tool_choice="auto",
                temperature=0.15,
                max_tokens=1000,
            )
        except Exception as e:
            err = str(e)
            if attempt < 2 and ("503" in err or "429" in err or "unavailable" in err.lower()):
                print(f"⚠️  Groq busy, retrying ({attempt+1}/3)…")
                time.sleep(2)
            else:
                raise
    raise RuntimeError("Groq unavailable after 3 attempts")


def _status_phrase(tool_name: str, params: dict, arabic: bool) -> str:
    phrases_en = {
        "open_app":               lambda p: f"Opening {p.get('name', 'app')}...",
        "close_app":              lambda p: f"Closing {p.get('name', 'app')}...",
        "search_web":             lambda p: f"Searching for {p.get('query', '')}...",
        "open_url":               lambda p: f"Opening {p.get('url', 'the page')}...",
        "play_youtube":           lambda p: f"Playing {p.get('query', '')} on YouTube...",
        "play_spotify":           lambda p: f"Playing {p.get('query', '')} on Spotify...",
        "read_screen":            lambda p: "Reading the screen...",
        "take_screenshot":        lambda p: "Taking a screenshot...",
        "read_clipboard":         lambda p: "Reading clipboard...",
        "run_terminal":           lambda p: "Running command...",
        "open_project":           lambda p: f"Opening project {p.get('name', '')}...",
        "control_volume":         lambda p: f"Volume {p.get('action', '')}...",
        "start_focus_timer":      lambda p: f"Starting {p.get('minutes', 25)} minute timer...",
        "remind_me":              lambda p: "Setting reminder...",
        "create_design_project":  lambda p: f"Creating project {p.get('name', '')}...",
        "open_design_folder":     lambda p: "Opening design folder...",
        "move_exports_to_desktop":lambda p: "Moving exports to desktop...",
        "switch_voice":           lambda p: f"Switching to {p.get('language', '')} voice...",
    }
    phrases_ar = {
        "open_app":        lambda p: f"كنفتح {p.get('name', '')}...",
        "close_app":       lambda p: f"كنسد {p.get('name', '')}...",
        "read_screen":     lambda p: "كنقرأ الشاشة...",
        "take_screenshot": lambda p: "كناخد صورة...",
        "search_web":      lambda p: f"كنبحث على {p.get('query', '')}...",
        "open_url":        lambda p: f"كنفتح {p.get('url', 'الصفحة')}...",
        "run_terminal":    lambda p: "كنشغل الأمر...",
    }
    table = phrases_ar if arabic else phrases_en
    fn = table.get(tool_name)
    if fn:
        return fn(params)
    return f"Running {tool_name}..." if not arabic else "كنكمل..."


def ask_gemini(
    user_input: str,
    tool_executor,      # callable: (action: str, params: dict) -> str
    speak_fn=None,      # optional callable: (text: str) -> None for intermediate status
) -> str:
    """
    Run the agentic loop and return the final response text for TTS.

    The loop: LLM decides a tool → execute it → feed result back → LLM decides next step
    → ... → LLM gives final spoken answer.

    conversation_history is mutated in-place so context carries across turns.
    """
    global conversation_history

    conversation_history.append({"role": "user", "content": user_input})

    arabic = _is_arabic(user_input)
    model  = _MODEL_ARABIC if arabic else _MODEL_DEFAULT

    system   = SYSTEM_PROMPT + _spotify_context()
    messages = [{"role": "system", "content": system}] + _safe_window(conversation_history, 20)

    for step in range(MAX_STEPS):
        try:
            response = _call_llm(messages, model)
        except Exception as e:
            return f"I had trouble reaching the AI: {e}"

        choice        = response.choices[0]
        finish_reason = choice.finish_reason
        msg           = choice.message

        # ── Model wants to call one or more tools ─────────────────────────────
        if finish_reason == "tool_calls" and msg.tool_calls:

            # Store assistant message with tool_calls as plain dicts (not SDK objects)
            assistant_msg = {
                "role": "assistant",
                "content": msg.content,   # often None — preserve as-is
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ],
            }
            messages.append(assistant_msg)
            conversation_history.append(assistant_msg)

            # Execute each tool and feed results back
            for tc in msg.tool_calls:
                tool_name = tc.function.name
                raw_args  = tc.function.arguments or "{}"
                try:
                    params = json.loads(raw_args)
                except json.JSONDecodeError:
                    params = {}

                if speak_fn:
                    speak_fn(_status_phrase(tool_name, params, arabic))

                try:
                    tool_result = tool_executor(tool_name, params)
                except Exception as exc:
                    tool_result = f"Tool '{tool_name}' failed: {exc}"

                print(f"[agentic] step={step+1} tool={tool_name} → {str(tool_result)[:100]}")

                tool_msg = {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": str(tool_result),
                }
                messages.append(tool_msg)
                conversation_history.append(tool_msg)

            # Loop back — let LLM decide the next step

        # ── Model gives a final text response ─────────────────────────────────
        elif finish_reason in ("stop", "length", None):
            final_text = (msg.content or "").strip()
            if not final_text:
                final_text = "Done." if not arabic else "خلصت."

            conversation_history.append({"role": "assistant", "content": final_text})
            return final_text

        else:
            break

    # Safety valve: loop exhausted without a stop response
    fallback = "Task complete." if not arabic else "خلصت المهمة."
    conversation_history.append({"role": "assistant", "content": fallback})
    return fallback
