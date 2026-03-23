package scheduler

import (
	"context"
	"sync"
	"time"
)

// ScraperFunc é a assinatura comum de todos os scrapers.
type ScraperFunc func(ctx context.Context) (int, error)

// Result contém o resultado da execução de um scraper.
type Result struct {
	Name     string
	Inserted int
	Err      error
	Elapsed  time.Duration
}

// RunAll executa todos os scrapers em goroutines paralelas.
// Falha em um não interrompe os demais.
// Retorna slice de Results quando todos terminam ou ctx é cancelado.
func RunAll(ctx context.Context, scrapers map[string]ScraperFunc) []Result {
	results := make(chan Result, len(scrapers))

	var wg sync.WaitGroup
	for name, fn := range scrapers {
		wg.Add(1)
		go func(name string, fn ScraperFunc) {
			defer wg.Done()
			start := time.Now()
			n, err := fn(ctx)
			results <- Result{
				Name:     name,
				Inserted: n,
				Err:      err,
				Elapsed:  time.Since(start),
			}
		}(name, fn)
	}

	// Fecha o canal após todos terminarem
	go func() {
		wg.Wait()
		close(results)
	}()

	var out []Result
	for r := range results {
		out = append(out, r)
	}
	return out
}
