package g1

import (
	"context"
	"encoding/xml"
	"fmt"
	"log/slog"
	"net/http"
	"strings"
	"time"

	"github.com/scrapshe/scrapers/internal/storage"
)

const (
	rssURL     = "https://g1.globo.com/rss/g1/se/"
	sourceName = "g1"
	reqTimeout = 30 * time.Second
)

var keywords = []string{
	"feminicídio", "feminicidio",
	"mulher morta", "mulher assassinada",
	"violência doméstica", "violencia domestica",
}

type rss struct {
	Channel struct {
		Items []rssItem `xml:"item"`
	} `xml:"channel"`
}

type rssItem struct {
	Title   string `xml:"title"`
	Link    string `xml:"link"`
	PubDate string `xml:"pubDate"`
	Desc    string `xml:"description"`
}

type Scraper struct {
	db     *storage.DB
	logger *slog.Logger
}

func New(db *storage.DB, logger *slog.Logger) *Scraper {
	return &Scraper{db: db, logger: logger}
}

// Run coleta o RSS do G1 SE, filtra por keywords e insere em raw_records.
func (s *Scraper) Run(ctx context.Context) (int, error) {
	client := &http.Client{Timeout: reqTimeout}
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, rssURL, nil)
	if err != nil {
		return 0, err
	}
	req.Header.Set("User-Agent", "Mozilla/5.0 (compatible; scrapshe/1.0)")

	resp, err := client.Do(req)
	if err != nil {
		return 0, fmt.Errorf("g1 RSS fetch: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return 0, fmt.Errorf("g1 RSS HTTP %d", resp.StatusCode)
	}

	var feed rss
	if err := xml.NewDecoder(resp.Body).Decode(&feed); err != nil {
		return 0, fmt.Errorf("g1 RSS decode: %w", err)
	}

	inserted := 0
	for _, item := range feed.Channel.Items {
		text := strings.ToLower(item.Title + " " + item.Desc)
		if !containsKeyword(text) {
			continue
		}

		var publishedAt *time.Time
		// RSS pubDate: "Mon, 22 Mar 2026 19:58:37 -0000"
		if t, err := time.Parse("Mon, 02 Jan 2006 15:04:05 -0700", item.PubDate); err == nil {
			publishedAt = &t
		}

		body := item.Desc
		if len(body) > 2000 {
			body = body[:2000]
		}

		rec := storage.RawRecord{
			Source:      sourceName,
			URL:         item.Link,
			Title:       item.Title,
			Body:        body,
			PublishedAt: publishedAt,
		}
		ok, err := s.db.Insert(ctx, rec)
		if err != nil {
			s.logger.Error("g1 db insert", "url", item.Link, "err", err)
			continue
		}
		if ok {
			inserted++
			s.logger.Info("g1 new record", "title", item.Title)
		}
	}

	if inserted == 0 {
		s.logger.Warn("g1: 0 novos registros neste run — sem notícias com keywords no RSS")
	}
	return inserted, nil
}

func containsKeyword(text string) bool {
	for _, kw := range keywords {
		if strings.Contains(text, kw) {
			return true
		}
	}
	return false
}
