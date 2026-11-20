#pragma once
#include <algorithm>
#include <cctype>
#include <cmath>
#include <cstdint>
#include <numeric>
#include <string>
#include <vector>

namespace mini_quality {
/* --- bounded n-gram loop detector ---
 * Returns true if the last `window` tokens contain a repeated subsequence
 * of length >= `min_len` appearing at least `min_count` times.
 * This catches the degenerate repetition produced by greedy argmax. */
static bool has_loop(const std::vector<int32_t> &history,
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
static int32_t sample_token(const float *logits, int32_t count,
                                float temperature, int top_k) {
    if (!logits || count <= 0 || top_k <= 0 || !std::isfinite(temperature) ||
        temperature <= 0.0f) return -1;

    // Ignore corrupt logits rather than sorting NaN (undefined comparator order).
    std::vector<float> scaled(count);
    std::vector<int32_t> indices;
    indices.reserve(count);
    for (int32_t i = 0; i < count; ++i) {
        if (!std::isfinite(logits[i])) continue;
        scaled[i] = logits[i] / temperature;
        if (std::isfinite(scaled[i])) indices.push_back(i);
    }
    if (indices.empty()) return -1;
    int k = std::min(top_k, (int)indices.size());
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
    if (!(sum > 0.0f) || !std::isfinite(sum)) return -1;
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

// A tiny model cannot authenticate its own claims. Suppress observed
// first-person remote/server assertions; other generated facts remain DRAFT.
static bool unsupported_self_claim(const std::string &output) {
    std::string lower = output;
    std::transform(lower.begin(), lower.end(), lower.begin(),
        [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
    const char *claims[] = {
        "i'm currently running a ", "i am currently running a ",
        "i'm connected to ", "i am connected to ",
        "i have access to ", "i can access your ",
        "i have internet access", "i ran a command", "i executed a command"
    };
    for (const char *claim : claims)
        if (lower.find(claim) != std::string::npos) return true;
    return false;
}


} // namespace mini_quality
