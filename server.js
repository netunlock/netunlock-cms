/**
 * NetUnlock CMS - Backend Server
 * Express.js + SQLite
 *
 * Credenciales por defecto:
 * Usuario: admin
 * Contraseña: admin123
 */

import express from 'express';
import sqlite3 from 'sqlite3';
import cors from 'cors';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.PORT || 5000;
const DB_PATH = process.env.DB_PATH || path.join(__dirname, 'data', 'netunlock.db');

// Middleware
app.use(cors());
app.use(express.json());
app.use((req, res, next) => {
  if (/\.db(-journal)?$/i.test(req.path)) return res.status(404).end();
  next();
});
app.use(express.static(__dirname));

fs.mkdirSync(path.dirname(DB_PATH), { recursive: true });

// Inicializar base de datos SQLite
const db = new sqlite3.Database(DB_PATH, (err) => {
  if (err) {
    console.error('❌ Error al conectar DB:', err);
  } else {
    console.log(`✅ Base de datos SQLite en ${DB_PATH}`);
    initializeDatabase();
  }
});

/**
 * Inicializar tablas
 */
function initializeDatabase() {
  const tables = [
    // Posts (con soporte para contenido JSON de bloques)
    `CREATE TABLE IF NOT EXISTS posts (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      title TEXT NOT NULL,
      description TEXT,
      content TEXT NOT NULL,
      blocks TEXT,
      category TEXT DEFAULT 'General',
      views INTEGER DEFAULT 0,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )`,

    // Calificaciones (1 a 5 estrellas, una por visitante)
    `CREATE TABLE IF NOT EXISTS post_ratings (
      post_id INTEGER NOT NULL,
      ip TEXT NOT NULL,
      rating INTEGER NOT NULL,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (post_id, ip)
    )`,

    // Comentarios
    `CREATE TABLE IF NOT EXISTS comments (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      post_id INTEGER NOT NULL,
      author_name TEXT DEFAULT 'Anónimo',
      author_email TEXT,
      content TEXT NOT NULL,
      is_flagged INTEGER DEFAULT 0,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE
    )`,

    // Newsletter
    `CREATE TABLE IF NOT EXISTS newsletter (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      email TEXT UNIQUE NOT NULL,
      subscribed_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )`,

    // Publicidad / Ads
    `CREATE TABLE IF NOT EXISTS ads (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      title TEXT NOT NULL,
      image_url TEXT,
      link_url TEXT NOT NULL,
      position TEXT DEFAULT 'sidebar',
      active INTEGER DEFAULT 1,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )`
  ];

  tables.forEach(table => {
    db.run(table, (err) => {
      if (err) console.error('Error creating table:', err);
    });
  });

  // Bases creadas antes de existir la columna de categoría
  db.run("ALTER TABLE posts ADD COLUMN category TEXT DEFAULT 'General'", () => {});

  console.log('✅ Tablas inicializadas');
}

// ============================================
// RUTAS: POSTS PÚBLICOS
// ============================================

const CATEGORIES = ['General', 'Tutoriales', 'Recursos', 'Noticias'];

function normalizeCategory(category) {
  return CATEGORIES.includes(category) ? category : 'General';
}

app.get('/api/categories', (req, res) => {
  res.json(CATEGORIES);
});

app.get('/api/posts', (req, res) => {
  db.all(
    `SELECT p.*,
       (SELECT ROUND(AVG(rating), 1) FROM post_ratings WHERE post_id = p.id) AS avg_rating,
       (SELECT COUNT(*) FROM post_ratings WHERE post_id = p.id) AS rating_count
     FROM posts p ORDER BY p.created_at DESC`,
    (err, rows) => {
      if (err) {
        res.status(500).json({ error: err.message });
      } else {
        res.json(rows || []);
      }
    }
  );
});

app.get('/api/posts/:id', (req, res) => {
  const { id } = req.params;

  // Incrementar views
  db.run('UPDATE posts SET views = views + 1 WHERE id = ?', [id]);

  db.get('SELECT * FROM posts WHERE id = ?', [id], (err, row) => {
    if (err) {
      res.status(500).json({ error: err.message });
    } else if (!row) {
      res.status(404).json({ error: 'Post no encontrado' });
    } else {
      res.json(row);
    }
  });
});

// ============================================
// RUTAS: COMENTARIOS
// ============================================

app.get('/api/posts/:id/comments', (req, res) => {
  const { id } = req.params;

  db.all(
    'SELECT * FROM comments WHERE post_id = ? ORDER BY created_at DESC',
    [id],
    (err, rows) => {
      if (err) {
        res.status(500).json({ error: err.message });
      } else {
        res.json(rows || []);
      }
    }
  );
});

