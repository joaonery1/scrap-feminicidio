package storage

import (
	"context"
	"fmt"
	"net"
	"time"

	"github.com/jackc/pgx/v5"
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

	// Resolve hostname to IPv4 to avoid IPv6 issues on GitHub Actions runners.
	host := cfg.ConnConfig.Host
	addrs, err := net.DefaultResolver.LookupHost(ctx, host)
	if err != nil {
		return nil, fmt.Errorf("dns lookup %s: %w", host, err)
	}
	for _, a := range addrs {
		if ip := net.ParseIP(a); ip != nil && ip.To4() != nil {
			cfg.ConnConfig.Host = a
			break
		}
	}

	// PgBouncer (Supabase pooler) não suporta prepared statements entre conexões.
	// Simple protocol desabilita o cache de prepared statements.
	cfg.ConnConfig.DefaultQueryExecMode = pgx.QueryExecModeSimpleProtocol

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
