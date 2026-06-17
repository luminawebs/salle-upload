# Revisor de Documentos - LA SALLE

This application validates `.docx` documents against a specific structure for La Salle, extracting Unidades Didácticas, Preguntas Orientadoras, Actividades, and their chosen virtual platform tools (Foro, Tarea, Cuestionario, etc.).

## Project Structure
- `app.py`: Flask application providing the backend API.
- `wsgi.py`: Entry point for production WSGI servers (like Gunicorn).
- `core/`: Python modules for parsing and reviewing the `.docx`.
  - `data_parser.py`: Converts `.docx` to HTML using Mammoth.
  - `document_reviewer.py`: Contains the logic to extract structural information from the converted HTML.
- `static/`: Frontend assets (HTML, CSS, JS).
- `requirements.txt`: Python dependencies.

## Deployment to DigitalOcean Droplet (Ubuntu)

Follow these steps to deploy the application to a DigitalOcean Droplet running Ubuntu:

### 1. Update and Install Dependencies
```bash
sudo apt update
sudo apt install python3-pip python3-venv nginx -y
```

### 2. Clone/Upload the Project
Upload this project folder to your Droplet, typically in `/var/www/document_review_SALLE` or inside your home directory.

### 3. Setup Python Virtual Environment
Navigate to the project directory:
```bash
cd /path/to/document_review_SALLE
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Test Gunicorn
Test that Gunicorn can serve the application:
```bash
gunicorn --bind 0.0.0.0:5000 wsgi:app
```
(Press `Ctrl+C` to stop it once confirmed).

### 5. Create a Systemd Service for Gunicorn
Create a service file to run the app in the background:
```bash
sudo nano /etc/systemd/system/docreviewer.service
```
Add the following content (update the paths according to your setup):
```ini
[Unit]
Description=Gunicorn instance to serve Document Reviewer
After=network.target

[Service]
User=root
Group=www-data
WorkingDirectory=/path/to/document_review_SALLE
Environment="PATH=/path/to/document_review_SALLE/venv/bin"
ExecStart=/path/to/document_review_SALLE/venv/bin/gunicorn --workers 3 --bind unix:docreviewer.sock -m 007 wsgi:app

[Install]
WantedBy=multi-user.target
```
Start and enable the service:
```bash
sudo systemctl start docreviewer
sudo systemctl enable docreviewer
```

### 6. Configure Nginx as a Reverse Proxy
```bash
sudo nano /etc/nginx/sites-available/docreviewer
```
Add the following content (replace `your_domain_or_IP`):
```nginx
server {
    listen 80;
    server_name your_domain_or_IP;

    location / {
        include proxy_params;
        proxy_pass http://unix:/path/to/document_review_SALLE/docreviewer.sock;
    }
}
```
Enable the site and restart Nginx:
```bash
sudo ln -s /etc/nginx/sites-available/docreviewer /etc/nginx/sites-enabled
sudo nginx -t
sudo systemctl restart nginx
```

Your application should now be live and accessible via your Droplet's IP address!
