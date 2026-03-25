package tjse

import (
	"context"
	"fmt"
	"html"
	"io"
	"log/slog"
	"net/http"
	"net/http/cookiejar"
	"net/url"
	"regexp"
	"strings"
	"time"

	"github.com/scrapshe/scrapers/internal/storage"
	"golang.org/x/text/encoding/charmap"
	"golang.org/x/text/transform"
)

const (
	baseURL    = "https://www.tjse.jus.br/diario/internet"
	sourceName = "tjse"
	reqTimeout = 30 * time.Second
	// Janela de busca: últimos 60 dias para garantir cobertura sem sobrecarregar
	lookbackDays = 60
)

var (
	// verSecao('6648', 7, 1048)
	reVerSecao = regexp.MustCompile(`verSecao\('(\d+)',\s*(\d+),\s*(\d+)\)`)
	// Data da edição: (07 de Janeiro de 2026)
	reDataEdicao = regexp.MustCompile(`\((\d{2} de \w+ de \d{4})\)`)
	// Remove tags HTML
	reHTMLTag = regexp.MustCompile(`<[^>]+>`)
	// Espaços múltiplos
	reSpaces = regexp.MustCompile(`\s+`)
)

type secao struct {
	edicao  string
	caderno string
	secaoID string
	data    string // "07 de Janeiro de 2026"
	titulo  string
}

type Scraper struct {
	db     *storage.DB
	logger *slog.Logger
}

func New(db *storage.DB, logger *slog.Logger) *Scraper {
	return &Scraper{db: db, logger: logger}
}

func (s *Scraper) Run(ctx context.Context) (int, error) {
	jar, _ := cookiejar.New(nil)
	client := &http.Client{Timeout: reqTimeout, Jar: jar}

	secoes, err := s.buscarSecoes(ctx, client)
	if err != nil {
		return 0, fmt.Errorf("tjse buscarSecoes: %w", err)
	}
	s.logger.Info("tjse: seções encontradas", "total", len(secoes))

	inserted := 0
	for _, sec := range secoes {
		texto, err := s.buscarTexto(ctx, client, sec)
		if err != nil {
			s.logger.Warn("tjse: erro ao buscar texto", "edicao", sec.edicao, "secao", sec.secaoID, "err", err)
			continue
		}
		if texto == "" {
			continue
		}

		// URL canônica identificando a publicação
		pubURL := fmt.Sprintf("%s/inicial.wsp?tmp.diario.nu_edicao=%s&tmp.diario.cd_caderno=%s&tmp.diario.cd_secao=%s",
			baseURL, sec.edicao, sec.caderno, sec.secaoID)

		var publishedAt *time.Time
		if t := parseDataEdicao(sec.data); t != nil {
			publishedAt = t
		}

		title := fmt.Sprintf("DJE TJ-SE nº %s — %s — %s", sec.edicao, sec.data, sec.titulo)
		body := texto
		if len(body) > 2000 {
			body = body[:2000]
		}

		rec := storage.RawRecord{
			Source:      sourceName,
			URL:         pubURL,
			Title:       title,
			Body:        body,
			PublishedAt: publishedAt,
		}
		ok, err := s.db.Insert(ctx, rec)
		if err != nil {
			s.logger.Error("tjse db insert", "url", pubURL, "err", err)
			continue
		}
		if ok {
			inserted++
			s.logger.Info("tjse new record", "edicao", sec.edicao, "secao", sec.secaoID)
		}
	}

	if inserted == 0 {
		s.logger.Warn("tjse: 0 novos registros neste run")
	}
	return inserted, nil
}

// buscarSecoes faz POST em pesquisar.wsp e extrai os pares (edicao, caderno, secao).
func (s *Scraper) buscarSecoes(ctx context.Context, client *http.Client) ([]secao, error) {
	// 1. GET para obter o token de sessão
	getReq, err := http.NewRequestWithContext(ctx, http.MethodGet, baseURL+"/pesquisar.wsp", nil)
	if err != nil {
		return nil, err
	}
	getReq.Header.Set("User-Agent", "Mozilla/5.0 (compatible; scrapshe/1.0)")
	getResp, err := client.Do(getReq)
	if err != nil {
		return nil, fmt.Errorf("GET pesquisar: %w", err)
	}
	pageHTML, _ := readLatin1(getResp.Body)
	getResp.Body.Close()

	token := extractBetween(pageHTML, `wi.token" VALUE="`, `"`)

	// Janela de busca
	now := time.Now()
	dtFim := now.Format("02/01/2006")
	dtInicio := now.AddDate(0, 0, -lookbackDays).Format("02/01/2006")

	// 2. POST pesquisar.wsp
	formData := url.Values{
		"tmp_origem":           {""},
		"tmp.diario.dt_inicio": {dtInicio},
		"tmp.diario.dt_fim":    {dtFim},
		"tmp.diario.pal_chave": {"feminicidio"},
		"wi.token":             {token},
	}
	postReq, err := http.NewRequestWithContext(ctx, http.MethodPost,
		baseURL+"/pesquisar.wsp", strings.NewReader(formData.Encode()))
	if err != nil {
		return nil, err
	}
	postReq.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	postReq.Header.Set("User-Agent", "Mozilla/5.0 (compatible; scrapshe/1.0)")

	postResp, err := client.Do(postReq)
	if err != nil {
		return nil, fmt.Errorf("POST pesquisar: %w", err)
	}
	resultHTML, _ := readLatin1(postResp.Body)
	postResp.Body.Close()

	// 3. Extrair verSecao(edicao, caderno, secao) + data + título
	var secoes []secao
	// Percorre linha a linha para capturar data e título junto
	lines := strings.Split(resultHTML, "\n")
	for _, line := range lines {
		matches := reVerSecao.FindStringSubmatch(line)
		if matches == nil {
			continue
		}
		// Evitar duplicatas (cada resultado aparece duas vezes no HTML)
		if len(secoes) > 0 {
			last := secoes[len(secoes)-1]
			if last.edicao == matches[1] && last.secaoID == matches[3] {
				continue
			}
		}

		// Título da seção: texto visível na linha
		titulo := stripHTML(line)

		// Data da edição: buscar em linhas próximas
		data := ""
		if m := reDataEdicao.FindStringSubmatch(line); m != nil {
			data = m[1]
		}

		secoes = append(secoes, secao{
			edicao:  matches[1],
			caderno: matches[2],
			secaoID: matches[3],
			data:    data,
			titulo:  titulo,
		})
	}

	// Segunda passagem: preencher datas faltantes consultando contexto
	// (a data fica numa linha acima do verSecao)
	for i := range secoes {
		if secoes[i].data != "" {
			continue
		}
		// Procura pelo número da edição no HTML para extrair data próxima
		searchStr := fmt.Sprintf(">%s<", secoes[i].edicao)
		idx := strings.Index(resultHTML, searchStr)
		if idx < 0 {
			continue
		}
		chunk := resultHTML[max(0, idx-200):min(len(resultHTML), idx+300)]
		if m := reDataEdicao.FindStringSubmatch(chunk); m != nil {
			secoes[i].data = m[1]
		}
	}

	return secoes, nil
}

