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
    try:
        content = await file.read()
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
    if not text_data.strip(): return {"error": "Không đọc được file."}

    # BƯỚC 1: HỎI GOOGLE XEM TÔI ĐƯỢC DÙNG MODEL NÀO?
    list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEY}"
    try:
        models_res = requests.get(list_url).json()
        # Tìm model Flash hoặc Pro trong danh sách Google trả về
        available_models = [m['name'] for m in models_res.get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
        
        if not available_models:
            return {"error": "API Key của bạn không có quyền truy cập vào bất kỳ model nào. Hãy kiểm tra lại Billing."}

        # Ưu tiên Flash, không thì lấy cái đầu tiên trong danh sách
        chosen_model = next((m for m in available_models if "flash" in m), available_models[0])
        
    except Exception as e:
        return {"error": f"Lỗi kiểm tra quyền: {str(e)}"}

    # BƯỚC 2: GỌI ĐÚNG MODEL ĐÃ TÌM THẤY
    gen_url = f"https://generativelanguage.googleapis.com/v1beta/{chosen_model}:generateContent?key={API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": f"Phân tích văn bản sau thành Mindmap Markdown: \n\n {text_data[:15000]}"}]}]
    }

    try:
        response = requests.post(gen_url, json=payload, timeout=60)
        res_data = response.json()
        if response.status_code == 200:
            markdown_out = res_data['candidates'][0]['content']['parts'][0]['text']
            return {"markdown": markdown_out}
        else:
            return {"error": f"Google từ chối ({chosen_model}): {res_data.get('error', {}).get('message')}"}
    except Exception as e:
        return {"error": str(e)}

@app.get("/")
async def serve_frontend():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())
