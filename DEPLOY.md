# 🚀 Deploy en GitHub y Cloudflare

## Paso 1: Preparar en GitHub

### 1.1 Crear repositorio en GitHub

```bash
# Inicia git
git init

# Agrega todos los archivos
git add .

# Primer commit
git commit -m "Initial commit: NetUnlock CMS Pro with block editor"

# Agrega remote
git remote add origin https://github.com/tu-usuario/netunlock-cms.git

# Cambia rama a main (GitHub lo espera)
git branch -M main

# Push
git push -u origin main
```

### 1.2 Estructura de carpetas para GitHub

```
netunlock-cms/
├── .github/
│   └── workflows/
│       └── deploy.yml          ← CI/CD automático
├── public/                      ← Frontend (index.html)
├── server.js                    ← Backend
├── package.json
├── .gitignore
├── README.md
├── DEPLOY.md
└── MONETIZATION.md
```

---

## Paso 2: Deploy en Cloudflare Pages (Frontend)

### 2.1 Conectar GitHub a Cloudflare Pages

1. **Ve a:** https://dash.cloudflare.com
2. **Sidebar → Pages**
3. **"Create a project" → "Connect to Git"**
4. **Selecciona tu repositorio `netunlock-cms`**
5. **Build settings:**
   - Framework: None
   - Build command: (vacío)
   - Build output directory: `/`
6. **Click "Save and Deploy"**

**Tu frontend estará en:** `https://netunlock-cms.pages.dev`

---

## Paso 3: Deploy Backend (Cloudflare Workers + Node)

### Opción A: Usando Render.com (Recomendado para principiantes)

#### 3.1 Crear cuenta en Render

1. Ve a https://render.com
2. Crea cuenta con GitHub
3. Click "New +" → "Web Service"
4. Conecta tu repositorio
5. Configuración:
   - **Name:** netunlock-api
   - **Environment:** Node
   - **Build Command:** `npm install`
   - **Start Command:** `node server.js`
   - **Port:** 5000

#### 3.2 Actualizar API_BASE en index.html

Una vez deployado, Render te dará una URL como `https://netunlock-api.onrender.com`

En el archivo `index.html`, busca:
```javascript
const API_BASE = 'http://localhost:5000/api';
```

Reemplázalo con:
```javascript
const API_BASE = 'https://netunlock-api.onrender.com/api';
```

Luego haz commit y push:
```bash
git add index.html
git commit -m "Update API_BASE for production"
git push
```

Cloudflare Pages se actualizará automáticamente.

---

### Opción B: Cloudflare Workers (Avanzado)

Si quieres todo en Cloudflare:

```bash
npm install -g wrangler
wrangler deploy
```

Esto deployará tu backend en Cloudflare Workers.

---

## Paso 4: Variables de Entorno

### En Render:

1. **Settings → Environment**
2. Agrega:
   ```
   ADMIN_PASSWORD=tu-password-seguro
   ```

### En Cloudflare Pages:

Variables públicas (si las necesitas):
1. **Settings → Environment Variables**

---

## Paso 5: Base de Datos Persistente

**IMPORTANTE:** Con la configuración actual, la base de datos se reinicia cuando el servidor se reinicia.

Para datos persistentes, elige uno:

### A. Usar Render con Postgres (Gratis)
```bash
npm install pg
```

Actualiza `server.js` para usar PostgreSQL en lugar de SQLite.

### B. Usar MongoDB Atlas (Gratis)
```bash
npm install mongoose
```

### C. Usar Cloudflare D1 (Recomendado)
D1 es SQLite en Cloudflare. Ver: https://developers.cloudflare.com/d1/

---

## Paso 6: Configurar Dominio Personalizado

### En Cloudflare Pages:

1. **Your website → Settings → Custom Domains**
2. **Add Custom Domain**
3. Ingresa tu dominio (ej: `cms.tudominio.com`)
4. **Continue**
5. Sigue las instrucciones para apuntar el DNS

---

## 🎯 Resumen de URLs Finales

| Servicio | URL |
|----------|-----|
| Frontend | `https://netunlock-cms.pages.dev` |
| Frontend Custom | `https://cms.tudominio.com` |
| Backend API | `https://netunlock-api.onrender.com` |
| Admin Panel | `https://cms.tudominio.com/?admin` |

---

## 🔄 CI/CD Automático

Crear `.github/workflows/deploy.yml`:

```yaml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Deploy to Cloudflare Pages
        uses: cloudflare/wrangler-action@v3
        with:
          apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          accountId: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
```

---

## ✅ Checklist de Deploy

- [ ] Repositorio en GitHub creado
- [ ] Archivos pusheados a main
- [ ] Cloudflare Pages conectado
- [ ] Backend en Render/Workers
- [ ] `API_BASE` actualizado en index.html
- [ ] Variables de entorno configuradas
- [ ] Base de datos persistente (opcional)
- [ ] Dominio personalizado (opcional)
- [ ] CI/CD configurado (opcional)

---

## 🚨 Troubleshooting

| Problema | Solución |
|----------|----------|
| CORS Error | Agrega headers CORS en server.js |
| API 404 | Verifica `API_BASE` en index.html |
| Admin no funciona | Verifica `ADMIN_PASSWORD` en env vars |
| Datos se pierden | Configura base de datos persistente |

---

**¡Ahora tu CMS está en producción! 🎉**
