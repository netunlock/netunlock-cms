/**
 * NetUnlock API - Backend con Cloudflare Workers + D1
 * Gestiona posts, comentarios, newsletter y autenticación admin
 */

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;

    // CORS headers
    const corsHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    };

    // Preflight CORS
    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }

    try {
      // ============================================
      // RUTAS DE POSTS
      // ============================================

      // GET /api/posts - Obtener todos los posts
      if (path === '/api/posts' && request.method === 'GET') {
        const posts = await env.DB.prepare(
          `SELECT id, title, description, content, image_url, video_url, created_at, views
           FROM posts WHERE published = 1 ORDER BY created_at DESC`
        ).all();

        return new Response(JSON.stringify(posts.results), {
          headers: { 'Content-Type': 'application/json', ...corsHeaders }
        });
      }

      // GET /api/posts/:id - Obtener post específico
      if (path.match(/^\/api\/posts\/\d+$/) && request.method === 'GET') {
        const id = path.split('/').pop();
        const post = await env.DB.prepare(
          `SELECT * FROM posts WHERE id = ? AND published = 1`
        ).bind(id).first();

        if (!post) {
          return new Response(JSON.stringify({ error: 'Post no encontrado' }), {
            status: 404,
            headers: { 'Content-Type': 'application/json', ...corsHeaders }
          });
        }

        // Incrementar views
        await env.DB.prepare(
          `UPDATE posts SET views = views + 1 WHERE id = ?`
        ).bind(id).run();

        return new Response(JSON.stringify(post), {
          headers: { 'Content-Type': 'application/json', ...corsHeaders }
        });
      }

      // POST /api/posts - Crear nuevo post (solo admin)
      if (path === '/api/posts' && request.method === 'POST') {
        const auth = request.headers.get('Authorization');
        if (!auth || !auth.startsWith('Bearer ')) {
          return new Response(JSON.stringify({ error: 'No autorizado' }), {
            status: 401,
            headers: { 'Content-Type': 'application/json', ...corsHeaders }
          });
        }

        const token = auth.substring(7);
        if (!await verifyAdminToken(token, env)) {
          return new Response(JSON.stringify({ error: 'Token inválido' }), {
            status: 401,
            headers: { 'Content-Type': 'application/json', ...corsHeaders }
          });
        }

        const data = await request.json();
        const result = await env.DB.prepare(
          `INSERT INTO posts (title, description, content, image_url, video_url, published)
           VALUES (?, ?, ?, ?, ?, 1)`
        ).bind(data.title, data.description, data.content, data.image_url, data.video_url).run();

        return new Response(JSON.stringify({
          id: result.meta.last_row_id,
          message: 'Post creado exitosamente'
        }), {
          status: 201,
          headers: { 'Content-Type': 'application/json', ...corsHeaders }
        });
      }

      // PUT /api/posts/:id - Actualizar post (solo admin)
      if (path.match(/^\/api\/posts\/\d+$/) && request.method === 'PUT') {
        const auth = request.headers.get('Authorization');
        if (!auth || !auth.startsWith('Bearer ')) {
          return new Response(JSON.stringify({ error: 'No autorizado' }), {
            status: 401,
            headers: { 'Content-Type': 'application/json', ...corsHeaders }
          });
        }

        const token = auth.substring(7);
        if (!await verifyAdminToken(token, env)) {
          return new Response(JSON.stringify({ error: 'Token inválido' }), {
            status: 401,
            headers: { 'Content-Type': 'application/json', ...corsHeaders }
          });
        }

        const id = path.split('/').pop();
        const data = await request.json();

        await env.DB.prepare(
          `UPDATE posts SET title = ?, description = ?, content = ?, image_url = ?, video_url = ?
           WHERE id = ?`
        ).bind(data.title, data.description, data.content, data.image_url, data.video_url, id).run();

        return new Response(JSON.stringify({ message: 'Post actualizado' }), {
          headers: { 'Content-Type': 'application/json', ...corsHeaders }
        });
      }

      // DELETE /api/posts/:id - Eliminar post (solo admin)
      if (path.match(/^\/api\/posts\/\d+$/) && request.method === 'DELETE') {
        const auth = request.headers.get('Authorization');
        if (!auth || !auth.startsWith('Bearer ')) {
          return new Response(JSON.stringify({ error: 'No autorizado' }), {
            status: 401,
            headers: { 'Content-Type': 'application/json', ...corsHeaders }
          });
        }

        const token = auth.substring(7);
        if (!await verifyAdminToken(token, env)) {
          return new Response(JSON.stringify({ error: 'Token inválido' }), {
            status: 401,
            headers: { 'Content-Type': 'application/json', ...corsHeaders }
          });
        }

        const id = path.split('/').pop();
        await env.DB.prepare(`DELETE FROM posts WHERE id = ?`).bind(id).run();

        return new Response(JSON.stringify({ message: 'Post eliminado' }), {
          headers: { 'Content-Type': 'application/json', ...corsHeaders }
        });
      }

      // ============================================
      // RUTAS DE COMENTARIOS
      // ============================================

      // GET /api/posts/:id/comments - Obtener comentarios del post
      if (path.match(/^\/api\/posts\/\d+\/comments$/) && request.method === 'GET') {
        const postId = path.split('/')[3];
        const comments = await env.DB.prepare(
          `SELECT id, author_name, author_email, content, is_flagged, created_at
           FROM comments WHERE post_id = ? AND approved = 1 ORDER BY created_at DESC`
        ).bind(postId).all();

        return new Response(JSON.stringify(comments.results), {
          headers: { 'Content-Type': 'application/json', ...corsHeaders }
        });
      }

      // POST /api/posts/:id/comments - Crear comentario
      if (path.match(/^\/api\/posts\/\d+\/comments$/) && request.method === 'POST') {
        const postId = path.split('/')[3];
        const data = await request.json();

        // Validar
        if (!data.content || data.content.trim().length === 0) {
          return new Response(JSON.stringify({ error: 'Comentario vacío' }), {
            status: 400,
            headers: { 'Content-Type': 'application/json', ...corsHeaders }
          });
        }

        // Detectar spam (keywords sospechosas)
        const isFlagged = containsSpamKeywords(data.content);

        const result = await env.DB.prepare(
          `INSERT INTO comments (post_id, author_name, author_email, content, is_flagged, approved)
           VALUES (?, ?, ?, ?, ?, 1)`
        ).bind(
          postId,
          data.author_name || 'Anónimo',
          data.author_email || null,
          data.content,
          isFlagged ? 1 : 0
        ).run();

        return new Response(JSON.stringify({
          id: result.meta.last_row_id,
          message: isFlagged ? 'Comentario publicado (pendiente revisión)' : 'Comentario publicado',
          flagged: isFlagged
        }), {
          status: 201,
          headers: { 'Content-Type': 'application/json', ...corsHeaders }
        });
      }

      // DELETE /api/comments/:id - Eliminar comentario (solo admin)
      if (path.match(/^\/api\/comments\/\d+$/) && request.method === 'DELETE') {
        const auth = request.headers.get('Authorization');
        if (!auth || !await verifyAdminToken(auth.substring(7), env)) {
          return new Response(JSON.stringify({ error: 'No autorizado' }), {
            status: 401,
            headers: { 'Content-Type': 'application/json', ...corsHeaders }
          });
        }

        const id = path.split('/').pop();
        await env.DB.prepare(`DELETE FROM comments WHERE id = ?`).bind(id).run();

        return new Response(JSON.stringify({ message: 'Comentario eliminado' }), {
          headers: { 'Content-Type': 'application/json', ...corsHeaders }
        });
      }

      // ============================================
      // RUTAS DE NEWSLETTER
      // ============================================

      // POST /api/newsletter/subscribe - Suscribirse
      if (path === '/api/newsletter/subscribe' && request.method === 'POST') {
        const data = await request.json();

        if (!data.email || !data.email.includes('@')) {
          return new Response(JSON.stringify({ error: 'Email inválido' }), {
            status: 400,
            headers: { 'Content-Type': 'application/json', ...corsHeaders }
          });
        }

        try {
          await env.DB.prepare(
            `INSERT INTO newsletter (email, subscribed_at) VALUES (?, datetime('now'))`
          ).bind(data.email).run();

          return new Response(JSON.stringify({
            message: 'Suscripción confirmada. Recibirás actualizaciones pronto.'
          }), {
            headers: { 'Content-Type': 'application/json', ...corsHeaders }
          });
        } catch (err) {
          // Email ya existe
          return new Response(JSON.stringify({
            message: 'Ya estás suscrito a nuestro newsletter'
          }), {
            headers: { 'Content-Type': 'application/json', ...corsHeaders }
          });
        }
      }

      // POST /api/admin/login - Login admin
      if (path === '/api/admin/login' && request.method === 'POST') {
        const data = await request.json();

        if (data.password === env.ADMIN_PASSWORD) {
          const token = await generateAdminToken(env);
          return new Response(JSON.stringify({
            token,
            message: 'Login exitoso'
          }), {
            headers: { 'Content-Type': 'application/json', ...corsHeaders }
          });
        }

        return new Response(JSON.stringify({ error: 'Contraseña incorrecta' }), {
          status: 401,
          headers: { 'Content-Type': 'application/json', ...corsHeaders }
        });
      }

      // 404
      return new Response(JSON.stringify({ error: 'Ruta no encontrada' }), {
        status: 404,
        headers: { 'Content-Type': 'application/json', ...corsHeaders }
      });

    } catch (error) {
      console.error('Error:', error);
      return new Response(JSON.stringify({ error: error.message }), {
        status: 500,
        headers: { 'Content-Type': 'application/json', ...corsHeaders }
      });
    }
  },

  // Evento para inicializar base de datos
  async scheduled(event, env, ctx) {
    await initializeDatabase(env);
  }
};

