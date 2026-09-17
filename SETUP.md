# 🚀 NetUnlock: Guía de Deployement

## Arquitectura del Sistema

```
┌─────────────────────────────────────┐
│   Cloudflare Pages (Frontend)       │
│  - index.html (SPA completa)        │
│  - Interfaz pública + Admin         │
└────────────────┬────────────────────┘
                 │ HTTP/API Calls
                 ▼
┌─────────────────────────────────────┐
│  Cloudflare Workers (Backend)       │
│  - Rutas de API REST                │
│  - Autenticación de admin           │
│  - Lógica de posts, comentarios     │
└────────────────┬────────────────────┘
                 │ SQL Queries
                 ▼
┌─────────────────────────────────────┐
│   Cloudflare D1 (Base de Datos)     │
│  - SQLite - posts, comments, subs   │
└─────────────────────────────────────┘
```

---

## 📋 Requisitos Previos

- Cuenta en **Cloudflare** (https://dash.cloudflare.com)
- Node.js 18+ instalado localmente
- npm o yarn
- Git (opcional pero recomendado)

---

## ⚙️ Paso 1: Setup Local

### 1.1 Clonar/Descargar archivos

```bash
# Crear carpeta del proyecto
mkdir netunlock-cms
cd netunlock-cms

# Copiar estos archivos en la carpeta:
# - index.html
# - wrangler.toml
# - src/index.js (crear carpeta src/)
```

### 1.2 Instalar dependencias

```bash
npm install -g wrangler
npm init -y
npm install
```

---

## 🗄️ Paso 2: Crear Base de Datos en Cloudflare D1

### 2.1 Crear la base de datos

```bash
wrangler d1 create netunlock
```

Esto te dará un `database_id`. **Guárdalo** para el siguiente paso.

### 2.2 Actualizar `wrangler.toml`

Reemplaza `tu-database-id-aqui` con el ID que recibiste:

```toml
[[d1_databases]]
binding = "DB"
database_name = "netunlock"
database_id = "5abc1234-9999-4321-abcd-1234567890ab"  # Tu ID aquí
```

### 2.3 Crear tablas iniciales

```bash
wrangler d1 execute netunlock --local < init-db.sql
```

Crea un archivo `init-db.sql` con este contenido:

```sql
CREATE TABLE IF NOT EXISTS posts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  description TEXT,
  content TEXT NOT NULL,
  image_url TEXT,
  video_url TEXT,
  published INTEGER DEFAULT 0,
  views INTEGER DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS comments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  post_id INTEGER NOT NULL,
  author_name TEXT DEFAULT 'Anónimo',
  author_email TEXT,
  content TEXT NOT NULL,
  is_flagged INTEGER DEFAULT 0,
  approved INTEGER DEFAULT 1,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS newsletter (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT UNIQUE NOT NULL,
  subscribed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  unsubscribed INTEGER DEFAULT 0
);
```

---

## 🔐 Paso 3: Configurar Variables de Entorno

En `wrangler.toml`, actualiza la contraseña de admin:

```toml
[env.production]
vars = { 
  ADMIN_PASSWORD = "tu-password-mega-seguro-aqui",
  SITE_URL = "tu-dominio.com"
}
```

**Recomendaciones:**
- Usa una contraseña fuerte (mínimo 16 caracteres)
- Guárdala en un gestor de contraseñas
- Cámbiala regularmente

---

## 🧪 Paso 4: Probar Localmente

```bash
wrangler dev
```

Visita http://localhost:8787

### Pruebas rápidas:

1. **Ver posts públicos**: La página debe cargar sin errores
2. **Newsletter**: Ingresa un email y suscríbete
3. **Admin panel**: Click en "Admin" → Ingresa tu contraseña
4. **Crear post**: Desde el admin, crea un post de prueba

---

## 🚀 Paso 5: Deploy en Cloudflare

### 5.1 Conectar a GitHub (recomendado)

```bash
git init
git add .
git commit -m "Initial commit: NetUnlock CMS"
git remote add origin https://github.com/tu-usuario/netunlock
git push -u origin main
```

### 5.2 Configurar Cloudflare Pages

1. Ve a **Cloudflare Dashboard** → **Pages**
2. Click en **Create a project** → **Connect to Git**
3. Selecciona tu repositorio `netunlock`
4. **Build settings:**
   - Framework: None
   - Build command: (dejar vacío)
   - Build output directory: / (raíz)
5. Click **Save and Deploy**

### 5.3 Configurar Workers

```bash
wrangler deploy
```

Esto subirá tu API a Cloudflare Workers.

---

## 🔗 Paso 6: Conectar Frontend con Backend

En el `index.html`, actualiza la variable `API_BASE`:

```javascript
const API_BASE = 'https://netunlock-api.nombre-de-usuario.workers.dev/api';
```

(Reemplaza con la URL que Cloudflare te proporcione al hacer deploy de Workers)

---

## 📊 Estructura Final de Rutas

### Públicas (sin autenticación)
- `GET /api/posts` → Lista de posts
- `GET /api/posts/:id` → Detalle de post (incrementa views)
- `GET /api/posts/:id/comments` → Comentarios del post
- `POST /api/posts/:id/comments` → Crear comentario
- `POST /api/newsletter/subscribe` → Suscribirse

### Admin (requieren token)
- `POST /api/admin/login` → Login (devuelve token)
- `POST /api/posts` → Crear post
- `PUT /api/posts/:id` → Editar post
- `DELETE /api/posts/:id` → Eliminar post
- `DELETE /api/comments/:id` → Eliminar comentario

---

## 🛡️ Seguridad

### Ya implementado:
- ✅ Token de autenticación simple
- ✅ Detección de spam en comentarios (keywords sospechosas)
- ✅ CORS habilitado solo para tu dominio
- ✅ Contraseña encriptada en variables de entorno

### Para producción (TODO):
- [ ] Implementar JWT en lugar de tokens simples
- [ ] Rate limiting en API
- [ ] Validación más robusta de inputs
- [ ] Logs de auditoría
- [ ] Backup automático de D1

---

## 📝 Contenido de Ejemplo

Para probar, crea un post vía admin con:

```json
{
  "title": "Cómo optimizar tu tienda",
  "description": "Guía completa para mejorar ventas",
  "content": "Lorem ipsum dolor sit amet...",
  "image_url": "https://via.placeholder.com/600x400",
  "video_url": "https://www.youtube.com/embed/dQw4w9WgXcQ"
}
```

---

## 🐛 Troubleshooting

| Problema | Solución |
|----------|----------|
| "API not found" | Verifica que `API_BASE` en index.html coincida con tu Workers URL |
| "Database error" | Ejecuta `wrangler d1 execute netunlock < init-db.sql` de nuevo |
| Login no funciona | Revisa que `ADMIN_PASSWORD` en wrangler.toml sea correcta |
| Comentarios no se guardan | Verifica que D1 está vinculado correctamente en wrangler.toml |

---

## 📞 Soporte

Para problemas específicos:
- Docs de Cloudflare: https://developers.cloudflare.com
- Cloudflare Community: https://community.cloudflare.com
- Workers Docs: https://developers.cloudflare.com/workers

---

## ✨ Próximos pasos opcionales

- [ ] Integrar email transaccional (Resend, SendGrid)
- [ ] Agregar búsqueda de posts (FTS en SQLite)
- [ ] Sistema de categorías/tags
- [ ] Estadísticas en admin (posts más vistos, etc)
- [ ] Exportar newsletter a CSV
- [ ] Dark/Light mode selector
- [ ] Soporte multiidioma

---

**¡Listo! Tu CMS está en vivo en Cloudflare. 🎉**
