# NetUnlock CMS Pro 🚀

**Sistema de gestión de contenidos profesional con editor de bloques avanzado, monetización integrada y deploy fácil en Cloudflare.**

---

## ✨ Características

- ✅ **Editor de Bloques Avanzado:**
  - Texto con formato (negrita, cursiva, subrayado, títulos)
  - Múltiples imágenes con posicionamiento
  - Embed de videos (YouTube, Vimeo)
  - Citas formateadas
  - Links de descarga
  - HTML personalizado
  - Reordenar bloques fácilmente

- ✅ **Panel Admin Completo:**
  - Login seguro (admin/admin123)
  - Crear, editar y eliminar posts
  - Gestión de comentarios
  - Dashboard de newsletter
  - Notificaciones automáticas al publicar

- ✅ **Comentarios Inteligentes:**
  - Anónimo o con email
  - Auto-detección de spam
  - Revisión de comentarios flagged

- ✅ **Newsletter:**
  - Suscripción fácil
  - Notificaciones automáticas de nuevos posts
  - Dashboard de suscriptores

- ✅ **Diseño Premium:**
  - Gradientes sofisticados
  - Tipografía elegante (Plus Jakarta Sans)
  - Responsive (mobile-first)
  - Dark mode moderno

- ✅ **Listo para Monetizar:**
  - Google AdSense integrado
  - Slots de publicidad personalizados
  - Affiliate links
  - Suscripción premium

---

## 🚀 Inicio Rápido

### Paso 1: Instalar dependencias
```bash
npm install
```

### Paso 2: Ejecutar localmente
```bash
npm start
```

Abre: **http://localhost:5000**

### Paso 3: Acceder al admin
- Usuario: `admin`
- Contraseña: `admin123`

---

## 📦 Estructura del Proyecto

```
netunlock-cms/
├── index.html              ← Frontend + Admin (SPA)
├── server.js               ← Backend (Express + SQLite)
├── package.json            ← Dependencias
├── START.md                ← Quick start
├── SETUP.md                ← Setup detallado
├── DEPLOY.md               ← GitHub + Cloudflare
├── MONETIZATION.md         ← Estrategias de ingresos
├── CHECKLIST.md            ← Validación paso a paso
└── README.md               ← Este archivo
```

---

## 🔐 Seguridad

- ✅ Contraseña admin (cambiar después de testear)
- ✅ Token Bearer para autenticación
- ✅ SQL Injection prevention (prepared statements)
- ✅ CORS habilitado
- ✅ Password en variables de entorno

---

## 📊 Próximos Pasos

