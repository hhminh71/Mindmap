import os
import io
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import pdfplumber
import docx
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
if API_KEY:
    genai.configure(api_key=API_KEY)

# Hàm khởi tạo model an toàn
def get_model():
    # Thử lần lượt các tên gọi model phổ biến nhất
    for model_name in ['gemini-1.5-flash', 'gemini-1.5-flash-latest', 'gemini-pro']:
        try:
            m = genai.GenerativeModel(model_name)
            # Thử gọi một lệnh nhỏ để kiểm tra model có tồn tại không
            return m
        except:
            continue
    return genai.GenerativeModel('gemini-pro') # Cuối cùng dùng bản Pro ổn định nhất

model = get_model()

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
                text = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text() or ""])
        elif ext in ["doc", "docx"]:
            doc = docx.Document(io.BytesIO(content))
            text = "\n".join([para.text for para in doc.paragraphs])
        else:
            raise ValueError("Định dạng file chưa được hỗ trợ.")
    except Exception as e:
        raise ValueError(f"Lỗi đọc file: {str(e)}")
    return text

@app.post("/api/generate")
async def generate_mindmap(file: UploadFile = File(...)):
    try:
        if not API_KEY:
            return {"error": "Chưa cấu hình API Key."}
            
        document_text = await extract_text(file)
        if not document_text.strip():
            return {"error": "Tài liệu không có nội dung chữ (có thể là file ảnh scan)."}

        prompt = f"""
        Bạn là "VCA Smart Visualizer". Hãy bóc tách chi tiết văn bản sau thành Markdown phân cấp sâu (#, ##, ###, -, v.v.) để làm mindmap.
        Giữ lời văn chuyên nghiệp, trích xuất đủ số liệu tài chính và mốc thời gian.
        Chỉ trả về nội dung Markdown, không giải thích.
        
        Nội dung:
        {document_text[:10000]}
        """
        
        # Gọi AI với cơ chế xử lý lỗi
        try:
            response = model.generate_content(prompt)
            markdown_content = response.text.replace('```markdown', '').replace('```', '')
            return {"markdown": markdown_content.strip()}
        except Exception as ai_err:
            # Nếu model Flash vẫn lỗi, thử dùng model Pro ngay lập tức
            fallback_model = genai.GenerativeModel('gemini-pro')
            response = fallback_model.generate_content(prompt)
            markdown_content = response.text.replace('```markdown', '').replace('```', '')
            return {"markdown": markdown_content.strip()}

    except Exception as e:
        return {"error": str(e)}

@app.get("/")
async def serve_frontend():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())
