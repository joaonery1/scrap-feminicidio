package storage

import (
	"context"
	"fmt"
	"net"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

type RawRecord struct {
	Source      string
	URL         string
	Title       string
	Body        string
	PublishedAt *time.Time
}

type DB struct {
	pool *pgxpool.Pool
}

func New(ctx context.Context, dsn string) (*DB, error) {
	cfg, err := pgxpool.ParseConfig(dsn)
	if err != nil {
		return nil, fmt.Errorf("pgxpool.ParseConfig: %w", err)
	}
	cfg.ConnConfig.DialFunc = func(ctx context.Context, network, addr string) (net.Conn, error) {
		return (&net.Dialer{}).DialContext(ctx, "tcp4", addr)
	}
	pool, err := pgxpool.NewWithConfig(ctx, cfg)
	if err != nil {
		return nil, fmt.Errorf("pgxpool.New: %w", err)
	}
	if err := pool.Ping(ctx); err != nil {
		return nil, fmt.Errorf("db ping: %w", err)
	}
	return &DB{pool: pool}, nil
}

func (db *DB) Close() {
	db.pool.Close()
}

// Insert insere um registro em raw_records ignorando conflito de URL (ON CONFLICT DO NOTHING).
// Retorna true se o registro foi inserido (novo), false se já existia.
func (db *DB) Insert(ctx context.Context, r RawRecord) (bool, error) {
	tag, err := db.pool.Exec(ctx, `
		INSERT INTO raw_records (source, url, title, body, published_at)
		VALUES ($1, $2, $3, $4, $5)
		ON CONFLICT (url) DO NOTHING
	`, r.Source, r.URL, r.Title, r.Body, r.PublishedAt)
	if err != nil {
		return false, fmt.Errorf("insert raw_record: %w", err)
	}
	return tag.RowsAffected() == 1, nil
}
