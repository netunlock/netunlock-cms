-- Inicialización de Base de Datos: NetUnlock CMS
-- Ejecutar con: wrangler d1 execute netunlock < init-db.sql

-- Tabla de Posts
CREATE TABLE IF NOT EXISTS posts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  description TEXT,
  content TEXT NOT NULL,
  image_url TEXT,
  video_url TEXT,
  published INTEGER DEFAULT 1,
  views INTEGER DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de Comentarios
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

-- Tabla de Newsletter
CREATE TABLE IF NOT EXISTS newsletter (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT UNIQUE NOT NULL,
  subscribed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  unsubscribed INTEGER DEFAULT 0
);

-- Índices para optimización de queries
CREATE INDEX IF NOT EXISTS idx_posts_published ON posts(published);
CREATE INDEX IF NOT EXISTS idx_posts_created_at ON posts(created_at);
CREATE INDEX IF NOT EXISTS idx_comments_post_id ON comments(post_id);
CREATE INDEX IF NOT EXISTS idx_comments_flagged ON comments(is_flagged);
CREATE INDEX IF NOT EXISTS idx_newsletter_email ON newsletter(email);

-- Datos de ejemplo (opcional - comentar si no quieres datos de prueba)
INSERT INTO posts (title, description, content, image_url, published, views)
VALUES (
  'Bienvenido a NetUnlock CMS',
  'Tu plataforma de gestión de contenidos profesional',
  'Este es tu primer post. Puedes editarlo o eliminarlo desde el panel de admin. Los posts pueden incluir imágenes, videos embebidos y aceptan comentarios de visitantes.',
  'https://via.placeholder.com/600x400?text=NetUnlock+CMS',
  1,
  1
);

-- Crear vistas útiles (opcional)
CREATE VIEW IF NOT EXISTS posts_stats AS
SELECT
  p.id,
  p.title,
  COUNT(c.id) as comment_count,
  SUM(CASE WHEN c.is_flagged = 1 THEN 1 ELSE 0 END) as flagged_comments,
  p.views,
  p.created_at
FROM posts p
LEFT JOIN comments c ON p.id = c.post_id
GROUP BY p.id;
