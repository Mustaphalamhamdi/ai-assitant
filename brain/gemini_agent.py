import json
import re
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from groq import Groq
from config import GROQ_API_KEY

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = Groq(api_key=GROQ_API_KEY)
    return _client


def _is_arabic(text: str) -> bool:
    return any('\u0600' <= c <= '\u06FF' for c in text)


# Use the large model for Arabic/Darija (8b struggles with dialect),
# fast model for English/French commands.
_MODEL_ARABIC  = "llama-3.3-70b-versatile"
_MODEL_DEFAULT = "llama-3.1-8b-instant"


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
جواب غلط: "قدر تفتح تطبيقات زي الحاسوب، فولدر، سيت" ← هذا ليس دارجة حقيقية

سؤال: "فتح الكروم"
جواب صح: {"action":"open_app","params":{"name":"chrome"}}

سؤال: "واش سمعتني؟"
جواب صح: "إيه، سمعتك مزيان! أش بغيتي؟"

سؤال: "عطيني وقت ديال تركيز"
جواب صح: {"action":"start_focus_timer","params":{"minutes":25}}

━━ مفردات دارجة مغربية ━━
كمبيوتر / باسي = computer | برنامج / أبليكاسيون = app | فتح = open | سد / قفل = close
بحث = search | صورة ديال الشاشة = screenshot | الكليبوورد = clipboard | الصوت = volume
مشروع = project | فولدر = folder | سيت / موقع = website | لينك = URL
قادر / قادرة = can | بغيتي = do you want | دير لي = do for me | واش = question marker
مزيان = good | واخا = okay | ماكاينش = not found/doesn't exist | بزاف = a lot
غادي = going to | كيفاش = how | أشنو / أش = what | علاش = why | فين = where
ولاش / ماشي = no/not | إيه / آه = yes | هاو = here it is | عاود = repeat/again

━━ الأدوات (tools) ━━
عند الحاجة لأداة، جاوب بـ JSON فقط بدون كلام:
{"action": "tool_name", "params": {"key": "value"}}
أكثر من أداة → كل أداة في سطر.

- open_app(name): فتح برنامج — "vscode","chrome","figma","illustrator","spotify","terminal"
- close_app(name): سد برنامج
- open_project(name): فتح مشروع في VS Code — فقط إذا سمّى المشروع
- run_terminal(command): تشغيل أمر في التيرمينال — ماشي للمواقع أو البرامج
- create_design_project(name): إنشاء فولدر ديزاين
- open_design_folder(): فتح فولدر الديزاين
- search_web(query): بحث في غوغل
- open_url(url, browser): فتح موقع، browser اختياري: "chrome"/"firefox"
- play_youtube(query): بحث على يوتيوب وتشغيل أول نتيجة تلقائياً — استخدم هذا دائماً لتشغيل موسيقى أو فيديوهات
- play_spotify(query): فتح سبوتيفاي وتشغيل بلايليست أو أغنية بالاسم — استخدم إذا قال المستخدم "شغل سبوتيفاي" أو "شغل بلايليستي"
- read_screen(question): شوف شنو كاين فالشاشة وجاوب على السؤال — استخدم إذا المستخدم قال "اللي فالشاشة" أو "الأول" بدون ما يحدد
- take_screenshot(): صورة ديال الشاشة
- read_clipboard(): قراءة الكليبوورد
- start_focus_timer(minutes): تايمر تركيز
- remind_me(minutes, message): تذكير صوتي
- control_volume(action): "up"/"down"/"mute"
- switch_voice(language): "arabic"/"english"/"japanese"/"default"

