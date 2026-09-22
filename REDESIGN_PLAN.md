# 🎨 Plan de Rediseño: Foro Moderno

## 📊 Arquitectura Nueva

```
netlify-cms/
├── index.html (SPA única)
├── server.js (Express backend)
├── package.json
└── public/
    ├── css/ (NEW - estilos separados)
    │   ├── base.css
    │   ├── layout.css
    │   └── responsive.css
    └── js/ (NEW - scripts separados)
        ├── router.js (History API)
        ├── views.js
        └── api.js
```

---

## 🔄 **Router: De Hash a History API**

### Antes (Hash-based)
```
http://site.com/#admin
http://site.com/#post/mi-titulo
```

### Después (Real URLs)
```
http://site.com/admin
http://site.com/post/mi-titulo
http://site.com/ (home)
```

### Cambios en server.js

```javascript
// Servir SPA
app.get('/', (req, res) => res.sendFile(path.join(__dirname, 'index.html')));
app.get('/admin', (req, res) => res.sendFile(path.join(__dirname, 'index.html')));
app.get('/post/:slug', (req, res) => res.sendFile(path.join(__dirname, 'index.html')));

// API (sin cambios)
app.get('/api/posts', ...);
```

---

## 🏠 **Nuevas Vistas**

### 1. **HomeView** - Feed principal
```html
<div id="homeView" class="view active">
  <!-- Header -->
  <header class="navbar">
    <h1>NetUnlock</h1>
    <nav>
      <a href="/admin" class="dev-link">dev</a>
    </nav>
  </header>

  <!-- Search & Filter -->
  <div class="search-section">
    <input type="search" placeholder="Buscar posts...">
    <button>🔍</button>
  </div>

  <!-- Featured Posts -->
  <section class="featured-section">
    <h2>Destacados</h2>
    <div class="posts-featured">
      <!-- Posts renderizados aquí -->
    </div>
  </section>

  <!-- All Posts Grid -->
  <section class="posts-section">
    <h2>Todos los Posts</h2>
    <div id="postsGrid" class="posts-grid">
      <!-- Grid responsive de posts -->
    </div>
  </section>

  <!-- Ads -->
  <div class="ad-section">
    <!-- Google AdSense -->
  </div>

  <!-- Newsletter -->
  <section class="newsletter">
    <h2>Suscríbete</h2>
    <form>
      <input type="email" placeholder="tu@email.com">
      <button>Suscribirse</button>
    </form>
  </section>
</div>
```

### 2. **PostView** - Página dedicada de post
```html
<div id="postView" class="view hidden">
  <!-- Breadcrumb -->
  <div class="breadcrumb">
    <a href="/">← Volver</a>
  </div>

  <!-- Post Content -->
  <article class="post-article">
    <h1 class="post-title">Título del Post</h1>
    
    <div class="post-meta">
      <span>👤 Autor</span>
      <span>📅 Fecha</span>
      <span>👁 Views</span>
    </div>

    <!-- Featured Image -->
    <img src="" alt="" class="post-featured-image">

    <!-- Post Content (bloques) -->
    <div id="postContent" class="post-content">
      <!-- Contenido renderizado aquí -->
    </div>

    <!-- Share Buttons -->
    <div class="share-buttons">
      <a href="" class="share-btn">💬 WhatsApp</a>
      <a href="" class="share-btn">👍 Facebook</a>
      <a href="" class="share-btn">𝕏 Twitter</a>
      <button class="share-btn">🔗 Copiar</button>
    </div>

    <!-- Ads -->
    <div class="ad-section-post">
      <!-- Google AdSense -->
    </div>
  </article>

  <!-- Comments Section -->
  <section class="comments-section">
    <h2>💬 Comentarios</h2>
    
    <!-- Comment Form -->
    <form class="comment-form">
      <input type="email" placeholder="tu@email.com (opcional)">
      <textarea placeholder="Tu comentario..."></textarea>
      <button type="submit">Publicar</button>
    </form>

    <!-- Comments List -->
    <div id="commentsList" class="comments-list">
      <!-- Comentarios renderizados aquí -->
    </div>
  </section>

  <!-- Related Posts -->
  <section class="related-posts">
    <h2>📚 Posts Relacionados</h2>
    <div class="posts-grid">
      <!-- Posts relacionados -->
    </div>
  </section>

  <!-- Newsletter (Small) -->
  <div class="newsletter-small">
    <p>¿Te gustó? Suscríbete para más contenido.</p>
    <form>
      <input type="email" placeholder="tu@email.com">
      <button>Suscribirse</button>
    </form>
  </div>
</div>
```

