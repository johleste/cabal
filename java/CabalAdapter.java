import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * CabalAdapter — Python ↔ Java translation and Java endpoint interaction.
 *
 * Commands:
 *   py2java <file.py> [-o out.java]     Translate Python to Java via Ollama
 *   java2py <file.java> [-o out.py]     Translate Java to Python via Ollama
 *   call <url> [METHOD] [json_body]     HTTP call to a Java endpoint
 *   probe <url>                         Probe a Java endpoint for reachability and headers
 *   help                                Print this help
 *
 * Translation uses the local Ollama instance (deepseek-coder-v2).
 * HTTP operations use Java's built-in HttpClient — no external dependencies.
 */
public class CabalAdapter {

    static final String OLLAMA_URL  = System.getenv().getOrDefault("OLLAMA_BASE_URL", "http://localhost:11434") + "/api/generate";
    static final String CODER_MODEL = "deepseek-coder-v2:latest";

    static final HttpClient HTTP = HttpClient.newBuilder()
        .connectTimeout(Duration.ofSeconds(15))
        .followRedirects(HttpClient.Redirect.NORMAL)
        .build();

    // ── Entry point ────────────────────────────────────────────────────────────

    public static void main(String[] args) throws Exception {
        if (args.length == 0) { printHelp(); System.exit(1); }
        switch (args[0]) {
            case "py2java" -> py2java(args);
            case "java2py" -> java2py(args);
            case "call"    -> call(args);
            case "probe"   -> probe(args);
            case "help", "--help", "-h" -> printHelp();
            default -> { System.err.println("Unknown command: " + args[0]); printHelp(); System.exit(1); }
        }
    }

    // ── Translation ────────────────────────────────────────────────────────────

    static void py2java(String[] args) throws Exception {
        if (args.length < 2) { System.err.println("Usage: adapter py2java <file.py> [-o out.java]"); System.exit(1); }
        String source = readFile(args[1]);
        String prompt =
            "Translate the following Python code to idiomatic Java.\n" +
            "Output ONLY the Java code in a single fenced block. No explanation.\n\n" +
            "Python:\n```python\n" + source + "\n```";
        String result = translate(prompt, "Python → Java", args[1]);
        writeOrPrint(result, args, "-o");
    }

    static void java2py(String[] args) throws Exception {
        if (args.length < 2) { System.err.println("Usage: adapter java2py <file.java> [-o out.py]"); System.exit(1); }
        String source = readFile(args[1]);
        String prompt =
            "Translate the following Java code to idiomatic Python 3.\n" +
            "Output ONLY the Python code in a single fenced block. No explanation.\n\n" +
            "Java:\n```java\n" + source + "\n```";
        String result = translate(prompt, "Java → Python", args[1]);
        writeOrPrint(result, args, "-o");
    }

    static String translate(String prompt, String label, String srcFile) throws Exception {
        System.err.println("[adapter] translating " + label + ": " + srcFile);
        System.err.println("[adapter] calling " + CODER_MODEL + " via Ollama...");
        String raw = ollamaQuery(prompt);
        return stripFence(raw);
    }

    // ── HTTP call ─────────────────────────────────────────────────────────────

    static void call(String[] args) throws Exception {
        if (args.length < 2) {
            System.err.println("Usage: adapter call <url> [GET|POST|PUT|DELETE|PATCH] [json_body]");
            System.exit(1);
        }
        String url    = args[1];
        String method = args.length > 2 ? args[2].toUpperCase() : "GET";
        String body   = args.length > 3 ? args[3] : "";

        System.err.println("[adapter] " + method + " " + url);

        HttpRequest.Builder builder = HttpRequest.newBuilder()
            .uri(URI.create(url))
            .timeout(Duration.ofSeconds(30))
            .header("Content-Type", "application/json")
            .header("Accept", "application/json");

        HttpRequest request = switch (method) {
            case "POST"  -> builder.POST(HttpRequest.BodyPublishers.ofString(body)).build();
            case "PUT"   -> builder.PUT(HttpRequest.BodyPublishers.ofString(body)).build();
            case "PATCH" -> builder.method("PATCH", HttpRequest.BodyPublishers.ofString(body)).build();
            case "DELETE"-> builder.DELETE().build();
            default      -> builder.GET().build();
        };

        HttpResponse<String> resp = HTTP.send(request, HttpResponse.BodyHandlers.ofString());
        System.out.println("status: " + resp.statusCode());
        resp.headers().map().forEach((k, v) -> System.out.println(k + ": " + String.join(", ", v)));
        System.out.println();
        System.out.println(resp.body());
    }

    // ── Probe ─────────────────────────────────────────────────────────────────