━━ أمثلة ━━
"open VS Code" → {"action":"open_app","params":{"name":"vscode"}}
"فتح الكروم" → {"action":"open_app","params":{"name":"chrome"}}
"افتح فيسبوك فالكروم" → {"action":"open_url","params":{"url":"https://facebook.com","browser":"chrome"}}
"play moroccan rap on youtube" → {"action":"play_youtube","params":{"query":"moroccan rap music"}}
"play my favourites on spotify" / "شغل بلايليست المفضلة" → {"action":"play_spotify","params":{"query":"favourites"}}
"open spotify and play chill music" → {"action":"play_spotify","params":{"query":"chill"}}
"شغل موسيقى مغربية" → {"action":"play_youtube","params":{"query":"موسيقى مغربية"}}
"play any video" / "شغل أي فيديو" → {"action":"play_youtube","params":{"query":"popular music 2024"}}
"play a video on the home page" / "شغل الأول فالصفحة" → {"action":"play_youtube","params":{"query":"trending music"}}
"play the first video" → {"action":"read_screen","params":{"question":"what is the title of the first video result on screen?"}}
"شنو كاين فالشاشة" → {"action":"read_screen","params":{"question":"describe what is visible on the screen"}}
"حول للعربية" → {"action":"switch_voice","params":{"language":"arabic"}}

إذا ما كاين شي أداة: جاوب بدارجة طبيعية قصيرة (جملة أو جملتين فقط)."""

conversation_history = []


def reset_conversation() -> None:
    """Clear history at the start of each new session."""
    global conversation_history
    conversation_history = []


def _extract_actions(text: str) -> list:
    actions = []
    decoder = json.JSONDecoder()
    pos = 0
    while pos < len(text):
        match = re.search(r'\{', text[pos:])
        if not match:
            break
        start = pos + match.start()
        try:
            obj, offset = decoder.raw_decode(text, start)
            if isinstance(obj, dict) and "action" in obj:
                actions.append(obj)
            pos = start + offset
        except json.JSONDecodeError:
            pos = start + 1
    return actions


def _spotify_context() -> str:
    """Return a prompt snippet listing saved Spotify entries so the brain uses play_spotify."""
    try:
        from user_config import get_config
        entries = get_config().spotify_playlists
        if not entries:
            return ""
        names = ", ".join(f'"{p["name"]}"' for p in entries)
        examples = "\n".join(
            f'"play {p["name"]}" / "شغل {p["name"]}" → {{"action":"play_spotify","params":{{"query":"{p["name"]}"}}}}'
            for p in entries
        )
        return f"\n━━ Spotify المحفوظة (استخدم play_spotify دائماً لهاد الأسماء) ━━\nالأسماء: {names}\n{examples}\n"
    except Exception:
        return ""


def ask_gemini(user_input: str) -> dict:
    conversation_history.append({"role": "user", "content": user_input})

    # Keep only last 10 exchanges to prevent context drift
    recent = conversation_history[-20:]

    # Inject saved Spotify names so brain routes them to play_spotify not play_youtube
    system = SYSTEM_PROMPT + _spotify_context()

    messages = [{"role": "system", "content": system}] + [
        {"role": e["role"], "content": e["content"]} for e in recent
    ]

    # Use stronger model for Arabic/Darija — 8b handles dialect poorly
    model = _MODEL_ARABIC if _is_arabic(user_input) else _MODEL_DEFAULT

    reply = None
    for attempt in range(3):
        try:
            response = _get_client().chat.completions.create(
                model       = model,
                messages    = messages,
                temperature = 0.15,
                max_tokens  = 250,
            )
            reply = response.choices[0].message.content.strip()
            break
        except Exception as e:
            err = str(e)
            if attempt < 2 and ("503" in err or "429" in err or "unavailable" in err.lower()):
                print(f"⚠️  Groq busy, retrying ({attempt+1}/3)…")
                time.sleep(2)
            else:
                return {"type": "speech", "text": f"I had trouble reaching the AI: {e}"}

    if reply is None:
        return {"type": "speech", "text": "The AI is unavailable right now, try again."}

    conversation_history.append({"role": "assistant", "content": reply})

    actions = _extract_actions(reply)
    if len(actions) == 1:
        return {"type": "tool", "action": actions[0]["action"], "params": actions[0].get("params", {})}
    if len(actions) > 1:
        return {"type": "tools", "actions": actions}
    return {"type": "speech", "text": reply}