### 3. **AdminView** - Panel (sin cambios en estructura)
```html
<div id="adminView" class="view hidden">
  <!-- Tabs: Posts, Comentarios, Newsletter, Publicidad -->
  <!-- Misma funcionalidad, nuevo diseño responsive -->
</div>
```

---

## 🎨 **CSS: Estructura Modular**

### `base.css` - Variables y reset
```css
:root {
  --primary: #6366f1;
  --secondary: #0f1419;
  --text: #f1f5f9;
  --text-light: #94a3b8;
  --border: #334155;
  --spacing-xs: 0.5rem;
  --spacing-sm: 1rem;
  --spacing-md: 1.5rem;
  --spacing-lg: 2rem;
  --spacing-xl: 3rem;
  --radius: 12px;
  --radius-lg: 16px;
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: 'Inter', sans-serif;
  background: var(--secondary);
  color: var(--text);
  line-height: 1.6;
}
```

### `layout.css` - Componentes
```css
/* Header/Navbar */
.navbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-md);
  background: rgba(15, 20, 25, 0.8);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  z-index: 100;
}

/* Posts Grid */
.posts-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: var(--spacing-lg);
  margin: var(--spacing-xl) 0;
}

/* Post Card */
.post-card {
  background: rgba(26, 31, 46, 0.8);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
  transition: all 0.3s ease;
  cursor: pointer;
}

.post-card:hover {
  transform: translateY(-4px);
  border-color: var(--primary);
  box-shadow: 0 20px 40px rgba(99, 102, 241, 0.15);
}

.post-card-image {
  width: 100%;
  height: 200px;
  object-fit: cover;
  background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
}

.post-card-body {
  padding: var(--spacing-md);
}

.post-card-title {
  font-size: 1.25rem;
  font-weight: 600;
  margin-bottom: var(--spacing-sm);
  color: var(--text);
}

.post-card-meta {
  font-size: 0.875rem;
  color: var(--text-light);
  margin-bottom: var(--spacing-md);
  display: flex;
  gap: var(--spacing-sm);
}

.post-card-description {
  font-size: 0.95rem;
  color: var(--text-light);
  line-height: 1.5;
}

/* Article (Post Dedicado) */
.post-article {
  max-width: 800px;
  margin: 0 auto;
  padding: var(--spacing-xl);
}

.post-title {
  font-size: 2.5rem;
  font-weight: 700;
  margin: var(--spacing-xl) 0 var(--spacing-md) 0;
}

.post-featured-image {
  width: 100%;
  max-height: 400px;
  object-fit: cover;
  border-radius: var(--radius-lg);
  margin: var(--spacing-xl) 0;
}

.post-content {
  font-size: 1.05rem;
  line-height: 1.8;
  color: var(--text);
  margin: var(--spacing-xl) 0;
}

.post-content p {
  margin-bottom: var(--spacing-md);
}

/* Comments Section */
.comments-section {
  margin-top: var(--spacing-xl);
  padding-top: var(--spacing-xl);
  border-top: 1px solid var(--border);
}

.comment-form {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-xl);
  padding: var(--spacing-md);
  background: rgba(26, 31, 46, 0.5);
  border-radius: var(--radius);
}

.comment-form input,
.comment-form textarea {
  padding: var(--spacing-sm);
  background: rgba(30, 41, 59, 0.8);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  color: var(--text);
  font-family: inherit;
}

.comment-form textarea {
  resize: vertical;
  min-height: 120px;
}

.comment-item {
  padding: var(--spacing-md);
  background: rgba(26, 31, 46, 0.5);
  border-radius: var(--radius);
  margin-bottom: var(--spacing-md);
}

.comment-meta {
  font-weight: 600;
  margin-bottom: var(--spacing-sm);
}

.comment-text {
  color: var(--text-light);
  margin-bottom: var(--spacing-sm);
}

.comment-actions {
  font-size: 0.875rem;
}

.comment-actions button {
  background: none;
  border: none;
  color: var(--primary);
  cursor: pointer;
  padding: 0.25rem 0.5rem;
}
```

