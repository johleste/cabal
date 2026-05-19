// CabalAdapter (Go) — Python/Java ↔ Go translation, Go execution, and HTTP endpoint interaction.
//
// Commands:
//
//	py2go   <file.py>   [-o out.go]      Translate Python to Go
//	go2py   <file.go>   [-o out.py]      Translate Go to Python
//	java2go <file.java> [-o out.go]      Translate Java to Go
//	go2java <file.go>   [-o out.java]    Translate Go to Java
//	run     <file.go>   [-- args...]     Compile and run a Go file
//	build   <file.go>   [-o binary]      Compile Go to a binary
//	call    <url>       [METHOD] [body]  HTTP call to an endpoint
//	probe   <url>                        Probe endpoint reachability and headers
//	help                                 Show this help
//
// Translation uses the local Ollama instance (deepseek-coder-v2).
// Set OLLAMA_BASE_URL to override (default: http://localhost:11434).
// Set GOBIN or GOROOT to override Go toolchain location.
package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strings"
	"time"
)

var (
	ollamaBase = envOr("OLLAMA_BASE_URL", "http://localhost:11434")
	coderModel = "deepseek-coder-v2:latest"
	httpClient = &http.Client{Timeout: 30 * time.Second}
)

func main() {
	if len(os.Args) < 2 {
		printHelp()
		os.Exit(1)
	}
	var err error
	switch os.Args[1] {
	case "py2go":
		err = translate(os.Args[2:], "Python", "Go", "py", "go")
	case "go2py":
		err = translate(os.Args[2:], "Go", "Python", "go", "py")
	case "java2go":
		err = translate(os.Args[2:], "Java", "Go", "java", "go")
	case "go2java":
		err = translate(os.Args[2:], "Go", "Java", "go", "java")
	case "run":
		err = runGo(os.Args[2:])
	case "build":
		err = buildGo(os.Args[2:])
	case "call":
		err = callEndpoint(os.Args[2:])
	case "probe":
		err = probeEndpoint(os.Args[2:])
	case "help", "--help", "-h":
		printHelp()
	default:
		fmt.Fprintf(os.Stderr, "unknown command: %s\n\n", os.Args[1])
		printHelp()
		os.Exit(1)
	}
	if err != nil {
		fmt.Fprintln(os.Stderr, "[go-adapter] error:", err)
		os.Exit(1)
	}
}

// ── Translation ───────────────────────────────────────────────────────────────

func translate(args []string, srcLang, dstLang, srcExt, dstExt string) error {
	if len(args) < 1 {
		return fmt.Errorf("usage: go-adapter %s2%s <file.%s> [-o out.%s]",
			strings.ToLower(srcLang), strings.ToLower(dstLang), srcExt, dstExt)
	}
	src := args[0]
	code, err := os.ReadFile(src)
	if err != nil {
		return fmt.Errorf("reading %s: %w", src, err)
	}

	prompt := fmt.Sprintf(
		"Translate the following %s code to idiomatic %s.\n"+
			"Output ONLY the %s code in a single fenced block. No explanation.\n\n"+
			"%s:\n```%s\n%s\n```",
		srcLang, dstLang, dstLang, srcLang, strings.ToLower(srcLang), string(code),
	)

	fmt.Fprintf(os.Stderr, "[go-adapter] translating %s → %s: %s\n", srcLang, dstLang, src)
	fmt.Fprintf(os.Stderr, "[go-adapter] calling %s via Ollama...\n", coderModel)

	result, err := ollamaQuery(prompt)
	if err != nil {
		return err
	}
	result = stripFence(result)

	out := flagVal(args[1:], "-o")
	if out != "" {
		if err := os.WriteFile(out, []byte(result+"\n"), 0644); err != nil {
			return fmt.Errorf("writing output: %w", err)
		}
		fmt.Fprintf(os.Stderr, "[go-adapter] written to %s\n", out)
	} else {
		fmt.Println(result)
	}
	return nil
}

// ── Go execution ──────────────────────────────────────────────────────────────

