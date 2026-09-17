# ⚡ Quick Start - NetUnlock CMS

## 1️⃣ Instala Wrangler
```bash
npm install -g wrangler
```

## 2️⃣ Crea la BD
```bash
wrangler d1 create netunlock
# Copia el database_id que te dé
```

## 3️⃣ Actualiza wrangler.toml
```toml
[[d1_databases]]
database_id = "TU_ID_AQUI"
```

## 4️⃣ Inicializa tablas
```bash
wrangler d1 execute netunlock < init-db.sql
```

## 5️⃣ Configura contraseña admin
En **wrangler.toml**:
```toml
vars = { ADMIN_PASSWORD = "tu-password-fuerte" }
```

## 6️⃣ Prueba localmente
```bash
wrangler dev
# Abre http://localhost:8787
```

## 7️⃣ Verifica BD
```bash
wrangler d1 query "SELECT COUNT(*) FROM posts;" --database netunlock
# Debería mostrar 1 (post de ejemplo)
```

## 8️⃣ Deploy Workers
```bash
wrangler deploy
# Copia la URL que aparece
```

## 9️⃣ Actualiza API_BASE
En **index.html**, busca:
```javascript
const API_BASE = 'https://netunlock-api.YOUR-ACCOUNT.workers.dev/api';
```

## 🔟 Deploy en Pages
- GitHub: Sube los archivos
- Cloudflare Pages: Connect Git
- Build command: (vacío)
- Output: /
- Deploy ✓

## ✅ Listo
- Frontend: tu-url.pages.dev
- Admin: Click en "Admin" → Tu contraseña
- Crear posts: "+ Crear Nuevo Post"
- Ver público: "Recursos"

---

## Comandos Útiles

```bash
# Prueba local
wrangler dev

# Deploy
wrangler deploy

# Ver BD
wrangler d1 query "SELECT * FROM posts;" --database netunlock

# Ver logs
wrangler tail

# Crear nueva tabla
wrangler d1 execute netunlock --command "CREATE TABLE..."
```

---

## Admin URLs

- **Login:** Click "Admin" → Ingresa contraseña
- **Dashboard:** posts → comentarios → newsletter
- **Crear post:** "+ Crear Nuevo Post"
- **Eliminar:** Click en "Eliminar" dentro del dashboard

---

## Archivos que necesitas

```
✓ index.html         ← Frontend (1 archivo, 1000+ líneas)
✓ wrangler.toml      ← Config
✓ src/index.js       ← API
✓ init-db.sql        ← Base de datos
✓ package.json       ← Dependencias
```

---

## Troubleshooting 2 Minutos

| Problema | Fix |
|----------|-----|
| API 404 | Verifica `API_BASE` en index.html |
| DB error | Ejecuta `init-db.sql` de nuevo |
| Login falla | Revisa `ADMIN_PASSWORD` en wrangler.toml |
| No ve posts | Verifica que `database_id` es correcto |

---

**¿Preguntas? Ver SETUP.md o README.md**

Última actualización: 2026-09-17