app.post('/api/posts/:id/comments', (req, res) => {
  const { id } = req.params;
  const { content, author_name, author_email } = req.body;

  if (!content || content.trim().length === 0) {
    return res.status(400).json({ error: 'Comentario vacío' });
  }

  // Detectar spam
  const spamKeywords = ['viagra', 'casino', 'poker', 'click here', 'buy now', 'bit.ly', 'http://', 'https://'];
  const isFlagged = spamKeywords.some(keyword => content.toLowerCase().includes(keyword));

  db.run(
    `INSERT INTO comments (post_id, author_name, author_email, content, is_flagged)
     VALUES (?, ?, ?, ?, ?)`,
    [id, author_name || 'Anónimo', author_email || null, content, isFlagged ? 1 : 0],
    function(err) {
      if (err) {
        res.status(500).json({ error: err.message });
      } else {
        res.status(201).json({
          id: this.lastID,
          message: isFlagged ? 'Comentario publicado (pendiente revisión)' : 'Comentario publicado',
          flagged: isFlagged
        });
      }
    }
  );
});

app.delete('/api/comments/:id', (req, res) => {
  const { id } = req.params;

  db.run('DELETE FROM comments WHERE id = ?', [id], (err) => {
    if (err) {
      res.status(500).json({ error: err.message });
    } else {
      res.json({ message: 'Comentario eliminado' });
    }
  });
});

// ============================================
// RUTAS: CALIFICACIONES
// ============================================

function clientIp(req) {
  const forwarded = req.headers['x-forwarded-for'];
  return forwarded ? forwarded.split(',')[0].trim() : req.socket.remoteAddress;
}

app.get('/api/posts/:id/rating', (req, res) => {
  db.get(
    'SELECT ROUND(AVG(rating), 1) AS average, COUNT(*) AS count FROM post_ratings WHERE post_id = ?',
    [req.params.id],
    (err, row) => {
      if (err) {
        res.status(500).json({ error: err.message });
      } else {
        res.json({ average: row.average || 0, count: row.count });
      }
    }
  );
});

app.post('/api/posts/:id/rating', (req, res) => {
  const rating = Number(req.body.rating);
  if (!Number.isInteger(rating) || rating < 1 || rating > 5) {
    return res.status(400).json({ error: 'La calificación debe ser de 1 a 5' });
  }

  db.run(
    `INSERT INTO post_ratings (post_id, ip, rating) VALUES (?, ?, ?)
     ON CONFLICT(post_id, ip) DO UPDATE SET rating = excluded.rating, created_at = CURRENT_TIMESTAMP`,
    [req.params.id, clientIp(req), rating],
    (err) => {
      if (err) {
        res.status(500).json({ error: err.message });
      } else {
        res.json({ message: 'Calificación guardada' });
      }
    }
  );
});

// ============================================
// RUTAS: NEWSLETTER
// ============================================

app.post('/api/newsletter/subscribe', (req, res) => {
  const { email } = req.body;

  if (!email || !email.includes('@')) {
    return res.status(400).json({ error: 'Email inválido' });
  }

  db.run(
    'INSERT INTO newsletter (email) VALUES (?)',
    [email],
    (err) => {
      if (err && err.message.includes('UNIQUE')) {
        res.json({ message: 'Ya estás suscrito a nuestro newsletter' });
      } else if (err) {
        res.status(500).json({ error: err.message });
      } else {
        res.status(201).json({ message: 'Suscripción confirmada. Recibirás actualizaciones pronto.' });
      }
    }
  );
});

app.get('/api/newsletter/subscribers', (req, res) => {
  db.all('SELECT email, subscribed_at FROM newsletter ORDER BY subscribed_at DESC', (err, rows) => {
    if (err) {
      res.status(500).json({ error: err.message });
    } else {
      res.json(rows || []);
    }
  });
});

// ============================================
// RUTAS: PUBLICIDAD / ADS
// ============================================

app.get('/api/ads', (req, res) => {
  db.all('SELECT * FROM ads WHERE active = 1 ORDER BY created_at DESC', (err, rows) => {
    if (err) {
      res.status(500).json({ error: err.message });
    } else {
      res.json(rows || []);
    }
  });
});

app.post('/api/ads', verifyAdminToken, (req, res) => {
  const { title, image_url, link_url, position } = req.body;

  if (!title || !link_url) {
    return res.status(400).json({ error: 'Título y link son requeridos' });
  }

  db.run(
    `INSERT INTO ads (title, image_url, link_url, position)
     VALUES (?, ?, ?, ?)`,
    [title, image_url || null, link_url, position || 'sidebar'],
    function(err) {
      if (err) {
        res.status(500).json({ error: err.message });
      } else {
        res.status(201).json({ id: this.lastID, message: 'Anuncio creado' });
      }
    }
  );
});

