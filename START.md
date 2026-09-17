# 🚀 NetUnlock CMS - Inicio Rápido

## ⚡ 3 pasos para empezar

### 1️⃣ Instala dependencias
```bash
npm install
```

### 2️⃣ Inicia el servidor
```bash
npm start
```

Deberías ver:
```
🚀 NetUnlock CMS Backend ejecutándose en http://localhost:5000

📍 Frontend: http://localhost:5000
🔐 Credenciales de Admin:
   Usuario: admin
   Contraseña: admin123
```

### 3️⃣ Abre en el navegador
```
http://localhost:5000
```

---

## 📝 Qué puedes hacer

### Vista Pública
- ✅ Ver posts
- ✅ Leer contenido completo
- ✅ Comentar (anónimo o con email)
- ✅ Suscribirse al newsletter

### Panel Admin (Click "Admin")
- ✅ Usuario: `admin`
- ✅ Contraseña: `admin123`
- ✅ Crear posts
- ✅ Eliminar posts
- ✅ Ver comentarios flagged (spam)
- ✅ Ver suscriptores

---

## 🎯 Quick Test

1. **Abre** http://localhost:5000
2. **Click** "Admin" → Ingresa admin/admin123
3. **Click** "+ Crear Nuevo Post"
4. **Completa:**
   - Título: "Mi Primer Post"
   - Contenido: "Contenido de prueba"
   - Imagen: https://via.placeholder.com/600x400
5. **Click** "Publicar"
6. **Click** "Recursos" → Deberías ver tu post

---

## 🔑 Cambiar Credenciales (después de testear)

En **server.js**, línea ~250, busca:
```javascript
if (username === 'admin' && password === 'admin123') {
```

Cámbialo a:
```javascript
if (username === 'tu-usuario' && password === 'tu-password-seguro') {
```

Luego reinicia: `npm start`

---

## ⚙️ Para Detener

Presiona: `Ctrl + C`

---

## 🐛 Si algo no funciona

| Problema | Solución |
|----------|----------|
| "Port already in use" | `npm start` en otra terminal o cambia PORT en server.js |
| "Cannot find module" | Ejecuta `npm install` de nuevo |
| Conexión rechazada | Verifica que `npm start` está ejecutándose |

---

## 📂 Archivos Principales

- **server.js** - Backend Express + SQLite
- **index.html** - Frontend SPA completo
- **package.json** - Dependencias

¡Eso es todo! 🎉

Para documentación completa, ver SETUP.md o README.md
