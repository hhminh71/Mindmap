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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def extract_text(file: UploadFile):
    ext = file.filename.split('.')[-1].lower()
    content = await file.read()
    text = ""
    try:
        if ext == "txt":
            text = content.decode('utf-8')
        elif ext == "pdf":
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                text = "\n".join([page.extract_text() or "" for page in pdf.pages])
        elif ext in ["doc", "docx"]:
            doc = docx.Document(io.BytesIO(content))
            text = "\n".join([para.text for para in doc.paragraphs])
        return text
    except Exception:
        return ""

@app.post("/api/generate")
async def generate_mindmap(file: UploadFile = File(...)):
    try:
        text_data = await extract_text(file)
        if not text_data.strip():
            return {"error": "Không trích xuất được văn bản từ file."}

        # --- THAY ĐỔI QUAN TRỌNG: DÙNG V1 THAY VÌ V1BETA ---
        # Thử model Flash trên bản v1 chính thức
        url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={API_KEY}"
        
        payload = {
            "contents": [{
                "parts": [{
                    "text": f"Bạn là VCA Smart Visualizer. Phân tích văn bản sau thành Markdown mindmap chi tiết (#, ##, -), trích xuất đủ số liệu tài chính: \n\n {text_data[:15000]}"
                }]
            }]
        }

        response = requests.post(url, json=payload)
        res_data = response.json()

        # Nếu v1 vẫn báo lỗi, tự động thử sang bản gemini-pro (vốn cực kỳ ổn định)
        if response.status_code != 200:
            url_fallback = f"https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={API_KEY}"
            response = requests.post(url_fallback, json=payload)
            res_data = response.json()

        if response.status_code != 200:
            return {"error": f"Lỗi Google: {res_data.get('error', {}).get('message', '404 Not Found')}"}

        markdown_out = res_data['candidates'][0]['content']['parts'][0]['text']
        return {"markdown": markdown_out.replace('```markdown', '').replace('```', '')}
        
    except Exception as e:
        return {"error": f"Lỗi hệ thống: {str(e)}"}

@app.get("/")
async def serve_frontend():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())
