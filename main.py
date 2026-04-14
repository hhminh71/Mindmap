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
    text = ""
    try:
        ext = file.filename.split('.')[-1].lower()
        if ext == "txt": text = content.decode('utf-8')
        elif ext == "pdf":
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                text = "\n".join([page.extract_text() or "" for page in pdf.pages])
        elif ext in ["doc", "docx"]:
            doc = docx.Document(io.BytesIO(content))
            text = "\n".join([p.text for p in doc.paragraphs])
        return text
    except: return ""

@app.post("/api/generate")
async def generate_mindmap(file: UploadFile = File(...)):
    text_data = await extract_text(file)
    if not text_data.strip(): return {"error": "File không có nội dung chữ."}

    # DANH SÁCH CÁC CỬA NGÕ (ĐỀ PHÒNG GOOGLE KHÓA)
    # Chúng ta thử v1 trước (cho Paid Tier), sau đó mới thử v1beta
    endpoints = [
        "https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent",
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent",
        "https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent"
    ]

    payload = {
        "contents": [{"parts": [{"text": f"Phân tích văn bản này thành Mindmap Markdown chi tiết: \n\n {text_data[:12000]}"}]}]
    }

    last_error = "Không thể kết nối với Google AI"

    for url in endpoints:
        try:
            full_url = f"{url}?key={API_KEY}"
            response = requests.post(full_url, json=payload, timeout=30)
            res_data = response.json()
            
            if response.status_code == 200:
                markdown_out = res_data['candidates'][0]['content']['parts'][0]['text']
                return {"markdown": markdown_out.replace('```markdown', '').replace('```', '')}
            else:
                last_error = res_data.get('error', {}).get('message', f"Lỗi {response.status_code}")
        except Exception as e:
            last_error = str(e)
            continue

    return {"error": f"Tất cả cửa ngõ đều bị từ chối: {last_error}"}

@app.get("/")
async def serve_frontend():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())
