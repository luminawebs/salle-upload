import os
import json
import asyncio
import traceback
from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import JSONResponse
from core.data_parser import parse_docx_to_html
from core.document_reviewer import review_document
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import subprocess
import shutil
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# A simple event queue to push logs to SSE
log_queue = asyncio.Queue()

# Ensure assets directory exists
os.makedirs("assets", exist_ok=True)

@app.get("/api/settings")
def get_settings():
    # Read settings from .env file or return defaults
    settings = {}
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    settings[k] = v
    return settings

@app.post("/api/settings")
async def save_settings(request: Request):
    new_settings = await request.json()
    
    settings = {}
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    settings[k] = v
                    
    settings.update(new_settings)
    
    with open(".env", "w") as f:
        for k, v in settings.items():
            f.write(f"{k}={v}\n")
    return {"status": "success"}

@app.post("/api/upload")
async def upload_doc(file: UploadFile = File(...), course_id: str = Form(...)):
    # Create the course-specific directory
    course_dir = os.path.join("assets", course_id)
    os.makedirs(course_dir, exist_ok=True)
    
    # Clean up old generated files to ensure we don't use data from past uploads
    folders_to_clean = ["imgs", "actividades", "material", "introduccion", "unidades_intro"]
    for folder_name in folders_to_clean:
        folder_path = os.path.join(course_dir, folder_name)
        if os.path.exists(folder_path):
            try:
                shutil.rmtree(folder_path)
            except Exception as e:
                print(f"Error removing {folder_path}: {e}")
                
    # Clean up the raw extracted html
    raw_html_path = os.path.join(course_dir, "raw_docx_extracted.html")
    if os.path.exists(raw_html_path):
        try:
            os.remove(raw_html_path)
        except Exception as e:
            print(f"Error removing {raw_html_path}: {e}")
    
    # Save the file as course_id.docx which main.py expects
    file_location = os.path.join(course_dir, f"{course_id}.docx")
    with open(file_location, "wb+") as file_object:
        file_object.write(file.file.read())
    return {"info": f"archivo '{file.filename}' guardado exitosamente"}

@app.post("/api/review")
async def api_review(file: UploadFile = File(...)):
    if not file.filename.endswith('.docx'):
        return JSONResponse(status_code=400, content={"error": "El archivo debe ser un .docx."})

    TEMP_COURSE_ID = "temp_upload"
    TEMP_ASSETS_DIR = os.path.join("assets", TEMP_COURSE_ID)

    if os.path.exists(TEMP_ASSETS_DIR):
        try:
            shutil.rmtree(TEMP_ASSETS_DIR)
        except Exception:
            pass
    os.makedirs(TEMP_ASSETS_DIR, exist_ok=True)

    try:
        docx_path = os.path.join(TEMP_ASSETS_DIR, f"{TEMP_COURSE_ID}.docx")
        with open(docx_path, "wb+") as file_object:
            file_object.write(await file.read())

        # 1. Parse DOCX to HTML
        html_content = parse_docx_to_html(docx_path, TEMP_COURSE_ID)
        if not html_content:
            return JSONResponse(status_code=500, content={"error": "Fallo al extraer el contenido del documento."})
            
        output_html_path = os.path.join(TEMP_ASSETS_DIR, "raw_docx_extracted.html")
        with open(output_html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        # 2. Review the document
        report = review_document(
            course_id=TEMP_COURSE_ID,
            generate_json=False,
            generate_text=False
        )

        return report

    except Exception as e:
        return JSONResponse(status_code=500, content={
            "error": f"Error interno: {str(e)}",
            "trace": traceback.format_exc()
        })
        
    finally:
        # Cleanup temporary files
        try:
            if os.path.exists(TEMP_ASSETS_DIR):
                shutil.rmtree(TEMP_ASSETS_DIR)
        except Exception:
            pass

@app.get("/api/logs")
async def stream_logs():
    async def event_generator():
        while True:
            log_line = await log_queue.get()
            yield f"data: {json.dumps({'message': log_line})}\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/api/run")
async def run_automation():
    # Clear the queue
    while not log_queue.empty():
        await log_queue.get()

    async def run_script():
        await log_queue.put("[Sistema] Iniciando la tarea de automatización...")
        process = await asyncio.create_subprocess_exec(
            "python", "main.py",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )
        
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            await log_queue.put(line.decode(errors='replace').strip())
        
        await process.wait()
        await log_queue.put(f"[Sistema] La tarea finalizó con código de salida {process.returncode}")
        
        # Cleanup uploaded assets
        await log_queue.put("[Sistema] Limpiando los archivos temporales...")
        
        # Read the active course IDs from .env to clean up their docx files
        courses = []
        if os.path.exists(".env"):
            with open(".env", "r") as f:
                for line in f:
                    if line.startswith("COURSES_TO_PROCESS="):
                        courses = [c.strip() for c in line.split("=", 1)[1].split(",") if c.strip()]
        
        for cid in courses:
            target_docx = os.path.join("assets", cid, f"{cid}.docx")
            if os.path.exists(target_docx):
                os.remove(target_docx)
                
        # Also clean up any loose files in the root assets dir just in case
        for filename in os.listdir("assets"):
            file_path = os.path.join("assets", filename)
            if os.path.isfile(file_path) and (filename.endswith(".docx") or filename.endswith(".html")):
                os.remove(file_path)
                
        await log_queue.put("[Sistema] Limpieza completada con éxito.")
        
    asyncio.create_task(run_script())
    return {"status": "started"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
