package main

import (
	"context"
	"fmt"
	"log/slog"
	"os"
	"time"

	"github.com/joho/godotenv"
	"github.com/scrapshe/scrapers/internal/g1"
	"github.com/scrapshe/scrapers/internal/infonet"
	"github.com/scrapshe/scrapers/internal/instagram"
	"github.com/scrapshe/scrapers/internal/senoticias"
	"github.com/scrapshe/scrapers/internal/sspse"
	"github.com/scrapshe/scrapers/internal/storage"
	// "github.com/scrapshe/scrapers/internal/tjse" — desabilitado: principal.wsp é stateful demais
)

func main() {
	_ = godotenv.Load("../../.env")

	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
		Level: logLevel(),
	}))

	dsn := buildDSN()
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Minute)
	defer cancel()

	db, err := storage.New(ctx, dsn)
	if err != nil {
		logger.Error("db connect", "err", err)
		os.Exit(1)
	}
	defer db.Close()

	scrapers := []struct {
		name string
		run  func(context.Context) (int, error)
	}{
		{"sspse", sspse.New(db, logger.With("scraper", "sspse")).Run},
		{"g1", g1.New(db, logger.With("scraper", "g1")).Run},
		{"infonet", infonet.New(db, logger.With("scraper", "infonet")).Run},
		{"senoticias", senoticias.New(db, logger.With("scraper", "senoticias")).Run},
		{"instagram", instagram.New(db, logger.With("scraper", "instagram")).Run},
		// {"tjse", tjse.New(db, logger.With("scraper", "tjse")).Run}, — desabilitado
	}

	for _, s := range scrapers {
		start := time.Now()
		n, err := s.run(ctx)
		if err != nil {
			logger.Error("scraper failed", "scraper", s.name, "err", err)
			continue
		}
		logger.Info("scraper done", "scraper", s.name, "inserted", n, "elapsed", time.Since(start).String())
	}
}

func buildDSN() string {
	host := envOr("POSTGRES_HOST", "localhost")
	port := envOr("POSTGRES_PORT", "5433")
	db := envOr("POSTGRES_DB", "scrapshe")
	user := envOr("POSTGRES_USER", "scrapshe")
	pass := envOr("POSTGRES_PASSWORD", "changeme")
	return fmt.Sprintf("postgres://%s:%s@%s:%s/%s", user, pass, host, port, db)
}

func envOr(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func logLevel() slog.Level {
	switch os.Getenv("LOG_LEVEL") {
	case "debug":
		return slog.LevelDebug
	case "warn":
		return slog.LevelWarn
	case "error":
		return slog.LevelError
	default:
		return slog.LevelInfo
	}
}