### `responsive.css` - Mobile first
```css
/* Mobile (< 640px) */
@media (max-width: 639px) {
  .navbar {
    flex-direction: column;
    gap: var(--spacing-sm);
  }

  .posts-grid {
    grid-template-columns: 1fr;
    gap: var(--spacing-md);
  }

  .post-title {
    font-size: 1.75rem;
  }

  .post-article {
    padding: var(--spacing-md);
  }
}

/* Tablet (640px - 1024px) */
@media (min-width: 640px) and (max-width: 1023px) {
  .posts-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

/* Desktop (> 1024px) */
@media (min-width: 1024px) {
  .posts-grid {
    grid-template-columns: repeat(3, 1fr);
  }

  .post-article {
    padding: var(--spacing-xl) 0;
  }
}
```

---

## 📝 **JavaScript: Router con History API**

### `router.js`
```javascript
class Router {
  constructor() {
    this.routes = {
      '/': this.homePage.bind(this),
      '/admin': this.adminPage.bind(this),
      '/post/:slug': this.postPage.bind(this),
    };
    this.init();
  }

  init() {
    window.addEventListener('popstate', () => this.navigate(window.location.pathname));
    document.addEventListener('click', this.handleLinkClick.bind(this));
    this.navigate(window.location.pathname);
  }

  handleLinkClick(e) {
    if (e.target.tagName === 'A' && e.target.href.startsWith(window.location.origin)) {
      e.preventDefault();
      const path = new URL(e.target.href).pathname;
      this.navigate(path);
    }
  }

  navigate(path) {
    window.history.pushState({}, '', path);
    this.render(path);
  }

  render(path) {
    // Ocultar todas las vistas
    document.querySelectorAll('.view').forEach(v => v.classList.add('hidden'));

    // Determinar ruta
    if (path === '/') {
      this.homePage();
    } else if (path === '/admin') {
      this.adminPage();
    } else if (path.startsWith('/post/')) {
      const slug = path.split('/')[2];
      this.postPage(slug);
    }
  }

  homePage() {
    document.getElementById('homeView').classList.remove('hidden');
    app.loadPosts();
  }

  postPage(slug) {
    document.getElementById('postView').classList.remove('hidden');
    app.loadPostBySlug(slug);
  }

  adminPage() {
    document.getElementById('adminView').classList.remove('hidden');
    if (app.adminToken) {
      app.showView('admin');
    } else {
      app.showView('adminLogin');
    }
  }
}
```

---

## 📅 **Timeline**

| Día | Tarea |
|---|---|
| **Hoy** | Crear branch + Railway config |
| **Mañana** | Migración a Railway |
| **Día 3-4** | Implementar History API |
| **Día 5-6** | Crear nuevas vistas HTML |
| **Día 7-8** | CSS base + responsive |
| **Día 9** | Testing + ajustes |
| **Día 10** | Deploy a producción |

---

## ✅ **Checklist**

- [ ] Railway creado y funcionando
- [ ] Branch `redesign/foro-moderno` activo
- [ ] History API implementada
- [ ] Nuevas vistas HTML listas
- [ ] CSS modular aplicado
- [ ] Responsive testeado
- [ ] Admin funcional en nuevo diseño
- [ ] Deploy a producción
- [ ] Merge a `main`

