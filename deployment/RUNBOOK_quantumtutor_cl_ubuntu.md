# RUNBOOK: Deployment de Piloto (Ubuntu Server)
*Gobernado por políticas `.agent/workflows/deployment_production.md`*

## 1. PRE-CHECK 
Asegúrate de contar con lo siguiente antes de proceder:
- [x] Dominio base: `quantumtutor.cl`
- [x] Subdominios: `quantumtutor.cl`, `api.quantumtutor.cl`, `admin.quantumtutor.cl`
- [x] Cuenta de **Cloudflare Zero Trust / Teams** activa.
- [x] Acceso **SSH** al servidor Ubuntu preparado.
- [x] Repositorio en su respectivo main inclueyendo la carpeta estricta `.agent`.

---

## 2. DESPLIEGUE EN UBUNTU (Setup Híbrido)

**Paso 1: Ingreso al servidor**
```bash
ssh user@tu-servidor
```

**Paso 2: Clonar el proyecto**
```bash
sudo mkdir -p /opt/quantum_tutor
cd /opt/quantum_tutor

sudo git clone <TU_REPO> current
cd current
```

**Paso 3: Bootstrap Automático**
Instalar dependencias globales y sistema base.
```bash
sudo bash deployment/scripts/deploy_quantumtutor_ubuntu.sh bootstrap
```

**Paso 4: Configurar los Secretos / Config Env**
```bash
sudo nano /etc/quantum-tutor/quantum_tutor.env
```
> [!CAUTION]  
> Asegúrate de mapear estas variables críticas para abandonar el modo "LOCAL_FALLBACK":
> - `ENV=production`
> - `API_KEY=...`
> - `SECRET_KEY=...`
> - `GEMINI_API_KEYS=...`
> - `WOLFRAM_APP_ID=...`
> - `QT_BOOTSTRAP_ADMIN_EMAIL=...`
> - `QT_BOOTSTRAP_ADMIN_PASSWORD=...`

---

## 3. CLOUDFLARE TUNNEL (Configuración Edge/Network)

**1. Inicio de Sesión / Autenticación de Cloudflare**
```bash
sudo bash deployment/scripts/deploy_quantumtutor_ubuntu.sh cloudflare-login
```

**2. Creación del Tunnel**
```bash
cloudflared tunnel create quantumtutor
```
*(Copia el `TU_UUID` generado y expórtalo en el ambiente)*
```bash
export QT_TUNNEL_ID="TU_UUID"
```

**3. Configuración del Archivo del Tunnel**
```bash
sudo -E bash deployment/scripts/deploy_quantumtutor_ubuntu.sh configure-tunnel
```
*(Verificar la salida de configuración)*
```bash
sudo cat /etc/cloudflared/quantumtutor-cl.yml
```
> [!NOTE]
> Comprueba que incluya entradas válidas para `quantumtutor.cl`, `api.quantumtutor.cl` y `admin.quantumtutor.cl`.

---

## 4. RESOLUCIÓN DNS (Panel de Cloudflare)
En el panel web de tu DNS, vincula el túnel:
- `CNAME` → `quantumtutor.cl` → `TU_UUID.cfargotunnel.com`
- `CNAME` → `api.quantumtutor.cl` → `TU_UUID.cfargotunnel.com`
- `CNAME` → `admin.quantumtutor.cl` → `TU_UUID.cfargotunnel.com`

---

## 5. PROTECCIÓN DE ACCESO ZERO TRUST
En la configuración de Cloudflare (Access → Applications → Add):
- **OBLIGATORIO PROTEGER**: `admin.quantumtutor.cl` (Allow: emails admin)
- **NO PROTEGER** (Tráfico libre): `quantumtutor.cl`, `api.quantumtutor.cl`

---

## 6. LEVANTAR SERVICIOS (Go-Live)
```bash
sudo bash deployment/scripts/deploy_quantumtutor_ubuntu.sh start
```

---

## 7. VALIDACIÓN OBLIGATORIA DEL PILOTO

**1. Scripts Automáticos:**
```bash
sudo bash deployment/scripts/deploy_quantumtutor_ubuntu.sh preflight
sudo bash deployment/scripts/deploy_quantumtutor_ubuntu.sh smoke-test
```

**2. Controles HTTP:**
```bash
curl -I https://quantumtutor.cl
curl -I https://api.quantumtutor.cl/health
curl -I https://admin.quantumtutor.cl
```

**3. Validación Manual (Agente/Humano UI):**
- [ ] Flujo Estudiante: *Registro* → *Diagnóstico* → *Learning Journey* → *Evaluación Externa*.
- [ ] Muros de Carga de Seguridad: Inyección XSS anulada, Admin cruzado denegado.
- [ ] Estabilidad de Dashboards: Piloto Results exponiendo métricas nítidas de Pearson.

---

## 8. MONITOREO
Consolas críticas de rastreo de estado:
```bash
sudo journalctl -u quantum-tutor-api.service -f
sudo journalctl -u quantum-tutor-ui.service -f
sudo journalctl -u cloudflared.service -f

ss -ltnp | grep -E '8000|8501|8080'
```

> [!CAUTION]  
> **REGLAS DURANTE PILOTO (.agent)**
> - ❌ NO se hacen cambios estructurales grandes.
> - ❌ NO se modifica el engine subyacente.
> - ❌ NO se alteran las métricas recolectadas.
> - ✔️ SÍ se observan fricciones, se detectan fallos conceptuales y se retienen datos de correlación pura.
