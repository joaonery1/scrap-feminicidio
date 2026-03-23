package sspse

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"html"
	"log/slog"
	"net/http"
	"regexp"
	"time"

	"github.com/scrapshe/scrapers/internal/storage"
)

const (
	apiURL     = "https://ssp.se.gov.br/Noticias/Consultar"
	detailBase = "https://ssp.se.gov.br"
	sourceName = "sspse"
	reqTimeout = 30 * time.Second
)

type apiRequest struct {
	TituloSubtitulo string      `json:"tituloSubtitulo"`
	Paginacao       paginacaoReq `json:"paginacao"`
}

type paginacaoReq struct {
	APartirDo  int `json:"aPartirDo"`
	Quantidade int `json:"quantidade"`
}

type apiResponse struct {
	Noticias []noticia `json:"noticias"`
}

type noticia struct {
	ID             int    `json:"id"`
	Titulo         string `json:"titulo"`
	URL            string `json:"url"`
	Subtitulo      string `json:"subtitulo"`
	Conteudo       string `json:"conteudo"`
	DataCadastro   string `json:"dataCadastro"`
}

var stripTags = regexp.MustCompile(`<[^>]+>`)

type Scraper struct {
	db     *storage.DB
	logger *slog.Logger
}

func New(db *storage.DB, logger *slog.Logger) *Scraper {
	return &Scraper{db: db, logger: logger}
}

// Run consulta a API do SSP-SE por notícias de feminicídio e insere em raw_records.
func (s *Scraper) Run(ctx context.Context) (int, error) {
	keywords := []string{"feminicidio", "feminicídio", "mulher morta", "violência doméstica"}

	inserted := 0
	for _, kw := range keywords {
		n, err := s.fetchAndInsert(ctx, kw)
		if err != nil {
			s.logger.Error("sspse fetch keyword", "keyword", kw, "err", err)
			continue
		}
		inserted += n
	}

	if inserted == 0 {
		s.logger.Warn("sspse: 0 novos registros neste run")
	}
	return inserted, nil
}

func (s *Scraper) fetchAndInsert(ctx context.Context, keyword string) (int, error) {
	reqBody, err := json.Marshal(apiRequest{
		TituloSubtitulo: keyword,
		Paginacao:       paginacaoReq{APartirDo: 0, Quantidade: 50},
	})
	if err != nil {
		return 0, err
	}

	httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost, apiURL, bytes.NewReader(reqBody))
	if err != nil {
		return 0, err
	}
	httpReq.Header.Set("Content-Type", "application/json; charset=UTF-8")
	httpReq.Header.Set("X-Requested-With", "XMLHttpRequest")
	httpReq.ContentLength = int64(len(reqBody))

	client := &http.Client{Timeout: reqTimeout}
	resp, err := client.Do(httpReq)
	if err != nil {
		return 0, fmt.Errorf("sspse HTTP: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return 0, fmt.Errorf("sspse HTTP status %d", resp.StatusCode)
	}

	var result apiResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return 0, fmt.Errorf("sspse JSON decode: %w", err)
	}

	inserted := 0
	for _, n := range result.Noticias {
		body := html.UnescapeString(stripTags.ReplaceAllString(n.Conteudo, " "))
		if len(body) > 2000 {
			body = body[:2000]
		}

		var publishedAt *time.Time
		if t, err := time.Parse("02/01/2006 15:04", n.DataCadastro); err == nil {
			publishedAt = &t
		}

		rec := storage.RawRecord{
			Source:      sourceName,
			URL:         detailBase + n.URL,
			Title:       html.UnescapeString(n.Titulo),
			Body:        body,
			PublishedAt: publishedAt,
		}
		ok, err := s.db.Insert(ctx, rec)
		if err != nil {
			s.logger.Error("sspse db insert", "url", rec.URL, "err", err)
			continue
		}
		if ok {
			inserted++
			s.logger.Info("sspse new record", "title", rec.Title)
		}
	}
	return inserted, nil
}
