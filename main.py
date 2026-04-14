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

# Lấy API Key từ Environment Variables của Render
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
    except Exception as e:
        return ""

@app.post("/api/generate")
async def generate_mindmap(file: UploadFile = File(...)):
    try:
        text_data = await extract_text(file)
        if not text_data.strip():
            return {"error": "Không trích xuất được chữ từ file này."}

        # CẤU HÌNH GỌI API TRỰC TIẾP (Bypass SDK lỗi)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}"
        
        payload = {
            "contents": [{
                "parts": [{
                    "text": f"Bạn là VCA Smart Visualizer. Phân tích văn bản sau thành Markdown mindmap chi tiết (#, ##, -), trích xuất đủ số liệu: \n\n {text_data[:15000]}"
                }]
            }]
        }

        response = requests.post(url, json=payload)
        res_data = response.json()

        if response.status_code != 200:
            return {"error": f"Lỗi từ Google ({response.status_code}): {res_data.get('error', {}).get('message', 'Không rõ lỗi')}"}

        # Lấy nội dung Markdown trả về
        markdown_out = res_data['candidates'][0]['content']['parts'][0]['text']
        return {"markdown": markdown_out.replace('```markdown', '').replace('```', '')}
        
    except Exception as e:
        return {"error": f"Lỗi hệ thống: {str(e)}"}

@app.get("/")
async def serve_frontend():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())