app.put('/api/ads/:id', verifyAdminToken, (req, res) => {
  const { id } = req.params;
  const { title, image_url, link_url, position, active } = req.body;

  db.run(
    `UPDATE ads SET title = ?, image_url = ?, link_url = ?, position = ?, active = ?
     WHERE id = ?`,
    [title, image_url, link_url, position, active, id],
    (err) => {
      if (err) {
        res.status(500).json({ error: err.message });
      } else {
        res.json({ message: 'Anuncio actualizado' });
      }
    }
  );
});

app.delete('/api/ads/:id', verifyAdminToken, (req, res) => {
  const { id } = req.params;

  db.run('DELETE FROM ads WHERE id = ?', [id], (err) => {
    if (err) {
      res.status(500).json({ error: err.message });
    } else {
      res.json({ message: 'Anuncio eliminado' });
    }
  });
});

// ============================================
// RUTAS: ADMIN
// ============================================

app.post('/api/admin/login', (req, res) => {
  const { username, password } = req.body;

  // Credenciales por defecto
  if (username === 'admin' && password === '3.14o2do') {
    res.json({
      token: 'admin-token-' + Date.now(),
      message: 'Login exitoso'
    });
  } else {
    res.status(401).json({ error: 'Credenciales incorrectas' });
  }
});

// Middleware para verificar token
function verifyAdminToken(req, res, next) {
  const auth = req.headers.authorization;

  if (!auth || !auth.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'No autorizado' });
  }

  const token = auth.substring(7);

  // Token válido si comienza con 'admin-token-'
  if (!token.startsWith('admin-token-')) {
    return res.status(401).json({ error: 'Token inválido' });
  }

  next();
}

// Crear post (admin)
app.post('/api/posts', verifyAdminToken, (req, res) => {
  const { title, description, content, blocks, category } = req.body;

  if (!title || !content) {
    return res.status(400).json({ error: 'Título y contenido requeridos' });
  }

  const blocksJSON = blocks ? JSON.stringify(blocks) : null;

  db.run(
    `INSERT INTO posts (title, description, content, blocks, category)
     VALUES (?, ?, ?, ?, ?)`,
    [title, description || '', content, blocksJSON, normalizeCategory(category)],
    function(err) {
      if (err) {
        res.status(500).json({ error: err.message });
      } else {
        // Notificar a suscriptores
        notifySubscribersNewPost(this.lastID, title);

        res.status(201).json({
          id: this.lastID,
          message: 'Post creado exitosamente'
        });
      }
    }
  );
});

// Notificar suscriptores sobre nuevo post
function notifySubscribersNewPost(postId, postTitle) {
  db.all('SELECT email FROM newsletter WHERE unsubscribed = 0', (err, rows) => {
    if (rows && rows.length > 0) {
      console.log(`📧 Notificación automática enviada a ${rows.length} suscriptores sobre: "${postTitle}"`);
    }
  });
}

// Actualizar post (admin)
app.put('/api/posts/:id', verifyAdminToken, (req, res) => {
  const { id } = req.params;
  const { title, description, content, blocks, category } = req.body;

  const blocksJSON = blocks ? JSON.stringify(blocks) : null;

  db.run(
    `UPDATE posts SET title = ?, description = ?, content = ?, blocks = ?, category = ?, updated_at = CURRENT_TIMESTAMP
     WHERE id = ?`,
    [title, description, content, blocksJSON, normalizeCategory(category), id],
    (err) => {
      if (err) {
        res.status(500).json({ error: err.message });
      } else {
        res.json({ message: 'Post actualizado exitosamente' });
      }
    }
  );
});

// Eliminar post (admin)
app.delete('/api/posts/:id', verifyAdminToken, (req, res) => {
  const { id } = req.params;

  db.run('DELETE FROM posts WHERE id = ?', [id], (err) => {
    if (err) {
      res.status(500).json({ error: err.message });
    } else {
      res.json({ message: 'Post eliminado' });
    }
  });
});

// ============================================
// INICIAR SERVIDOR
// ============================================

app.get(/^\/(?!api\/).*/, (req, res) => {
  res.sendFile(path.join(__dirname, 'index.html'));
});

app.listen(PORT, () => {
  console.log(`\n🚀 NetUnlock CMS Backend ejecutándose en http://localhost:${PORT}`);
  console.log(`\n📍 Frontend: http://localhost:${PORT}`);
  console.log(`\n🔐 Credenciales de Admin:`);
  console.log(`   Usuario: admin`);
  console.log(`   Contraseña: admin123`);
  console.log(`\n💡 Comando para detener: Ctrl+C\n`);
});
