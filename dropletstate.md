# Remote Droplet Current State & Architecture Source of Truth

This document outlines the exact environment, reverse-proxy mappings, hardware constraints, and service configurations for the live deployment on the DigitalOcean Droplet. Read this file before recommending any script execution, dependency upgrades, or configuration changes.

---

## 1. Hardware Constraints & Emergency Virtual Memory
* **CPU/RAM:** 1 vCPU / 512 MB RAM (DigitalOcean Micro Instance).
* **Critical Operational Guardrail:** Due to the extremely tight 512MB memory space, an emergency **2GB Swap File** has been configured and mounted permanently at `/swapfile`.
* **Constraint:** Any high-memory operations (such as running multi-threaded browser automation, heavy npm builds, or unpacking massive packages) must rely on this swap buffer. Avoid spiking parallel processes.

---

## 2. Monolithic Application Architecture (Unified App Setup)
The original split architecture has been consolidated. The `salle-upload` project now serves as an all-in-one unified production platform handling both the documentation analysis and Moodle background automation workflows simultaneously.

* **Repository Active Root:** `/var/www/salle_automate`
* **Active Git Branch:** `salle`
* **Isolated Runtime:** Virtual environment initialized at `/var/www/salle_automate/venv` (Python 3.12).

---

## 3. Nginx Reverse Proxy Routing Matrix
Nginx handles traffic on public port `80` and splits requests between static compiled assets and the FastAPI application layer based on structural URL prefixes:

| Public URL Path | Proxy/Alias Target | Purpose | Connection Rules |
| :--- | :--- | :--- | :--- |
| `http://157.230.50.37/` | `/var/www/salle_automate/frontend/dist/` | Vite Production Frontend App | Served directly as static files. |
| `http://157.230.50.37/automate/api` | `http://127.0.0.1:8000/api` | FastAPI Python Backend Engine | Reverse proxy traffic forwarder. |

### Critical SSE Configuration for `/automate/api`
To allow the live log stream interface (`/api/logs`) to function through Server-Sent Events (SSE) without buffer timeout crashes, Nginx has buffering disabled and extended timeouts locked in:
```nginx
proxy_set_header Connection '';
proxy_http_version 1.1;
chunked_transfer_encoding off;
proxy_buffering off;
proxy_read_timeout 3600s;
client_max_body_size 50M; # Overrides Nginx 1MB default file upload restriction