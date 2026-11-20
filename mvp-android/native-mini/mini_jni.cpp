// PreceptorOS MINI-LOCAL: local text inference only; no tools, network or rack access.
#include <jni.h>
#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <numeric>
#include <string>
#include <vector>
#include "llama.h"

namespace {
std::mutex mx;
llama_model * loaded_model = nullptr;
std::string loaded_path;
bool backend_ready = false;
std::string no_data(const char *cause) { return std::string("NO_DATA(") + cause + ")"; }

/* --- bounded n-gram loop detector ---
 * Returns true if the last `window` tokens contain a repeated subsequence
 * of length >= `min_len` appearing at least `min_count` times.
 * This catches the degenerate repetition produced by greedy argmax. */
static bool has_loop(const std::vector<llama_token> &history,
                     int window, int min_len, int min_count) {
    if ((int)history.size() < window) return false;
    int n = (int)history.size();
    int tail = n - window;
    for (int len = min_len; len <= window / 2; ++len) {
        int count = 1;
        for (int i = 0; i + len * 2 < window; ++i) {
            bool match = true;
            for (int j = 0; j < len; ++j) {
                if (history[tail + i + j] != history[tail + i + len + j]) { match = false; break; }
            }
            if (match) { ++count; i += len - 1; }
        }
        if (count >= min_count) return true;
    }
    return false;
}

/* --- lightweight weighted sampling with temperature + top-k ---
 * Replaces the previous greedy argmax.  Uses only the raw logits API
 * already in use, so no extra llama.cpp sampler chain is needed. */
static llama_token sample_token(const float *logits, int32_t count,
                                float temperature, int top_k) {
    // 1. Apply temperature to logits
    std::vector<float> scaled(count);
    for (int32_t i = 0; i < count; ++i)
        scaled[i] = logits[i] / temperature;

    // 2. Top-k: find indices of the top_k largest values
    std::vector<int32_t> indices(count);
    std::iota(indices.begin(), indices.end(), 0);
    int k = std::min(top_k, (int)count);
    std::partial_sort(indices.begin(), indices.begin() + k, indices.end(),
        [&scaled](int32_t a, int32_t b) { return scaled[a] > scaled[b]; });

    // 3. Softmax over top-k
    float max_logit = scaled[indices[0]];
    float sum = 0.0f;
    std::vector<float> probs(k);
    for (int i = 0; i < k; ++i) {
        probs[i] = std::exp(scaled[indices[i]] - max_logit);
        sum += probs[i];
    }
    for (int i = 0; i < k; ++i) probs[i] /= sum;

    // 4. Weighted random pick (LCG — deterministic seed per session)
    static uint32_t seed = 42;
    seed ^= (seed << 13) ^ (seed >> 17) ^ (seed << 5);
    float r = ((double)seed) / 4294967295.0;
    float cdf = 0.0f;
    for (int i = 0; i < k; ++i) {
        cdf += probs[i];
        if (r <= cdf) return indices[i];
    }
    return indices[k - 1]; // fallback
}

std::string infer(const std::string &path, const std::string &user) {
    std::lock_guard<std::mutex> lk(mx);
    if (path.empty() || user.empty() || user.size() > 640) return no_data("mini_input_invalid");
    if (!backend_ready) { llama_backend_init(); backend_ready = true; }
    if (!loaded_model || loaded_path != path) {
        if (loaded_model) { llama_model_free(loaded_model); loaded_model = nullptr; }
        llama_model_params mp = llama_model_default_params();
        loaded_model = llama_model_load_from_file(path.c_str(), mp);
        if (!loaded_model) return no_data("mini_model_load_failed");
        loaded_path = path;
    }
    llama_context_params cp = llama_context_default_params();
    cp.n_ctx = 512; cp.n_batch = 384; cp.n_ubatch = 384;
    cp.n_threads = 4; cp.n_threads_batch = 4;
    llama_context *ctx = llama_init_from_model(loaded_model, cp);
    if (!ctx) return no_data("mini_context_init_failed");
    const llama_vocab *vocab = llama_model_get_vocab(loaded_model);
    if (!vocab) { llama_free(ctx); return no_data("mini_vocab_missing"); }
    const std::string prompt =
        "<|im_start|>system\nYou are MINI-LOCAL, a small offline PreceptorOS assistant. "
        "Answer briefly in the user's language. Do not claim internet, access to the rack, "
        "running tools, reading local files, or authorization. Say when unsure.\n<|im_end|>\n"
        "<|im_start|>user\n" + user + "\n<|im_end|>\n<|im_start|>assistant\n";
    std::vector<llama_token> tokens(384);
    int n = llama_tokenize(vocab, prompt.c_str(), (int) prompt.size(),
                           tokens.data(), (int) tokens.size(), true, true);
    if (n <= 0 || n > 384) { llama_free(ctx); return no_data("mini_tokenize_failed"); }
    llama_batch_ext *batch = llama_batch_ext_init(ctx);
    if (!batch) { llama_free(ctx); return no_data("mini_batch_init_failed"); }
    bool valid = true;
    for (int i=0; i<n; ++i) {
        int idx = llama_batch_ext_add_token(batch, 0, tokens[i]);
        llama_pos pos = i;
        if (idx < 0 || !llama_batch_ext_set_pos(batch, idx, &pos) ||
            !llama_batch_ext_set_output_logits(batch, idx, i == n-1)) {
            valid = false; break;
        }
    }
    if (!valid || llama_process(ctx, LLAMA_PROCESS_TYPE_DECODE, batch) != 0) {
        llama_batch_ext_free(batch); llama_free(ctx);
        return no_data("mini_prompt_process_failed");
    }
    std::string out;
    const int32_t count = llama_vocab_n_tokens(vocab);
    std::vector<llama_token> gen_tokens;
    gen_tokens.reserve(72);
    const float temperature = 0.8f;
    const int top_k = 40;
    const int loop_window = 12;
    const int loop_min_len = 3;
    const int loop_min_count = 2;
    for (int step = 0; step < 72 && n+step < 510; ++step) {
        float *logits = llama_get_logits_ith(ctx, -1);
        if (!logits) { out = no_data("mini_missing_logits"); break; }
        llama_token pick = sample_token(logits, count, temperature, top_k);
        if (llama_vocab_is_eog(vocab,pick)) break;
        gen_tokens.push_back(pick);
        if (has_loop(gen_tokens, loop_window, loop_min_len, loop_min_count)) {
            out += " [NO_DATA(mini_loop_detected)]";
            break;
        }
        char bytes[512] = {};
        int used = llama_token_to_piece(vocab,pick,bytes,sizeof(bytes),0,false);
        if (used > 0 && used < (int)sizeof(bytes) && out.size()+used < 4000)
            out.append(bytes,used);
        llama_batch_ext_clear(batch);
        int idx = llama_batch_ext_add_token(batch,0,pick);
        llama_pos pos = n+step;
        if (idx<0 || !llama_batch_ext_set_pos(batch,idx,&pos) ||
            !llama_batch_ext_set_output_logits(batch,idx,true) ||
            llama_process(ctx, LLAMA_PROCESS_TYPE_DECODE,batch)!=0) {
            out = no_data("mini_generation_failed"); break;
        }
    }
    llama_batch_ext_free(batch); llama_free(ctx);
    return out.empty() ? no_data("mini_empty_generation") : out;
}
}
extern "C" JNIEXPORT jstring JNICALL
Java_org_preceptoros_mvp_MiniNative_generate(JNIEnv *env, jclass, jstring jpath, jstring jprompt) {
    if (!jpath || !jprompt) return env->NewStringUTF("NO_DATA(mini_null_input)");
    const char *p=env->GetStringUTFChars(jpath,nullptr);
    const char *q=env->GetStringUTFChars(jprompt,nullptr);
    if (!p || !q) {
        if (p) env->ReleaseStringUTFChars(jpath,p);
        if (q) env->ReleaseStringUTFChars(jprompt,q);
        return env->NewStringUTF("NO_DATA(mini_utf8_error)");
    }
    std::string out=infer(p,q);
    env->ReleaseStringUTFChars(jpath,p);
    env->ReleaseStringUTFChars(jprompt,q);
    return env->NewStringUTF(out.c_str());
}
