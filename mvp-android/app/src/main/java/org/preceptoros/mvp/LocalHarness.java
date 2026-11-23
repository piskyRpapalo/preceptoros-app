package org.preceptoros.mvp;

import android.content.Context;
import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;
import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.text.Normalizer;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * The APP's harness around any chosen model: an editable instruction (files/harness/system.txt) and retrieval
 * from the person's own documents (files/rag/*.md|*.txt), BM25 over passages, all on the phone. Retrieved
 * passages go to the model numbered [n]; the page shows the same numbered sources under the answer.
 * Nothing leaves the phone except what the chosen model's own route already carries.
 */
final class LocalHarness {
    static final String DEFAULT_SYSTEM =
        "You are a model running inside PreceptorOS, chosen by the owner of this phone. Answer in the language of "
        + "the question, briefly and exactly. When numbered sources are given, use them and cite them as [n]; if "
        + "they do not answer the question, say so. Never invent rack state, keys, signatures or measurements: "
        + "say NO_DATA and why.";
    private static final int PASSAGE = 700;
    private static final int MAX_FILES = 300;
    private static final long MAX_FILE_B = 2_000_000;

    private final Context ctx;
    private String signature = "";
    private final List<String[]> passages = new ArrayList<>();          // {file, text}
    private final List<Map<String, Integer>> tf = new ArrayList<>();
    private final Map<String, Integer> df = new HashMap<>();
    private double avgLen;

    LocalHarness(Context ctx) { this.ctx = ctx; }

    File ragDir() { return ctx.getExternalFilesDir("rag"); }
    File harnessDir() { return ctx.getExternalFilesDir("harness"); }

    String system() {
        File f = harnessDir() == null ? null : new File(harnessDir(), "system.txt");
        try {
            if (f != null && f.isFile() && f.length() > 0 && f.length() < 8000) {
                String s = new String(Files.readAllBytes(f.toPath()), StandardCharsets.UTF_8).trim();
                if (!s.isEmpty()) return s;
            }
        } catch (IOException ignored) { }
        return DEFAULT_SYSTEM;
    }

    boolean customSystem() { return !system().equals(DEFAULT_SYSTEM); }

    private File[] files() {
        File dir = ragDir();
        File[] all = dir == null ? null : dir.listFiles((d, n) -> (n.endsWith(".md") || n.endsWith(".txt")));
        if (all == null) return new File[0];
        Arrays.sort(all);
        return all.length > MAX_FILES ? Arrays.copyOf(all, MAX_FILES) : all;
    }

    synchronized JSONObject status() throws JSONException {
        index();
        return new JSONObject().put("files", files().length).put("passages", passages.size())
            .put("custom_instruction", customSystem());
    }

    static List<String> words(String s) {
        String n = Normalizer.normalize(s.toLowerCase(Locale.ROOT), Normalizer.Form.NFD).replaceAll("\\p{M}+", "");
        List<String> out = new ArrayList<>();
        for (String w : n.split("[^\\p{L}\\p{N}]+")) if (w.length() >= 3) out.add(w);
        return out;
    }

    private synchronized void index() {
        StringBuilder sig = new StringBuilder();
        File[] fs = files();
        for (File f : fs) sig.append(f.getName()).append(':').append(f.length()).append(':').append(f.lastModified()).append(';');
        if (sig.toString().equals(signature)) return;
        signature = sig.toString();
        passages.clear(); tf.clear(); df.clear();
        long total = 0;
        for (File f : fs) {
            if (f.length() > MAX_FILE_B) continue;
            String text;
            try { text = new String(Files.readAllBytes(f.toPath()), StandardCharsets.UTF_8); } catch (IOException e) { continue; }
            StringBuilder cur = new StringBuilder();
            for (String para : text.split("\\n\\s*\\n")) {
                if (cur.length() + para.length() > PASSAGE && cur.length() > 0) { add(f.getName(), cur.toString()); cur.setLength(0); }
                if (para.length() > PASSAGE * 2) {
                    for (int i = 0; i < para.length(); i += PASSAGE) add(f.getName(), para.substring(i, Math.min(para.length(), i + PASSAGE)));
                } else cur.append(para.trim()).append("\n\n");
            }
            if (cur.toString().trim().length() > 0) add(f.getName(), cur.toString());
        }
        for (Map<String, Integer> m : tf) for (int v : m.values()) total += v;
        avgLen = tf.isEmpty() ? 1 : (double) total / tf.size();
    }

    private void add(String file, String text) {
        Map<String, Integer> m = new HashMap<>();
        for (String w : words(text)) m.merge(w, 1, Integer::sum);
        if (m.isEmpty()) return;
        passages.add(new String[] {file, text.trim()});
        tf.add(m);
        for (String w : m.keySet()) df.merge(w, 1, Integer::sum);
    }

    /** Top-k passages for a question: [{n, file, text, score}], best first; empty when nothing matches. */
    synchronized JSONArray retrieve(String question, int k) throws JSONException {
        index();
        JSONArray out = new JSONArray();
        if (passages.isEmpty()) return out;
        List<String> q = words(question);
        double[] score = new double[passages.size()];
        int n = passages.size();
        for (int i = 0; i < n; i++) {
            Map<String, Integer> m = tf.get(i);
            int len = 0;
            for (int v : m.values()) len += v;
            for (String w : q) {
                Integer f = m.get(w);
                if (f == null) continue;
                double idf = Math.log(1 + (n - df.get(w) + 0.5) / (df.get(w) + 0.5));
                score[i] += idf * (f * 2.2) / (f + 1.2 * (0.25 + 0.75 * len / avgLen));
            }
        }
        Integer[] order = new Integer[n];
        for (int i = 0; i < n; i++) order[i] = i;
        Arrays.sort(order, (a, b) -> Double.compare(score[b], score[a]));
        for (int i = 0; i < Math.min(k, n); i++) {
            int p = order[i];
            if (score[p] <= 0) break;
            out.put(new JSONObject().put("n", out.length() + 1).put("file", passages.get(p)[0])
                .put("text", passages.get(p)[1]).put("score", Math.round(score[p] * 100) / 100.0));
        }
        return out;
    }

    /** The person's last question, with numbered sources in front of it (the page keeps the original text). */
    static String withSources(String question, JSONArray sources) throws JSONException {
        if (sources.length() == 0) return question;
        StringBuilder b = new StringBuilder("Sources from my documents (cite as [n] when you use one):\n");
        for (int i = 0; i < sources.length(); i++) {
            JSONObject s = sources.getJSONObject(i);
            b.append('[').append(s.getInt("n")).append("] ").append(s.getString("file")).append(":\n")
                .append(s.getString("text")).append("\n\n");
        }
        return b.append("Question: ").append(question).toString();
    }
}