### Para Empezar Ahora
1. [Quick Start](START.md) - 2 minutos
2. [Crear primeros posts](#crear-posts)
3. [Cambiar credenciales](#cambiar-admin)

### Para Deploy
1. [Setup Completo](SETUP.md)
2. [Deploy en GitHub + Cloudflare](DEPLOY.md)
3. [Configurar dominio personalizado](#dominio)

### Para Monetizar
1. [Estrategias de Monetización](MONETIZATION.md)
2. [Google AdSense](#adsense)
3. [Publicidad personalizada](#ads)
4. [Affiliate links](#affiliate)

---

## ✏️ Crear Posts

### Editor de Bloques

1. Click "Admin" → Login
2. Click "+ Crear Nuevo Post"
3. Completa:
   - **Título:** Nombre del post
   - **Descripción:** Para la tarjeta
4. Agrega bloques:
   - **+ Texto:** Contenido con formato
   - **+ Imagen:** Imágenes posicionables
   - **+ Video:** Embed de videos
   - **+ Cita:** Bloques de cita
   - **+ Descarga:** Links de descarga
   - **+ HTML:** Código personalizado
5. Reordena con ⬆️ ⬇️
6. Click "Publicar Post"

### Formato de Texto

Selecciona texto en un bloque y usa:
- **Negrita** - `<strong>texto</strong>`
- **Cursiva** - `<em>texto</em>`
- **Subrayado** - `<u>texto</u>`
- **Títulos** - H1, H2, H3
- **Citas** - `<blockquote>`

---

## 🔄 Editar Posts

1. Admin → Pestaña "Posts"
2. Click "✏️ Editar" en el post
3. Modifica los bloques
4. Click "Actualizar Post"

---

## 💬 Comentarios

**Visitantes pueden comentar:**
- Anónimos (sin email)
- Con email (aparece su nombre)

**Admin puede:**
- Ver comentarios flagged como spam
- Eliminar comentarios spam
- Dashboard en "Comentarios"

---

## 📧 Newsletter

**Visitantes se suscriben:**
- Email fácil (sin datos personales)
- Reciben notificación automática de nuevos posts

**Admin ve:**
- Cantidad de suscriptores
- Lista de emails
- Fecha de suscripción

---

## 🔑 Cambiar Admin

En `server.js`, línea ~10:

```javascript
if (username === 'admin' && password === 'admin123') {
```

Cámbialo a:

```javascript
if (username === 'tu-usuario' && password === 'tu-password-seguro') {
```

Luego reinicia: `npm start`

---

## 💰 Monetización

### Google AdSense (Pasivo)
- Requiere tráfico mínimo
- Google paga por impresiones/clicks
- Ver: [MONETIZATION.md](MONETIZATION.md)

### Publicidad Personalizada
- Vende espacios a empresas ($100-1000/mes)
- Controla posición (sidebar, footer, etc.)

### Suscripción Premium
- Contenido exclusivo
- Integración con Stripe/PayPal

### Affiliate Links
- Amazon Associates
- Hosting, dominios, herramientas
- Comisión por ventas

---

## 🌐 Deploy en Cloudflare

Ver: [DEPLOY.md](DEPLOY.md)

**Resumen:**
1. Push a GitHub
2. Cloudflare Pages → Connect Git
3. Backend en Render.com (Node.js)
4. Dominio personalizado (opcional)

---

## 🛠️ Tecnologías

| Parte | Tecnología |
|-------|-----------|
| Frontend | HTML5 + Tailwind CSS + JS Vanilla |
| Backend | Node.js + Express |
| Database | SQLite (en memoria o archivo) |
| Hosting | Cloudflare Pages (frontend) + Render (backend) |
| Monetización | Google AdSense + Stripe/PayPal |

---

## 📚 Documentación

- [START.md](START.md) - Inicio rápido (2 min)
- [SETUP.md](SETUP.md) - Setup detallado
- [DEPLOY.md](DEPLOY.md) - GitHub + Cloudflare
- [MONETIZATION.md](MONETIZATION.md) - Generar ingresos
- [CHECKLIST.md](CHECKLIST.md) - Validación completa

---

## 🐛 Troubleshooting

| Problema | Solución |
|----------|----------|
| "Cannot find module" | `npm install` |
| Login no funciona | Verifica admin/admin123 en server.js |
| Posts no aparecen | Recarga la página (F5) |
| Comentarios no se guardan | Verifica conexión a localhost:5000 |
| Newsletter error | Verifica email válido |

---

## 📝 Changelog

### v1.0.0 (Actual)
- ✅ Editor de bloques avanzado
- ✅ Crear/Editar/Eliminar posts
- ✅ Sistema de comentarios con spam-detection
- ✅ Newsletter con notificaciones automáticas
- ✅ Admin dashboard completo
- ✅ Design premium anti-IA

---

## 📞 Soporte

- Documentación: [DEPLOY.md](DEPLOY.md)
- Monetización: [MONETIZATION.md](MONETIZATION.md)
- Validación: [CHECKLIST.md](CHECKLIST.md)

---

## 📄 Licencia

MIT - Úsalo como quieras, únicamente para tus proyectos.

---

## 🎉 Listo para Empezar

```bash
npm install && npm start
```

Luego abre: **http://localhost:5000**

**¡Crea tu primer post ahora!** 🚀