// buscarTexto faz POST em principal.wsp e retorna o texto limpo da publicação.
func (s *Scraper) buscarTexto(ctx context.Context, client *http.Client, sec secao) (string, error) {
	formData := url.Values{
		"tmp.diario.nu_edicao": {sec.edicao},
		"tmp.diario.cd_secao":  {sec.secaoID},
		"tmp.verintegra":       {"1"},
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost,
		baseURL+"/principal.wsp", strings.NewReader(formData.Encode()))
	if err != nil {
		return "", err
	}
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	req.Header.Set("User-Agent", "Mozilla/5.0 (compatible; scrapshe/1.0)")

	resp, err := client.Do(req)
	if err != nil {
		return "", err
	}
	raw, _ := readLatin1(resp.Body)
	resp.Body.Close()

	text := stripHTML(raw)
	text = html.UnescapeString(text)
	text = reSpaces.ReplaceAllString(text, " ")
	text = strings.TrimSpace(text)

	// Descartar se muito curto (página vazia / erro)
	if len(text) < 50 {
		return "", nil
	}

	// Extrair contexto ao redor da palavra "feminicid" em vez do início do doc.
	// Documentos do TJ-SE têm cabeçalhos longos; o termo relevante pode estar no meio.
	// Se a palavra não estiver no texto, o conteúdo é falso positivo — descartar.
	excerpt := extractKeywordContext(text, "feminicid", 600)
	if excerpt == "" {
		return "", nil
	}
	return excerpt, nil
}

// extractKeywordContext retorna uma janela de ±window/2 chars ao redor
// da primeira ocorrência de keyword (case-insensitive). Retorna "" se não encontrar.
func extractKeywordContext(text, keyword string, window int) string {
	lower := strings.ToLower(text)
	idx := strings.Index(lower, strings.ToLower(keyword))
	if idx < 0 {
		return ""
	}
	half := window / 2
	start := max(0, idx-half)
	end := min(len(text), idx+half)
	excerpt := strings.TrimSpace(text[start:end])
	// Indica ao leitor que é um trecho
	if start > 0 {
		excerpt = "..." + excerpt
	}
	if end < len(text) {
		excerpt = excerpt + "..."
	}
	return excerpt
}

// parseDataEdicao converte "07 de Janeiro de 2026" → *time.Time
func parseDataEdicao(s string) *time.Time {
	if s == "" {
		return nil
	}
	meses := map[string]string{
		"Janeiro": "01", "Fevereiro": "02", "Março": "03", "Abril": "04",
		"Maio": "05", "Junho": "06", "Julho": "07", "Agosto": "08",
		"Setembro": "09", "Outubro": "10", "Novembro": "11", "Dezembro": "12",
	}
	// "07 de Janeiro de 2026"
	parts := strings.Fields(s)
	if len(parts) != 5 {
		return nil
	}
	mes, ok := meses[parts[2]]
	if !ok {
		return nil
	}
	t, err := time.Parse("02/01/2006", fmt.Sprintf("%s/%s/%s", parts[0], mes, parts[4]))
	if err != nil {
		return nil
	}
	return &t
}

// readLatin1 lê o corpo da resposta e converte de ISO-8859-1 para UTF-8.
func readLatin1(r io.Reader) (string, error) {
	decoded := transform.NewReader(r, charmap.ISO8859_1.NewDecoder())
	b, err := io.ReadAll(decoded)
	if err != nil {
		return "", err
	}
	return string(b), nil
}

func stripHTML(s string) string {
	return strings.TrimSpace(reHTMLTag.ReplaceAllString(s, " "))
}

func extractBetween(s, start, end string) string {
	i := strings.Index(s, start)
	if i < 0 {
		return ""
	}
	i += len(start)
	j := strings.Index(s[i:], end)
	if j < 0 {
		return ""
	}
	return s[i : i+j]
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
