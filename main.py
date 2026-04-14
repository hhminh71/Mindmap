import os
import io
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import pdfplumber
import docx
import google.generativeai as genai
from dotenv import load_dotenv

# Tải các biến môi trường từ Render
load_dotenv()

# Lấy API Key an toàn
API_KEY = os.getenv("GEMINI_API_KEY")
if API_KEY:
    genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('models/gemini-1.5-flash')

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
                text = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
        elif ext in ["doc", "docx"]:
            doc = docx.Document(io.BytesIO(content))
            text = "\n".join([para.text for para in doc.paragraphs])
        else:
            raise ValueError("Định dạng file chưa được hỗ trợ.")
    except Exception as e:
        raise ValueError(f"Lỗi khi đọc file: {str(e)}")
    return text

@app.post("/api/generate")
async def generate_mindmap(file: UploadFile = File(...)):
    try:
        if not API_KEY:
            return {"error": "Chưa cấu hình API Key trên máy chủ."}
            
        document_text = await extract_text(file)
        if not document_text.strip():
            return {"error": "Không tìm thấy chữ trong tài liệu (Có thể là file ảnh)."}

        prompt = f"""
        Bạn là "VCA Smart Visualizer" - Trợ lý Số hóa của Phòng Tài chính - Kế hoạch (Cảng HKQT Cần Thơ).
        Tuyệt đối KHÔNG tóm tắt ngắn gọn. Hãy bóc tách toàn diện, chi tiết nhất có thể để tạo thành một sơ đồ tư duy đồ sộ, nhiều nhánh.
        BẮT BUỘC trích xuất đầy đủ: số liệu tài chính, mốc thời gian, định mức, phòng ban chịu trách nhiệm.
        Chỉ trả về nội dung Markdown phân cấp sâu (#, ##, ###, -, v.v.). KHÔNG giải thích thêm.
        
        Nội dung văn bản:
        {document_text}
        """
        response = model.generate_content(prompt)
        markdown_content = response.text.replace('```markdown', '').replace('```', '')
        return {"markdown": markdown_content.strip()}
    except Exception as e:
        return {"error": str(e)}

@app.get("/")
async def serve_frontend():
    with open("index.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)
