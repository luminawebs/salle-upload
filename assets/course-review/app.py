import os
import shutil
import traceback
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import werkzeug.exceptions
from werkzeug.utils import secure_filename
from core.data_parser import parse_docx_to_html
from core.document_reviewer import review_document

app = Flask(__name__, static_folder='static')
CORS(app)

@app.errorhandler(Exception)
def handle_exception(e):
    if isinstance(e, werkzeug.exceptions.HTTPException):
        return e
    app.logger.error(f"Unhandled Exception: {str(e)}")
    app.logger.error(traceback.format_exc())
    return jsonify({
        "error": "Error interno no controlado",
        "details": str(e),
        "trace": traceback.format_exc()
    }), 500

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

TEMP_COURSE_ID = "temp_upload"
TEMP_ASSETS_DIR = os.path.join(BASE_DIR, "assets", TEMP_COURSE_ID)

# Ensure temp directory exists
os.makedirs(TEMP_ASSETS_DIR, exist_ok=True)

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/api/review', methods=['POST'])
def api_review():
    if 'file' not in request.files:
        return jsonify({"error": "No se encontró el archivo."}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Ningún archivo seleccionado."}), 400
        
    if not file.filename.endswith('.docx'):
        return jsonify({"error": "El archivo debe ser un .docx."}), 400

    # Ensure clean slate for temp directory
    if os.path.exists(TEMP_ASSETS_DIR):
        shutil.rmtree(TEMP_ASSETS_DIR)
    os.makedirs(TEMP_ASSETS_DIR, exist_ok=True)

    try:
        app.logger.info("--- NUEVA SUBIDA DE DOCUMENTO ---")
        app.logger.info(f"File recibido: {file.filename}")
        
        # Save uploaded DOCX
        filename = secure_filename(file.filename)
        docx_path = os.path.join(TEMP_ASSETS_DIR, filename)
        app.logger.info(f"Guardando archivo en: {docx_path}")
        file.save(docx_path)
        app.logger.info("Archivo guardado exitosamente.")
        
        # We need it to be named temp_upload.docx for our parser if it expects <course_id>.docx
        expected_docx_path = os.path.join(TEMP_ASSETS_DIR, f"{TEMP_COURSE_ID}.docx")
        if docx_path != expected_docx_path:
            app.logger.info(f"Renombrando a: {expected_docx_path}")
            os.rename(docx_path, expected_docx_path)

        # 1. Parse DOCX to HTML
        html_content = parse_docx_to_html(expected_docx_path, TEMP_COURSE_ID)
        if not html_content:
            return jsonify({"error": "Fallo al extraer el contenido del documento."}), 500
            
        output_html_path = os.path.join(TEMP_ASSETS_DIR, "raw_docx_extracted.html")
        with open(output_html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        # 2. Review the document
        report = review_document(
            course_id=TEMP_COURSE_ID,
            generate_json=False,  # No need to save files, we return directly
            generate_text=False
        )

        app.logger.info("Documento procesado correctamente. Retornando reporte JSON.")
        return jsonify(report)

    except Exception as e:
        app.logger.error("!!! ERROR PROCESANDO DOCUMENTO !!!")
        app.logger.error(f"Error: {str(e)}")
        app.logger.error(traceback.format_exc())
        return jsonify({
            "error": f"Error interno: {str(e)}",
            "trace": traceback.format_exc()
        }), 500
        
    finally:
        # Cleanup temporary files as requested by the user
        try:
            if os.path.exists(TEMP_ASSETS_DIR):
                shutil.rmtree(TEMP_ASSETS_DIR)
        except Exception as e:
            app.logger.warning(f"Could not clean up temp directory: {e}")

if __name__ == '__main__':
    app.run(debug=True, port=5000)
