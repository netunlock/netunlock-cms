# 🚂 Migración a Railway - Guía Paso a Paso

## 1️⃣ **Crear Proyecto en Railway**

### Opción A: Desde la Web (Recomendado)

1. Ve a https://railway.app
2. Click en **"Start a New Project"**
3. Click en **"Deploy from GitHub"**
4. Autoriza Railway para acceder a tu GitHub
5. Selecciona el repo: `netunlock/netunlock-cms`
6. Selecciona la rama: `redesign/foro-moderno` (o `main` después de merge)
7. Click **"Deploy"**

### Opción B: Desde la CLI

```bash
# Instalar Railway CLI
npm install -g @railway/cli

# Login
railway login

# Crear proyecto
railway init

# Deploy
railway up
```

---

## 2️⃣ **Configurar Variables de Entorno**

En Railway Dashboard:

1. Ve a tu proyecto
2. Click en **"Variables"**
3. Agrega estas variables:

```
NODE_ENV = production
PORT = 5000
```

**Nota:** El puerto se configura automáticamente en Railway, no necesitas especificar nada.

---

## 3️⃣ **Verificar que Funciona**

Railway te dará una URL como:
```
https://netunlock-cms-production.up.railway.app
```

1. Accede a esa URL
2. Deberías ver la página pública
3. Prueba crear un post en `/#admin`

---

## 4️⃣ **Configurar Dominio Personalizado (Opcional)**

Si quieres tu dominio propio:

1. En Railway Dashboard → **"Settings"**
2. Click **"Domains"**
3. Conecta tu dominio

---

## 5️⃣ **Diferencias vs Render**

| Aspecto | Render | Railway |
|---|---|---|
| **Cold starts** | 10-30s | 2-5s |
| **Configuración** | Web UI simple | Similar |
| **Costo** | Gratis | Gratis ($5 crédito/mes) |
| **Performance** | Medio | Mejor |
| **Escalabilidad** | Limitada | Muy buena |

---

## ⚠️ **Importante**

- Railway no requiere cambios en el código
- `server.js` funciona igual
- `index.html` funciona igual
- Los únicos cambios serán en el redesign del frontend

---

## 🚀 **Próximos Pasos**

1. Crear proyecto en Railway ✅
2. Deploy automático desde GitHub ✅
3. Comenzar rediseño en rama `redesign/foro-moderno` ✅

**Una vez deployado en Railway:**
- Actualizar `API_BASE` en `index.html` (si lo necesitas)
- Comenzar con FASE 2: Rediseño