    static void probe(String[] args) throws Exception {
        if (args.length < 2) { System.err.println("Usage: adapter probe <url>"); System.exit(1); }
        String url = args[1];
        System.err.println("[adapter] probing " + url);

        // Try OPTIONS first (returns allowed methods), fall back to GET
        for (String method : new String[]{"OPTIONS", "GET"}) {
            try {
                HttpRequest req = HttpRequest.newBuilder()
                    .uri(URI.create(url))
                    .timeout(Duration.ofSeconds(10))
                    .method(method, HttpRequest.BodyPublishers.noBody())
                    .build();
                HttpResponse<String> resp = HTTP.send(req, HttpResponse.BodyHandlers.ofString());
                System.out.println("reachable : true");
                System.out.println("method    : " + method);
                System.out.println("status    : " + resp.statusCode());
                System.out.println("headers   :");
                resp.headers().map().forEach((k, v) ->
                    System.out.println("  " + k + ": " + String.join(", ", v)));
                String body = resp.body();
                if (body != null && !body.isBlank()) {
                    String snippet = body.length() > 500 ? body.substring(0, 500) + "..." : body;
                    System.out.println("body      :");
                    System.out.println("  " + snippet.replace("\n", "\n  "));
                }
                return;
            } catch (IOException e) {
                if (method.equals("GET")) {
                    System.out.println("reachable : false");
                    System.out.println("error     : " + e.getMessage());
                }
            }
        }
    }

    // ── Ollama ────────────────────────────────────────────────────────────────

    static String ollamaQuery(String prompt) throws Exception {
        String json = "{\"model\":" + jsonStr(CODER_MODEL) +
                      ",\"prompt\":" + jsonStr(prompt) +
                      ",\"stream\":false}";

        HttpRequest req = HttpRequest.newBuilder()
            .uri(URI.create(OLLAMA_URL))
            .timeout(Duration.ofMinutes(10))
            .header("Content-Type", "application/json")
            .POST(HttpRequest.BodyPublishers.ofString(json))
            .build();

        HttpResponse<String> resp = HTTP.send(req, HttpResponse.BodyHandlers.ofString());
        if (resp.statusCode() != 200) {
            throw new RuntimeException("Ollama error " + resp.statusCode() + ": " + resp.body());
        }

        // Extract "response" field value — Ollama returns a single JSON object
        Matcher m = Pattern.compile("\"response\":\"((?:[^\"\\\\]|\\\\.)*)\"").matcher(resp.body());
        if (!m.find()) throw new RuntimeException("Could not parse Ollama response: " + resp.body());
        return unescapeJson(m.group(1));
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    static String readFile(String path) throws IOException {
        return Files.readString(Path.of(path));
    }

    static void writeOrPrint(String content, String[] args, String flag) throws IOException {
        for (int i = 0; i < args.length - 1; i++) {
            if (args[i].equals(flag)) {
                Path out = Path.of(args[i + 1]);
                Files.writeString(out, content);
                System.err.println("[adapter] written to " + out);
                return;
            }
        }
        System.out.println(content);
    }

    static String stripFence(String text) {
        return text.trim()
            .replaceAll("(?s)^```\\w*\\n?", "")
            .replaceAll("\\n?```\\s*$", "")
            .trim();
    }

    static String jsonStr(String s) {
        return "\"" + s
            .replace("\\", "\\\\")
            .replace("\"", "\\\"")
            .replace("\n", "\\n")
            .replace("\r", "\\r")
            .replace("\t", "\\t")
            + "\"";
    }

    static String unescapeJson(String s) {
        return s.replace("\\n", "\n")
                .replace("\\t", "\t")
                .replace("\\r", "\r")
                .replace("\\\"", "\"")
                .replace("\\\\", "\\");
    }

    static void printHelp() {
        System.out.println("""
            CabalAdapter — Python ↔ Java translation and Java endpoint interaction

            Usage:
              adapter py2java <file.py> [-o out.java]     Translate Python to Java
              adapter java2py <file.java> [-o out.py]     Translate Java to Python
              adapter call <url> [METHOD] [json_body]     HTTP call to a Java endpoint
              adapter probe <url>                         Probe endpoint reachability and headers
              adapter help                                Show this help

            Translation uses the local Ollama instance (deepseek-coder-v2).
            Set OLLAMA_BASE_URL to override (default: http://localhost:11434).

            Examples:
              adapter py2java scanner.py -o Scanner.java
              adapter java2py Parser.java -o parser.py
              adapter call http://localhost:8080/api/status
              adapter call http://localhost:8080/api/data POST '{"key":"value"}'
              adapter probe http://localhost:8080
            """);
    }
}
