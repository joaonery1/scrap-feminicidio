package instagram

import (
	"bufio"
	"context"
	"encoding/json"
	"log/slog"
	"os"
	"os/exec"
	"time"

	"github.com/scrapshe/scrapers/internal/storage"
)

const (
	sourceName   = "instagram"
	totalTimeout = 5 * time.Minute
)

type Scraper struct {
	db     *storage.DB
	logger *slog.Logger
}

func New(db *storage.DB, logger *slog.Logger) *Scraper {
	return &Scraper{db: db, logger: logger}
}

// igPost representa uma linha do arquivo JSONL gerado pelo instaloader.
type igPost struct {
	URL         string `json:"url"`
	Title       string `json:"title"`
	Body        string `json:"body"`
	PublishedAt string `json:"published_at"`
}

// Run executa o script Python instaloader_fetch.py via subprocess,
// lê o JSONL gerado e insere cada post em raw_records.
// Erros no subprocess são não-fatais: retorna 0, nil como fallback.
func (s *Scraper) Run(ctx context.Context) (int, error) {
	runCtx, cancel := context.WithTimeout(ctx, totalTimeout)
	defer cancel()

	outputFile := os.TempDir() + "/ig_posts.jsonl"

	cmd := exec.CommandContext(runCtx, "python3", "../scripts/instaloader_fetch.py", "--output", outputFile)
	cmd.Env = append(os.Environ(),
		"IG_SESSION_ID="+os.Getenv("IG_SESSION_ID"),
	)

	if out, err := cmd.CombinedOutput(); err != nil {
		s.logger.Warn("instagram subprocess failed — run manual como fallback",
			"err", err,
			"output", string(out),
		)
		return 0, nil
	}

	f, err := os.Open(outputFile)
	if err != nil {
		s.logger.Warn("instagram: não foi possível abrir output JSONL", "path", outputFile, "err", err)
		return 0, nil
	}
	defer f.Close()

	inserted := 0
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := scanner.Bytes()
		if len(line) == 0 {
			continue
		}

		var post igPost
		if err := json.Unmarshal(line, &post); err != nil {
			s.logger.Warn("instagram: falha ao parsear linha JSONL", "err", err)
			continue
		}

		var publishedAt *time.Time
		if post.PublishedAt != "" {
			if t, err := time.Parse(time.RFC3339, post.PublishedAt); err == nil {
				publishedAt = &t
			} else {
				s.logger.Warn("instagram: falha ao parsear published_at", "value", post.PublishedAt, "err", err)
			}
		}

		rec := storage.RawRecord{
			Source:      sourceName,
			URL:         post.URL,
			Title:       post.Title,
			Body:        post.Body,
			PublishedAt: publishedAt,
		}

		ok, err := s.db.Insert(ctx, rec)
		if err != nil {
			s.logger.Error("instagram db insert", "url", post.URL, "err", err)
			continue
		}
		if ok {
			inserted++
			s.logger.Info("instagram new record", "url", post.URL)
		}
	}

	if err := scanner.Err(); err != nil {
		s.logger.Warn("instagram: erro ao ler JSONL", "err", err)
	}

	return inserted, nil
}
