package dados

import (
	"context"
	"encoding/csv"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/scrapshe/scrapers/internal/storage"
)

const (
	// URL do CSV em dados.gov.br — pode precisar de ajuste conforme o conjunto de dados atual.
	// Verificar em: https://dados.gov.br/dados/conjuntos-dados/violencia-contra-a-mulher
	csvURL = "https://dados.gov.br/dados/conjuntos-dados/violencia-contra-a-mulher"

	sourceName   = "dadosgovbr"
	httpTimeout  = 60 * time.Second
	maxRetries   = 1
	localFallback = "data/dados_govbr_cache.csv"
)

type Scraper struct {
	db     *storage.DB
	logger *slog.Logger
}

func New(db *storage.DB, logger *slog.Logger) *Scraper {
	return &Scraper{db: db, logger: logger}
}

// Run busca o CSV de violência contra a mulher de dados.gov.br,
// parseia e insere os registros em raw_records.
// Se o HTTP falhar, tenta fallback em data/dados_govbr_cache.csv.
func (s *Scraper) Run(ctx context.Context) (int, error) {
	reader, err := s.fetchCSV(ctx)
	if err != nil {
		s.logger.Warn("dadosgovbr: HTTP falhou, tentando fallback local",
			"path", localFallback,
			"err", err,
		)
		reader, err = s.readLocalFallback()
		if err != nil {
			return 0, fmt.Errorf("dadosgovbr: fallback local falhou: %w", err)
		}
	}
	if reader != nil {
		if closer, ok := reader.(io.Closer); ok {
			defer closer.Close()
		}
	}

	return s.parseAndInsert(ctx, reader)
}

// fetchCSV faz HTTP GET com timeout e 1 retry, retornando um io.Reader do CSV.
func (s *Scraper) fetchCSV(ctx context.Context) (io.Reader, error) {
	client := &http.Client{Timeout: httpTimeout}

	var (
		resp *http.Response
		err  error
	)

	for attempt := 0; attempt <= maxRetries; attempt++ {
		if attempt > 0 {
			backoff := time.Duration(1<<uint(attempt-1)) * time.Second
			s.logger.Warn("dadosgovbr: retrying HTTP GET", "attempt", attempt, "backoff", backoff)
			select {
			case <-ctx.Done():
				return nil, ctx.Err()
			case <-time.After(backoff):
			}
		}

		req, reqErr := http.NewRequestWithContext(ctx, http.MethodGet, csvURL, nil)
		if reqErr != nil {
			return nil, fmt.Errorf("build request: %w", reqErr)
		}
		req.Header.Set("User-Agent", "scrapshe/1.0")

		resp, err = client.Do(req)
		if err == nil && resp.StatusCode == http.StatusOK {
			break
		}
		if err == nil {
			resp.Body.Close()
			err = fmt.Errorf("HTTP status %d", resp.StatusCode)
		}
		s.logger.Error("dadosgovbr HTTP failed", "attempt", attempt, "err", err)
	}

	if err != nil {
		return nil, err
	}

	return resp.Body, nil
}

// readLocalFallback abre o CSV local de cache.
func (s *Scraper) readLocalFallback() (io.ReadCloser, error) {
	f, err := os.Open(localFallback)
	if err != nil {
		return nil, fmt.Errorf("open local fallback %s: %w", localFallback, err)
	}
	return f, nil
}

// parseAndInsert lê o CSV e insere registros no banco.
// Colunas esperadas: data, descricao, municipio.
func (s *Scraper) parseAndInsert(ctx context.Context, r io.Reader) (int, error) {
	cr := csv.NewReader(r)
	cr.LazyQuotes = true
	cr.TrimLeadingSpace = true

	// Lê cabeçalho
	header, err := cr.Read()
	if err != nil {
		return 0, fmt.Errorf("dadosgovbr: ler cabeçalho CSV: %w", err)
	}

	// Mapeia nomes de colunas para índices (case-insensitive)
	colIndex := make(map[string]int, len(header))
	for i, h := range header {
		colIndex[strings.ToLower(strings.TrimSpace(h))] = i
	}

	getField := func(row []string, name string) string {
		idx, ok := colIndex[name]
		if !ok || idx >= len(row) {
			return ""
		}
		return strings.TrimSpace(row[idx])
	}

	inserted := 0
	lineNum := 1

	for {
		select {
		case <-ctx.Done():
			return inserted, ctx.Err()
		default:
		}

		row, err := cr.Read()
		if err == io.EOF {
			break
		}
		if err != nil {
			s.logger.Warn("dadosgovbr: erro ao ler linha CSV", "line", lineNum, "err", err)
			lineNum++
			continue
		}
		lineNum++

		dataStr := getField(row, "data")
		descricao := getField(row, "descricao")
		municipio := getField(row, "municipio")

		if descricao == "" && municipio == "" {
			continue
		}

		title := descricao
		if municipio != "" {
			title = fmt.Sprintf("%s — %s", descricao, municipio)
		}

		// Gera URL sintética para garantir unicidade (sem URL real no CSV)
		url := fmt.Sprintf("dadosgovbr:%s:%s", dataStr, strings.ReplaceAll(title, " ", "_"))

		var publishedAt *time.Time
		for _, layout := range []string{"2006-01-02", "02/01/2006", "01/02/2006"} {
			if t, err := time.Parse(layout, dataStr); err == nil {
				publishedAt = &t
				break
			}
		}

		rec := storage.RawRecord{
			Source:      sourceName,
			URL:         url,
			Title:       title,
			Body:        descricao,
			PublishedAt: publishedAt,
		}

		ok, err := s.db.Insert(ctx, rec)
		if err != nil {
			s.logger.Error("dadosgovbr db insert", "title", title, "err", err)
			continue
		}
		if ok {
			inserted++
		}
	}

	if inserted == 0 {
		s.logger.Warn("dadosgovbr: 0 novos registros neste run — verificar estrutura do CSV ou URL de dados")
	}

	return inserted, nil
}
