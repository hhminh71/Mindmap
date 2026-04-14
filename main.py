import os
import io
import logging
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import pdfplumber
import docx
import google.generativeai as genai
from dotenv import load_dotenv

# Bật nhật ký để theo dõi lỗi trên Render Logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

if API_KEY:
    try:
        genai.configure(api_key=API_KEY)
        # Kiểm tra xem API Key có nhìn thấy model nào không
        logger.info("Đang kiểm tra danh sách model khả dụng...")
        for m in genai.list_models():
            logger.info(f"Model khả dụng: {m.name}")
    except Exception as e:
        logger.error(f"Lỗi cấu hình API: {str(e)}")

# Khởi tạo model mặc định
model = genai.GenerativeModel('gemini-1.5-flash')

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
        logger.error(f"Lỗi đọc file: {str(e)}")
        return ""

@app.post("/api/generate")
async def generate_mindmap(file: UploadFile = File(...)):
    try:
        text_data = await extract_text(file)
        if not text_data.strip():
            return {"error": "Không trích xuất được chữ. Vui lòng thử file khác."}

        prompt = f"Phân tích văn bản sau thành Markdown mindmap chi tiết: \n\n {text_data[:15000]}"
        
        # Gọi AI
        response = model.generate_content(prompt)
        return {"markdown": response.text.replace('```markdown', '').replace('```', '')}
        
    except Exception as e:
        logger.error(f"Lỗi xử lý AI: {str(e)}")
        return {"error": str(e)}

@app.get("/")
async def serve_frontend():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())
