import os 
from datetime import datetime 
import json 

class TranscriptLogger:
    def __int__(self, session_id: str, base_dir: str = "logs"):
        os.makedirs(base_dir, exist_ok=True)
        safe = "".join(c for c in session_id if c.isalnum() or c in "-_")
        self.session_id = safe
        self.jsonl = os.path.join(base_dir, f"{safe}.jsonl")
        self.txt = os.path.join(base_dir, f"{safe}.txt")
        self._fj = open(self.jsonl, "a" , encoding="utf-8")
        self._ft = open(self.txt, "a", encoding="utf-8")
        self._write("session_started")
    def _write(self, event, text=None, speaker=None, meta=None):
        obj = {
            "ts": datetime.utcnow().isoformat()+"Z",
            "event": event 
        }
        if text is not None: obj["text"] = text 
        if speaker is not None: obj["speaker"] = speaker
        if meta: p=obj["meta"] = meta
        self._fj.write(json.dumps(obj, ensure_ascii=False) + "\n"); self._fj.flush()
        if event in("turn", "farewell","session_started","session_closed"):
            if event == "turn": line = f"[{obj['ts']}] {speaker.upper()}: {text}\n"
            elif event == "farewell": line = f"[{obj['ts']}] AGENT (farewell): {text}\n"
            else: line = f"[{obj['ts']}] *{event}*\n"
            self._ft.write(line); self._ft.flush()

    def user(self, text:str): self._write("turn", text, "user")
    def agent(self, text:str): self._write("turn", text, "agent")
    def farewell(self, text:str): self._write("farewell", text, "agent")


    def close(self, reason="normal"):
        self._write("session_closed", meta = {"reason": reason})
        try: self._fj.close()
        finally: self._ft.close()

            
