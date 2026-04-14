import os
import io
import requests
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import pdfplumber
import docx
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

async def extract_text(file: UploadFile):
    content = await file.read()
    try:
        ext = file.filename.split('.')[-1].lower()
        if ext == "txt": return content.decode('utf-8')
        elif ext == "pdf":
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                return "\n".join([page.extract_text() or "" for page in pdf.pages])
        elif ext in ["doc", "docx"]:
            doc = docx.Document(io.BytesIO(content))
            return "\n".join([p.text for p in doc.paragraphs])
        return ""
    except: return ""

@app.post("/api/generate")
async def generate_mindmap(file: UploadFile = File(...)):
    text_data = await extract_text(file)
    if not text_data.strip(): return {"error": "File không có nội dung chữ hoặc định dạng không hỗ trợ."}

    # SỬ DỤNG ENDPOINT V1BETA CHO GEMINI 1.5 FLASH (ỔN ĐỊNH NHẤT CHO PAID TIER)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}"
    
    payload = {
        "contents": [{
            "parts": [{
                "text": f"Bạn là VCA Smart Visualizer. Hãy bóc tách chi tiết văn bản sau thành Markdown mindmap phân cấp sâu (#, ##, ###, -, v.v.) để làm sơ đồ. Giữ nguyên các số liệu tài chính quan trọng. Chỉ trả về Markdown, không giải thích.\n\nNội dung:\n{text_data[:15000]}"
            }]
        }],
        "generationConfig": {
            "temperature": 0.2,
            "topP": 0.8,
            "topK": 40
        }
    }

    try:
        response = requests.post(url, json=payload, timeout=60)
        res_data = response.json()

        if response.status_code == 200:
            markdown_out = res_data['candidates'][0]['content']['parts'][0]['text']
            return {"markdown": markdown_out.replace('```markdown', '').replace('```', '')}
        else:
            # Nếu vẫn lỗi, thử cổng v1 chính thức với cùng model
            url_v1 = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={API_KEY}"
            response_v1 = requests.post(url_v1, json=payload, timeout=60)
            if response_v1.status_code == 200:
                markdown_out = response_v1.json()['candidates'][0]['content']['parts'][0]['text']
                return {"markdown": markdown_out.replace('```markdown', '').replace('```', '')}
            
            error_msg = res_data.get('error', {}).get('message', f"Lỗi {response.status_code}")
            return {"error": f"AI phản hồi lỗi: {error_msg}"}
            
    except Exception as e:
        return {"error": f"Lỗi kết nối: {str(e)}"}

@app.get("/")
async def serve_frontend():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())