func runGo(args []string) error {
	if len(args) < 1 {
		return fmt.Errorf("usage: go-adapter run <file.go> [-- args...]")
	}
	gobin, err := findGo()
	if err != nil {
		return err
	}
	file := args[0]
	// Args after -- are passed to the program
	progArgs := []string{}
	for i, a := range args[1:] {
		if a == "--" {
			progArgs = args[i+2:]
			break
		}
	}
	fmt.Fprintf(os.Stderr, "[go-adapter] go run %s\n", file)
	cmd := exec.Command(gobin, append([]string{"run", file}, progArgs...)...)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.Env = parentEnv()
	return cmd.Run()
}

func buildGo(args []string) error {
	if len(args) < 1 {
		return fmt.Errorf("usage: go-adapter build <file.go> [-o binary]")
	}
	gobin, err := findGo()
	if err != nil {
		return err
	}
	file := args[0]
	out := flagVal(args[1:], "-o")
	if out == "" {
		base := strings.TrimSuffix(filepath.Base(file), ".go")
		out = filepath.Join(".", base)
	}
	fmt.Fprintf(os.Stderr, "[go-adapter] go build %s → %s\n", file, out)
	cmd := exec.Command(gobin, "build", "-o", out, file)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.Env = parentEnv()
	if err := cmd.Run(); err != nil {
		return err
	}
	fmt.Fprintf(os.Stderr, "[go-adapter] built: %s\n", out)
	return nil
}

// ── HTTP ──────────────────────────────────────────────────────────────────────

func callEndpoint(args []string) error {
	if len(args) < 1 {
		return fmt.Errorf("usage: go-adapter call <url> [GET|POST|PUT|DELETE|PATCH] [json_body]")
	}
	url := args[0]
	method := "GET"
	body := ""
	if len(args) > 1 {
		method = strings.ToUpper(args[1])
	}
	if len(args) > 2 {
		body = args[2]
	}
	fmt.Fprintf(os.Stderr, "[go-adapter] %s %s\n", method, url)

	var bodyReader io.Reader
	if body != "" {
		bodyReader = strings.NewReader(body)
	}
	req, err := http.NewRequest(method, url, bodyReader)
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")

	resp, err := httpClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	fmt.Printf("status: %d %s\n", resp.StatusCode, resp.Status)
	for k, v := range resp.Header {
		fmt.Printf("%s: %s\n", k, strings.Join(v, ", "))
	}
	fmt.Println()
	respBody, _ := io.ReadAll(resp.Body)
	fmt.Println(string(respBody))
	return nil
}

func probeEndpoint(args []string) error {
	if len(args) < 1 {
		return fmt.Errorf("usage: go-adapter probe <url>")
	}
	url := args[0]
	fmt.Fprintf(os.Stderr, "[go-adapter] probing %s\n", url)

	client := &http.Client{Timeout: 10 * time.Second}
	for _, method := range []string{"OPTIONS", "GET"} {
		req, err := http.NewRequest(method, url, nil)
		if err != nil {
			return err
		}
		resp, err := client.Do(req)
		if err != nil {
			if method == "GET" {
				fmt.Printf("reachable : false\nerror     : %s\n", err)
				return nil
			}
			continue
		}
		defer resp.Body.Close()
		fmt.Printf("reachable : true\nmethod    : %s\nstatus    : %d %s\nheaders   :\n", method, resp.StatusCode, resp.Status)
		for k, v := range resp.Header {
			fmt.Printf("  %s: %s\n", k, strings.Join(v, ", "))
		}
		respBody, _ := io.ReadAll(io.LimitReader(resp.Body, 512))
		if len(bytes.TrimSpace(respBody)) > 0 {
			fmt.Printf("body      :\n  %s\n", strings.ReplaceAll(string(respBody), "\n", "\n  "))
		}
		return nil
	}
	return nil
}

// ── Ollama ────────────────────────────────────────────────────────────────────