/**
 * Inicializar base de datos con tablas
 */
async function initializeDatabase(env) {
  const statements = [
    `CREATE TABLE IF NOT EXISTS posts (
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
    )`,

    `CREATE TABLE IF NOT EXISTS comments (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      post_id INTEGER NOT NULL,
      author_name TEXT DEFAULT 'Anónimo',
      author_email TEXT,
      content TEXT NOT NULL,
      is_flagged INTEGER DEFAULT 0,
      approved INTEGER DEFAULT 0,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (post_id) REFERENCES posts(id)
    )`,

    `CREATE TABLE IF NOT EXISTS newsletter (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      email TEXT UNIQUE NOT NULL,
      subscribed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      unsubscribed INTEGER DEFAULT 0
    )`
  ];

  for (const statement of statements) {
    await env.DB.prepare(statement).run();
  }
}

/**
 * Verificar token de admin (simple, en producción usar JWT)
 */
async function verifyAdminToken(token, env) {
  // En producción, deberías usar JWT real
  // Por ahora, almacenamos tokens en KV
  const stored = await env.KV?.get(`admin_token:${token}`);
  return stored !== null;
}

/**
 * Generar token de admin
 */
async function generateAdminToken(env) {
  const token = crypto.getRandomValues(new Uint8Array(32)).toString();
  // Guardarlo por 24 horas
  if (env.KV) {
    await env.KV.put(`admin_token:${token}`, 'true', { expirationTtl: 86400 });
  }
  return token;
}

/**
 * Detectar spam en comentarios
 */
function containsSpamKeywords(text) {
  const spamKeywords = [
    'viagra', 'casino', 'poker', 'lottery',
    'click here', 'buy now', 'free money',
    'http://', 'https://', // links sospechosos
    'bit.ly', 'tinyurl'
  ];

  const lowerText = text.toLowerCase();
  return spamKeywords.some(keyword => lowerText.includes(keyword));
}