type ollamaReq struct {
	Model  string `json:"model"`
	Prompt string `json:"prompt"`
	Stream bool   `json:"stream"`
}

type ollamaResp struct {
	Response string `json:"response"`
}

func ollamaQuery(prompt string) (string, error) {
	payload, err := json.Marshal(ollamaReq{Model: coderModel, Prompt: prompt, Stream: false})
	if err != nil {
		return "", err
	}
	client := &http.Client{Timeout: 10 * time.Minute}
	resp, err := client.Post(ollamaBase+"/api/generate", "application/json", bytes.NewReader(payload))
	if err != nil {
		return "", fmt.Errorf("ollama unreachable: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		body, _ := io.ReadAll(resp.Body)
		return "", fmt.Errorf("ollama error %d: %s", resp.StatusCode, body)
	}
	var result ollamaResp
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return "", fmt.Errorf("parsing ollama response: %w", err)
	}
	return result.Response, nil
}

// ── Helpers ───────────────────────────────────────────────────────────────────

var fenceRe = regexp.MustCompile("(?s)^```\\w*\\n?|\\n?```\\s*$")

func stripFence(s string) string {
	return strings.TrimSpace(fenceRe.ReplaceAllString(strings.TrimSpace(s), ""))
}

func flagVal(args []string, flag string) string {
	for i := 0; i < len(args)-1; i++ {
		if args[i] == flag {
			return args[i+1]
		}
	}
	return ""
}

func findGo() (string, error) {
	// Respect explicit override
	if g := os.Getenv("GOBIN"); g != "" {
		return g, nil
	}
	// Search well-known install paths (not system PATH — it may be restricted)
	candidates := []string{
		"/usr/local/go/bin/go",
		"/usr/bin/go",
		"/opt/go/bin/go",
		"/snap/bin/go",
	}
	if goroot := os.Getenv("GOROOT"); goroot != "" {
		candidates = append([]string{filepath.Join(goroot, "bin", "go")}, candidates...)
	}
	for _, p := range candidates {
		if _, err := os.Stat(p); err == nil {
			return p, nil
		}
	}
	return "", fmt.Errorf("go toolchain not found; set GOROOT or GOBIN, or symlink go into tools/")
}

// parentEnv returns the process environment with PATH restored to the real
// system PATH so go run / go build can find the standard library and toolchain.
func parentEnv() []string {
	env := os.Environ()
	for i, e := range env {
		if strings.HasPrefix(e, "PATH=") {
			// Replace restricted PATH with real system fallback
			env[i] = "PATH=/usr/local/go/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
			return env
		}
	}
	return append(env, "PATH=/usr/local/go/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin")
}

func envOr(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

func printHelp() {
	fmt.Print(`go-adapter — Python/Java ↔ Go translation, Go execution, and endpoint interaction

Usage:
  go-adapter py2go   <file.py>   [-o out.go]      Translate Python to Go
  go-adapter go2py   <file.go>   [-o out.py]      Translate Go to Python
  go-adapter java2go <file.java> [-o out.go]      Translate Java to Go
  go-adapter go2java <file.go>   [-o out.java]    Translate Go to Java
  go-adapter run     <file.go>   [-- args...]     Compile and run a Go file
  go-adapter build   <file.go>   [-o binary]      Compile Go to a binary
  go-adapter call    <url>       [METHOD] [body]  HTTP call to an endpoint
  go-adapter probe   <url>                        Probe endpoint reachability
  go-adapter help                                 Show this help

Translation uses the local Ollama instance (deepseek-coder-v2).
  OLLAMA_BASE_URL  override Ollama endpoint  (default: http://localhost:11434)
  GOROOT / GOBIN   override Go toolchain location

Examples:
  go-adapter py2go   scanner.py   -o Scanner.go
  go-adapter java2go Parser.java  -o parser.go
  go-adapter run     exploit.go   -- --target 10.0.0.1
  go-adapter build   tool.go      -o tools/Network/tool
  go-adapter call    http://localhost:8080/api/health
  go-adapter probe   http://localhost:9090
`)
}
